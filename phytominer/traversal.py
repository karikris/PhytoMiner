"""Root-aware breadth-first traversal."""

lazy import polars as pl
lazy import pyarrow.parquet as pq
from .checkpoints import TraversalCheckpoint
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
    all_edges = _empty(RELATIONSHIP_COLUMNS + ("_retrieval_event_id",))
    checkpoint = TraversalCheckpoint(cache, client, roots, targets, expansion_depth)
    restored = checkpoint.load()
    start_depth = 1
    if restored:
        frontier = {
            tuple(root): {tuple(n) for n in nodes}
            for root, nodes in restored["frontier"]
        }
        visited = {
            tuple(root): {tuple(n) for n in nodes}
            for root, nodes in restored["visited"]
        }
        queried = {tuple(n) for n in restored["queried"]}
        edge_parts = [checkpoint.root / p for p in restored["edges"]]
        feature_parts = [checkpoint.root / p for p in restored["features"]]
        provenance_parts = [checkpoint.root / p for p in restored["provenance"]]
        cache.used_paths.update(checkpoint.root / p for p in restored["used_paths"])
        all_edges = (
            pl.scan_parquet(edge_parts).unique()
            if edge_parts
            else _empty(RELATIONSHIP_COLUMNS + ("_retrieval_event_id",))
        )
        start_depth = restored["depth"] + 1
        if client.run is not None:
            client.run.track_genes(set().union(*visited.values()))
            client.run.emit("traversal_resumed", completed_depth=restored["depth"])
    for depth in range(start_depth, expansion_depth + 2):
        if client.run is not None:
            client.run.check()
        needed = set().union(*frontier.values()) - queried
        if needed:
            raw = raw_fetch(client, cache, _jobs(needed, client.config.batch_size))
            if raw is not None and targets is not None:
                catalog = client.catalog()
                allowed_ids = {catalog.resolve(value) for value in targets}
                raw = raw.filter(
                    pl.col("ortholog__dm_ortholog_organism_name").is_in(
                        catalog.names(allowed_ids)
                    )
                )
            edges, features = (
                resolver(client, cache, raw, scratch)
                if raw is not None
                else (
                    _empty(RELATIONSHIP_COLUMNS + ("_retrieval_event_id",)),
                    _empty(TABLES["features"]),
                )
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
            if client.run is not None:
                client.run.track_genes(
                    (row[0] or row[1], row[2])
                    for row in edges.select(
                        "target_organism_id", "target_organism_name", "target_gene_name"
                    )
                    .unique()
                    .collect()
                    .iter_rows()
                )
                client.run.check_output(scratch)
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
        checkpoint.save(
            depth,
            frontier,
            visited,
            queried,
            edge_parts,
            feature_parts,
            provenance_parts,
            cache.used_paths,
        )
        if client.run is not None:
            client.run.emit("level_completed", depth=depth)
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
