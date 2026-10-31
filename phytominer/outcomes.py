"""One scientific outcome per organism-qualified seed."""

from .models import TABLES
lazy import polars as pl

COLUMNS = TABLES["seed_outcomes"]


def write_outcomes(writer, run, seeds, features, edges=None):
    keys = ["organism_id", "gene_name"]
    frame = seeds.select(keys).unique()
    found = features.select(keys).unique().with_columns(pl.lit(True).alias("_found"))
    frame = frame.join(found, on=keys, how="left")
    if edges is not None:
        matched = (
            edges.select(
                pl.col("source_organism_id").alias("organism_id"),
                pl.col("source_gene_name").alias("gene_name"),
            )
            .unique()
            .with_columns(pl.lit(True).alias("_matched"))
        )
        frame = frame.join(matched, on=keys, how="left")
    else:
        frame = frame.with_columns(pl.col("_found").alias("_matched"))
    frame = (
        frame.with_columns(
            pl.when(pl.col("_matched").fill_null(False))
            .then(pl.lit("matched"))
            .when(pl.col("_found").fill_null(False))
            .then(pl.lit("no_homologs"))
            .otherwise(pl.lit("missing_gene"))
            .alias("status"),
            pl.when(pl.col("_found").fill_null(False))
            .then(pl.lit("resolved"))
            .otherwise(pl.lit("missing_feature"))
            .alias("feature_status"),
        )
        .select(COLUMNS)
        .sort(keys)
    )
    writer.write("seed_outcomes", frame)
    run.outcomes = frame.collect().to_dicts()
