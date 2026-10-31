"""Versioned manifests over compact canonical Parquet tables."""

import json
import hashlib
import os
import uuid
import time
from copy import deepcopy
from .maintenance import maintenance_lock, reader_lease
from pathlib import Path
from datetime import datetime, timezone
lazy import duckdb
lazy import polars as pl
lazy import pyarrow.parquet as pq
lazy import pyarrow as pa
from .storage import atomic_json, checksum
from .models import TABLES, TABLES_V1, IncompleteDatasetError, ValidationError

from .schemas import TABLES_V2, REQUIRED, NULLABLE, KEYS

DATASET_SCHEMA_VERSION = 3


def _validate_manifest(root, manifest, *, verify="full"):
    """Validate an unpublished candidate or an existing published generation."""
    root = Path(root)
    try:
        if manifest["status"] != "complete" or manifest["schema_version"] not in (
            1,
            DATASET_SCHEMA_VERSION,
        ):
            raise ValueError("Incomplete or unsupported manifest")
        schemas = {1: TABLES_V1, 2: TABLES_V2}.get(manifest["schema_version"], TABLES)
        if manifest["schema_version"] == 3:
            kind = manifest.get("kind")
            if kind not in REQUIRED or not REQUIRED[kind] <= manifest["tables"].keys():
                raise ValueError(
                    "Missing required dataset tables or unknown dataset kind"
                )
        for name, record in manifest["tables"].items():
            path = (root / record["file"]).resolve()
            if not path.is_relative_to(root.resolve()) or (
                verify == "full" and checksum(path) != record["sha256"]
            ):
                raise ValueError("Invalid dataset file")
            with pq.ParquetFile(path) as file:
                if name in schemas:
                    if file.schema_arrow.names != list(schemas[name]):
                        raise ValueError("Invalid dataset table schema")
                    for field in file.schema_arrow:
                        valid_type = (
                            pa.types.is_int64(field.type)
                            if field.name == "depth"
                            else (
                                pa.types.is_string(field.type)
                                or pa.types.is_large_string(field.type)
                            )
                        )
                        if not valid_type:
                            raise ValueError("Invalid dataset column type")
                if manifest["schema_version"] == 3 and name in (
                    "annotations",
                    "annotated_genes",
                ):
                    for key in ("organism_id", "gene_name"):
                        if key not in file.schema_arrow.names or not (
                            pa.types.is_string(file.schema_arrow.field(key).type)
                            or pa.types.is_large_string(
                                file.schema_arrow.field(key).type
                            )
                        ):
                            raise ValueError("Invalid annotation key schema")
                    if name == "annotated_genes" and (
                        "annotation_match" not in file.schema_arrow.names
                        or not pa.types.is_boolean(
                            file.schema_arrow.field("annotation_match").type
                        )
                    ):
                        raise ValueError("Invalid annotation match schema")
                if file.metadata.num_rows != record["rows"]:
                    raise ValueError("Invalid dataset row count")
            if manifest["schema_version"] == 3 and verify == "full":
                keys = KEYS.get(name, ())
                required_columns = [
                    c for c in schemas.get(name, keys) if c not in NULLABLE
                ]
                columns = list(dict.fromkeys((*keys, *required_columns)))
                seen = set()
                with pq.ParquetFile(path) as checked:
                    if not set(columns) <= set(checked.schema_arrow.names):
                        raise ValueError("Missing dataset key")
                    for batch in checked.iter_batches(batch_size=4096, columns=columns):
                        for column in required_columns:
                            if batch.column(column).null_count:
                                raise ValueError("Null required dataset key or value")
                        if name == "seed_outcomes":
                            for row in batch.to_pylist():
                                if row["status"] not in (
                                    "matched",
                                    "no_homologs",
                                    "missing_gene",
                                    "unresolved",
                                ):
                                    raise ValueError("Invalid published seed outcome")
                        if keys:
                            for row in batch.to_pylist():
                                identity = hashlib.sha256(
                                    json.dumps([row[k] for k in keys]).encode()
                                ).digest()
                                if identity in seen:
                                    raise ValueError("Duplicate dataset keys")
                                seen.add(identity)

    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        pa.ArrowException,
    ) as exc:
        raise IncompleteDatasetError(f"Cannot open dataset: {exc}") from exc


class DatasetWriter:
    def __init__(self, root, identity, *, kind="collection"):
        self.root = Path(root)
        self.generation = uuid.uuid4().hex
        self.directory = self.root / "tables" / self.generation
        self.directory.mkdir(parents=True, exist_ok=True)
        from . import __version__

        self.manifest = {
            "package_version": __version__,
            "kind": kind,
            "schema_version": DATASET_SCHEMA_VERSION,
            "status": "incomplete",
            "identity": identity,
            "tables": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        atomic_json(self.directory / "manifest.json", self.manifest)

    def write(self, name, frame):
        started = time.monotonic()
        columns = TABLES.get(name)
        if columns is not None:
            frame = frame.select(
                [
                    pl.col(c).cast(pl.Int64 if c == "depth" else pl.String, strict=True)
                    for c in columns
                ]
            )
        path = self.directory / (name + ".parquet")
        temp = path.with_suffix(".parquet.tmp")
        try:
            frame.sink_parquet(temp, compression="zstd", row_group_size=65536)
            from .run import CURRENT_RUN

            active = CURRENT_RUN.get()
            if active is not None:
                active.check_output(self.directory)
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)
        self.manifest["tables"][name] = {
            "file": path.relative_to(self.root).as_posix(),
            "sha256": checksum(path),
            "rows": pq.ParquetFile(path).metadata.num_rows,
        }
        atomic_json(self.directory / "manifest.json", self.manifest)
        if active is not None:
            active.timings["persist"] += time.monotonic() - started

    def finish(self, **details):
        started = time.monotonic()
        from .run import CURRENT_RUN

        active = CURRENT_RUN.get()
        if active is not None:
            active.check_output(self.directory)
        candidate = {**self.manifest, **details, "status": "complete"}
        pinned = HomologDataset._from_manifest(self.root, candidate)
        atomic_json(self.directory / "manifest.json", pinned.manifest)
        if active is not None:
            active.check()
        atomic_json(self.root / "manifest.json", pinned.manifest)
        self.manifest = deepcopy(pinned.manifest)
        if active is not None:
            active.timings["publication"] += time.monotonic() - started
        return pinned


class HomologDataset:
    def __init__(self, root, *, verify="full"):
        if verify not in ("full", "metadata"):
            raise ValidationError("verify must be full or metadata")
        self.verification_mode = verify
        self.root = Path(root)
        self._lease = None
        with maintenance_lock(self.root):
            try:
                manifest = json.loads((self.root / "manifest.json").read_text())
            except (OSError, ValueError) as exc:
                raise IncompleteDatasetError(f"Cannot open dataset: {exc}") from exc
            if verify == "full":
                _validate_manifest(self.root, manifest)
            else:
                _validate_manifest(self.root, manifest, verify=verify)
            self.manifest = deepcopy(manifest)
            self._lease = reader_lease(self.root, self.manifest)

    @classmethod
    def _from_manifest(cls, root, manifest):
        result = cls.__new__(cls)
        result._lease = None
        result.root = Path(root)
        result.verification_mode = "full"
        with maintenance_lock(result.root):
            _validate_manifest(root, manifest)
            result.manifest = deepcopy(manifest)
            result._lease = reader_lease(result.root, result.manifest)
        return result

    def close(self):
        lease = getattr(self, "_lease", None)
        if lease is not None and lease.exists():
            with maintenance_lock(self.root):
                lease.unlink(missing_ok=True)
            self._lease = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass  # Unknown leases stay protected after a crash or busy maintenance.

    def scan(self, table):
        if table not in self.manifest["tables"]:
            raise ValidationError(f"Unknown table: {table}")
        return pl.scan_parquet(self.root / self.manifest["tables"][table]["file"])

    def summary(self):
        """Count reported edges and distinct genes without label/transcript fanout."""
        return (
            self.scan("relationships")
            .group_by("target_organism_id", "target_organism_name", "relationship")
            .agg(
                pl.col("target_gene_name").n_unique().alias("homolog_genes"),
                pl.struct("source_organism_id", "source_gene_name")
                .n_unique()
                .alias("query_genes"),
                pl.len().alias("reported_edges"),
            )
            .sort("target_organism_id", "target_organism_name", "relationship")
        )

    def connect(self, database=":memory:"):
        """Return a caller-owned DuckDB connection with Parquet-backed views."""
        connection = duckdb.connect(str(database))
        try:
            for name, record in self.manifest["tables"].items():
                connection.read_parquet(
                    str((self.root / record["file"]).resolve())
                ).create_view(name, replace=True)
        except Exception:
            connection.close()
            raise
        return connection
