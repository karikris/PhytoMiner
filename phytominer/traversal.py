"""Root-aware breadth-first traversal."""

lazy import polars as pl
lazy import pyarrow.parquet as pq
from .models import TABLES, RELATIONSHIP_COLUMNS
from .normalization import _empty, _jobs


def _discover(
    client, cache, seeds, targets, expansion_depth, scratch, *, raw_fetch, resolver
):
    roots = sorted({(s.organism_id, s.gene_name) for s in seeds})
    frontier = {root: {root} for root in roots}
    visited = {root: {root} for root in roots}
    queried = set()
    edge_parts, feature_parts, provenance_parts = [], [], []
    all_edges = _empty(RELATIONSHIP_COLUMNS)
    for depth in range(1, expansion_depth + 2):
        needed = set().union(*frontier.values()) - queried
        if needed:
            raw = raw_fetch(client, cache, _jobs(needed, client.config.batch_size))
            edges, features = (
                resolver(client, cache, raw, scratch)
                if raw is not None
                else (_empty(RELATIONSHIP_COLUMNS), _empty(TABLES["features"]))
            )
            sources = pl.LazyFrame(
                [
                    {"source_organism_id": o, "source_gene_name": g}
                    for o, g in sorted(needed)
                ]
            )
            edges = edges.join(
                sources, on=["source_organism_id", "source_gene_name"], how="semi"
            )
            if targets is not None:
                edges = edges.filter(
                    pl.col("target_organism_id").is_in(targets)
                    | pl.col("target_organism_name").is_in(targets)
                )
            edge_path = scratch / f"edges-{depth}.parquet"
            feature_path = scratch / f"features-{depth}.parquet"
            edges.sink_parquet(edge_path)
            features.sink_parquet(feature_path)
            edge_parts.append(edge_path)
            feature_parts.append(feature_path)
            all_edges = pl.scan_parquet(edge_parts).unique()
            queried.update(needed)
        front = [
            {
                "root_organism_id": r[0],
                "root_gene_name": r[1],
                "source_organism_id": n[0],
                "source_gene_name": n[1],
            }
            for r, nodes in frontier.items()
            for n in nodes
        ]
        if not front:
            break
        step = (
            all_edges.join(
                pl.LazyFrame(front),
                on=["source_organism_id", "source_gene_name"],
                how="inner",
            )
            .with_columns(pl.lit(depth).alias("depth"))
            .select(TABLES["provenance"])
            .unique()
        )
        path = scratch / f"provenance-{depth}.parquet"
        step.sink_parquet(path)
        provenance_parts.append(path)
        next_frontier = {root: set() for root in roots}
        for batch in pq.ParquetFile(path).iter_batches(batch_size=4096):
            for row in batch.to_pylist():
                root = (row["root_organism_id"], row["root_gene_name"])
                node = (row["target_organism_id"], row["target_gene_name"])
                if node[0] is not None and node not in visited[root]:
                    visited[root].add(node)
                    next_frontier[root].add(node)
        frontier = next_frontier
        if not any(frontier.values()):
            break
    return (
        all_edges,
        pl.scan_parquet(feature_parts).unique()
        if feature_parts
        else _empty(TABLES["features"]),
        pl.scan_parquet(provenance_parts).unique()
        if provenance_parts
        else _empty(TABLES["provenance"]),
    )
