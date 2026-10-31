"""Validated feature-resolution index over reusable raw request parts."""

import json
from .models import FEATURE_ATTRIBUTES
from .storage import digest, atomic_json


def resolution_index(cache, client):
    key = digest(
        {
            "endpoint": client.config.endpoint,
            "dataset": client.config.dataset,
            "metadata": client.metadata_fingerprint,
            "version": 1,
        }
    )
    path = cache.root / f"resolution-{key}.json"
    try:
        index = json.loads(path.read_text())
    except OSError, ValueError:
        index = {}
    return path, index


def lookup(cache, client, genes):
    _, index = resolution_index(cache, client)
    paths = set()
    missing = []
    for gene in genes:
        record = index.get(gene)
        if not cache.refresh and record and cache.valid(record, FEATURE_ATTRIBUTES):
            if client.run is not None:
                client.run.increment("identity_cache_hits")
            paths.update(cache.root / p["file"] for p in record["parts"])
        else:
            missing.append(gene)
    cache.used_paths.update(paths)
    return paths, missing


def remember(cache, client, genes, paths):
    from .storage import checksum
    import pyarrow.parquet as pq

    path, index = resolution_index(cache, client)
    parts = [
        {
            "file": p.name,
            "sha256": checksum(p),
            "rows": pq.ParquetFile(p).metadata.num_rows,
        }
        for p in sorted(paths)
    ]
    for gene in genes:
        index[gene] = {"status": "complete", "parts": parts}
    atomic_json(path, index)
