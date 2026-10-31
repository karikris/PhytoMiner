"""Non-executable traversal state with validated immutable level artifacts."""

import json
from .storage import atomic_json, digest, checksum
from .inputs import PROCESSING_CONTRACT_VERSION


class TraversalCheckpoint:
    def __init__(self, cache, client, roots, targets, depth):
        self.root = cache.root.parent
        key = digest(
            {
                "roots": roots,
                "targets": targets,
                "depth": depth,
                "metadata": client.metadata_fingerprint,
                "endpoint": client.config.endpoint,
                "dataset": client.config.dataset,
                "version": PROCESSING_CONTRACT_VERSION,
            }
        )
        self.path = self.root / "traversal" / f"{key}.json"
        self.refresh = cache.refresh

    def load(self):
        if self.refresh:
            return None
        try:
            envelope = json.loads(self.path.read_text())
            state = envelope["state"]
            if envelope["checksum"] != digest(state):
                return None
            for record in state["artifacts"]:
                path = (self.root / record["file"]).resolve()
                if (
                    not path.is_relative_to(self.root.resolve())
                    or checksum(path) != record["sha256"]
                ):
                    return None
            return state
        except OSError, ValueError, KeyError, TypeError:
            return None

    def save(
        self, depth, frontier, visited, queried, edges, features, provenance, used_paths
    ):
        files = [
            *edges,
            *features,
            *provenance,
            *used_paths,
            *(p.with_suffix(".json") for p in used_paths),
        ]
        state = {
            "depth": depth,
            "frontier": [
                [list(root), [list(n) for n in sorted(nodes)]]
                for root, nodes in sorted(frontier.items())
            ],
            "visited": [
                [list(root), [list(n) for n in sorted(nodes)]]
                for root, nodes in sorted(visited.items())
            ],
            "queried": [list(n) for n in sorted(queried)],
            "edges": [p.relative_to(self.root).as_posix() for p in edges],
            "features": [p.relative_to(self.root).as_posix() for p in features],
            "provenance": [p.relative_to(self.root).as_posix() for p in provenance],
            "used_paths": [
                p.relative_to(self.root).as_posix() for p in sorted(used_paths)
            ],
            "artifacts": [
                {"file": p.relative_to(self.root).as_posix(), "sha256": checksum(p)}
                for p in files
            ],
        }
        atomic_json(self.path, {"state": state, "checksum": digest(state)})
