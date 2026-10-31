"""Persistent retrieval events and relationship support links."""

import json
from datetime import datetime, timezone
from .storage import digest
from .models import TABLES, RELATIONSHIP_COLUMNS
lazy import polars as pl

EVENT_COLUMNS = (
    "event_id",
    "query_hash",
    "retrieved_at",
    "endpoint",
    "dataset",
    "metadata_fingerprint",
    "raw_file",
)
TABLES["retrieval_events"] = EVENT_COLUMNS
TABLES["relationship_evidence"] = RELATIONSHIP_COLUMNS + ("event_id",)


def event_for(path, client):
    record = json.loads(path.with_suffix(".json").read_text())
    timestamp = (
        record.get("retrieved_at")
        or datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
    )
    return {
        "event_id": record.get("event_id")
        or digest({"query": record["query_hash"], "retrieved_at": timestamp}),
        "query_hash": record["query_hash"],
        "retrieved_at": timestamp,
        "endpoint": client.config.endpoint,
        "dataset": client.config.dataset,
        "metadata_fingerprint": client.metadata_fingerprint,
        "raw_file": path.name,
    }


def write_evidence(writer, cache, client, edges=None):
    events = [event_for(path, client) for path in sorted(cache.used_paths)]
    writer.write(
        "retrieval_events",
        pl.LazyFrame(events, schema={c: pl.String for c in EVENT_COLUMNS}).unique(),
    )
    if edges is not None:
        if "_retrieval_event_id" in edges.collect_schema().names():
            support = edges.select(
                *RELATIONSHIP_COLUMNS, pl.col("_retrieval_event_id").alias("event_id")
            ).unique()
        else:
            support = pl.LazyFrame(
                schema={c: pl.String for c in TABLES["relationship_evidence"]}
            )
        writer.write("relationship_evidence", support)
