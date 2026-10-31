"""Conservative generation inventory and explicit, revalidated cleanup."""

import json
import os
import shutil
import uuid
from pathlib import Path
from contextlib import contextmanager
from .models import ValidationError
from .storage import atomic_json, digest


@contextmanager
def maintenance_lock(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / ".maintenance.lock"
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ValidationError(
            "Dataset maintenance is active; retry after it finishes"
        ) from exc
    os.close(fd)
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


def reader_lease(root, manifest):
    path = Path(root) / ".leases" / f"{uuid.uuid4().hex}.json"
    generations = sorted(
        {Path(r["file"]).parent.as_posix() for r in manifest["tables"].values()}
    )
    atomic_json(path, {"pid": os.getpid(), "generations": generations})
    return path


def _inventory(root):
    root = Path(root).resolve()
    protected = set()
    all_protected = False
    try:
        manifest = json.loads((root / "manifest.json").read_text())
        protected.update(
            Path(r["file"]).parent.as_posix() for r in manifest["tables"].values()
        )
    except FileNotFoundError:
        pass
    except ValueError, KeyError:
        all_protected = True
    leases = []
    for lease in (root / ".leases").glob("*.json"):
        leases.append((lease.name, lease.read_text()))
        try:
            protected.update(json.loads(lease.read_text())["generations"])
        except ValueError, KeyError:
            all_protected = True
    for checkpoint in (root / "traversal").glob("*.json"):
        try:
            state = json.loads(checkpoint.read_text())["state"]
            protected.update(
                Path(r["file"]).parent.as_posix() for r in state["artifacts"]
            )
        except ValueError, KeyError:
            all_protected = True
    records = []
    for generation in sorted((root / "tables").glob("*")):
        if not generation.is_dir() or generation.is_symlink():
            continue
        files = []
        for p in sorted(generation.rglob("*")):
            if p.is_symlink():
                all_protected = True
            if p.is_file():
                files.append(
                    (
                        p.relative_to(root).as_posix(),
                        p.stat().st_size,
                        p.stat().st_mtime_ns,
                    )
                )
        status = "staging"
        try:
            status = json.loads((generation / "manifest.json").read_text())["status"]
        except OSError, ValueError, KeyError:
            pass
        records.append(
            {
                "generation": generation.relative_to(root).as_posix(),
                "bytes": sum(f[1] for f in files),
                "status": status,
                "files": files,
            }
        )
    writer = (root / ".writer.lock").exists()
    candidates = (
        []
        if writer or all_protected or "." in protected
        else [r for r in records if r["generation"] not in protected]
    )
    requests = {"complete": 0, "failed": 0}
    for p in (root / "requests").glob("*.json"):
        try:
            record = json.loads(p.read_text())
            if "query_hash" in record:
                requests[record.get("status", "failed")] += 1
        except ValueError, KeyError:
            pass
    return {
        "generations": records,
        "protected": sorted(protected),
        "leases": leases,
        "writer_active": writer,
        "requests": requests,
        "candidates": candidates,
    }


def inspect_cache(root):
    with maintenance_lock(root):
        return _inventory(root)


def plan_cleanup(root):
    with maintenance_lock(root):
        inventory = _inventory(root)
        return {
            "root": str(Path(root).resolve()),
            "fingerprint": digest(inventory),
            "generations": [r["generation"] for r in inventory["candidates"]],
            "files": [f[0] for r in inventory["candidates"] for f in r["files"]],
        }


def execute_cleanup(root, plan):
    root = Path(root).resolve()
    with maintenance_lock(root):
        current = _inventory(root)
        expected = {
            "root": str(root),
            "fingerprint": digest(current),
            "generations": [r["generation"] for r in current["candidates"]],
            "files": [f[0] for r in current["candidates"] for f in r["files"]],
        }
        if plan != expected:
            raise ValidationError("Cleanup plan is stale; inspect and plan again")
        for name in plan["generations"]:
            path = (root / name).resolve()
            if not path.is_relative_to(root / "tables"):
                raise ValidationError("Unsafe cleanup path")
            shutil.rmtree(path)
        return list(plan["files"])
