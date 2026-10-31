"""Raw batch execution and evidence normalization."""

lazy import polars as pl
lazy import pyarrow.parquet as pq
from .evidence import event_for

from .models import (
    TABLES,
    RELATIONSHIP_COLUMNS,
    FEATURE_ATTRIBUTES,
    ORTHOLOG_ATTRIBUTES,
    ServiceError,
)


def _empty(columns):
    return pl.LazyFrame(
        schema={c: pl.Int64 if c == "depth" else pl.String for c in columns}
    )


def _raw(client, cache, jobs):
    paths, contextual_frames = [], []

    def execute(job):
        page, genes, organism = job
        return job, cache.fetch(client, page, genes, organism)

    for (page, genes, organism), result in client.map(execute, jobs):
        if page == "orthologs":
            frame = pl.concat(
                [
                    pl.scan_parquet(path).with_columns(
                        pl.lit(event_for(path, client)["event_id"]).alias(
                            "_retrieval_event_id"
                        )
                    )
                    for path in sorted(set(result))
                ]
            )
            invalid = frame.filter(
                pl.col("ortholog__dm_gene_name").is_null()
                | ~pl.col("ortholog__dm_gene_name").is_in(genes)
                | pl.col("ortholog__dm_organism_name").is_null()
            )
            if invalid.limit(1).collect().height:
                raise ServiceError(
                    "BioMart returned an unexpected source gene or missing source name"
                )
            contextual_frames.append(
                frame.with_columns(
                    pl.lit(organism).alias("_requested_source_organism_id")
                )
            )
        else:
            paths.extend(result)
    if contextual_frames:
        return pl.concat(contextual_frames)
    return pl.scan_parquet(sorted(set(paths))) if paths else None


def _jobs(keys, batch_size):
    groups = {}
    for organism, gene in keys:
        groups.setdefault(organism, set()).add(gene)
    for organism, genes in sorted(groups.items()):
        genes = sorted(genes)
        for start in range(0, len(genes), batch_size):
            yield "orthologs", genes[start : start + batch_size], organism


def _resolve(client, cache, raw, scratch):
    if raw.limit(1).collect().is_empty():
        return _empty(RELATIONSHIP_COLUMNS + ("_retrieval_event_id",)), _empty(
            TABLES["features"]
        )
    source = raw.select(
        pl.col("ortholog__dm_gene_name").alias("gene_name"),
        pl.col("ortholog__dm_organism_name").alias("organism_name"),
    )
    target = raw.select(
        pl.col("ortholog__dm_ortholog_gene_name").alias("gene_name"),
        pl.col("ortholog__dm_ortholog_organism_name").alias("organism_name"),
    )
    refs = pl.concat([source, target]).unique()
    gene_file = scratch / "resolve-ids.parquet"
    refs.select("gene_name").unique().sort("gene_name").sink_parquet(gene_file)

    from .resolution import lookup, remember

    known_paths, missing = set(), []
    for batch in pq.ParquetFile(gene_file).iter_batches(
        batch_size=client.config.batch_size
    ):
        paths, absent = lookup(cache, client, batch.column(0).to_pylist())
        known_paths.update(paths)
        missing.extend(absent)
    previous = set(cache.used_paths)
    jobs = (
        ("resolve", missing[start : start + client.config.batch_size], None)
        for start in range(0, len(missing), client.config.batch_size)
    )
    fetched = _raw(client, cache, jobs)
    fresh_paths = cache.used_paths - previous
    if missing:
        # Include already-cached query parts used for a new resolution index.
        fresh_paths.update(cache.used_paths - known_paths - previous)
        if fetched is not None:
            # Raw query identities can already exist even when the per-gene index does not.
            for start in range(0, len(missing), client.config.batch_size):
                fresh_paths.update(
                    cache.fetch(
                        client,
                        "resolve",
                        missing[start : start + client.config.batch_size],
                        None,
                    )
                )
        remember(cache, client, missing, fresh_paths)
    paths = known_paths | fresh_paths
    features = pl.scan_parquet(sorted(paths)) if paths else None
    if features is None:
        raise ServiceError("Could not resolve reported gene identities")
    feature_mapping: dict[str, str] = dict(zip(FEATURE_ATTRIBUTES, TABLES["features"]))
    features = features.rename(feature_mapping)
    features = features.join(
        refs, on=["gene_name", "organism_name"], how="semi"
    ).unique()
    identities = features.select("organism_name", "gene_name", "organism_id").unique()
    if (
        identities.group_by("organism_name", "gene_name")
        .len()
        .filter(pl.col("len") > 1)
        .limit(1)
        .collect()
        .height
    ):
        raise ServiceError("Ambiguous organism/gene identity in BioMart features")
    mapping = dict(
        zip(
            ORTHOLOG_ATTRIBUTES,
            [
                "ortholog_group",
                "source_gene_name",
                "source_organism_name",
                "target_gene_name",
                "target_organism_name",
                "relationship",
            ],
        )
    )
    edges = raw.rename(mapping).with_columns(
        pl.col("_requested_source_organism_id").alias("source_organism_id")
    )
    for side in ("source", "target"):
        id_column = (
            "_feature_source_organism_id" if side == "source" else "target_organism_id"
        )
        lookup = identities.rename(
            {
                "organism_name": side + "_organism_name",
                "gene_name": side + "_gene_name",
                "organism_id": id_column,
            }
        )
        edges = edges.join(
            lookup,
            on=[side + "_organism_name", side + "_gene_name"],
            how="left",
            validate="m:1",
        )
    if (
        edges.filter(
            pl.col("_feature_source_organism_id").is_not_null()
            & (pl.col("_feature_source_organism_id") != pl.col("source_organism_id"))
        )
        .limit(1)
        .collect()
        .height
    ):
        raise ServiceError(
            "BioMart source feature identity conflicts with the requested organism"
        )
    return edges.select(*RELATIONSHIP_COLUMNS, "_retrieval_event_id").unique(), features


def _resolution_status(edges, features):
    identities = features.select("organism_id", "organism_name", "gene_name").unique()
    for side in ("source", "target"):
        keys = [f"{side}_organism_id", f"{side}_organism_name", f"{side}_gene_name"]
        lookup = identities.rename(
            dict(zip(("organism_id", "organism_name", "gene_name"), keys))
        )
        marker = f"_{side}_feature_verified"
        edges = edges.join(
            lookup.with_columns(pl.lit(True).alias(marker)),
            on=keys,
            how="left",
            validate="m:1",
        )
        edges = edges.with_columns(
            pl.when(pl.col(marker).fill_null(False))
            .then(pl.lit("resolved"))
            .otherwise(pl.lit("missing_feature"))
            .alias(f"{side}_resolution_status")
        ).drop(marker)
    return edges.select(TABLES["relationships"]).unique()
