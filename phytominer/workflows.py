"""Public orchestration for BioMart dataset workflows."""

from dataclasses import asdict
from pathlib import Path
from .outcomes import write_outcomes
from .evidence import write_evidence
from .run import run_context
from .contracts import Seeds, Targets
lazy import polars as pl
from .models import (
    Seed,
    TABLES,
    FEATURE_ATTRIBUTES,
    ValidationError,
    IncompleteDatasetError,
)
from .biomart import BioMartClient
from .storage import RequestCache
from .dataset import DatasetWriter, HomologDataset
from .inputs import (
    normalize_seeds,
    _normalize_targets,
    _result_identity,
    _target_identity,
)
from .lifecycle import _run_lock
from .normalization import _empty, _raw, _jobs, _resolve, _resolution_status
from .traversal import _discover
from .annotations import join_annotations


def fetch_homologs(
    seeds: Seeds,
    *,
    target_organisms: Targets = None,
    expansion_depth: int = 0,
    output_dir: str | Path,
    client: BioMartClient | None = None,
    refresh: bool = False,
    progress=None,
) -> HomologDataset:
    """Retrieve reported seed relationships; labels never multiply edge evidence."""
    seed_records = sorted(
        set(normalize_seeds(seeds)),
        key=lambda s: (s.organism_id, s.gene_name, s.label is not None, s.label or ""),
    )
    if not seed_records:
        raise ValidationError("At least one seed is required")
    if (
        not isinstance(expansion_depth, int)
        or isinstance(expansion_depth, bool)
        or expansion_depth < 0
    ):
        raise ValidationError("Expansion depth must be a nonnegative integer")
    target_organisms = _normalize_targets(target_organisms)
    if expansion_depth and not target_organisms:
        raise ValidationError("Expansion requires an explicit organism boundary")
    root = Path(output_dir)
    owned = client is None
    client = client or BioMartClient()
    try:
        with _run_lock(root), run_context(root, client, progress) as run:
            run.outcomes = [
                {
                    "organism_id": s.organism_id,
                    "gene_name": s.gene_name,
                    "status": "not_processed",
                }
                for s in seed_records
            ]
            cache = RequestCache(root / "requests", refresh=refresh)
            with run.stage("metadata"):
                fingerprint = cache.metadata(client, refresh)
                catalog = client.catalog()
                fingerprint = cache.metadata(client)
            seed_records = [
                Seed(catalog.resolve(s.organism_id), s.gene_name, s.label)
                for s in seed_records
            ]
            if target_organisms is not None:
                ids = tuple(
                    sorted({catalog.resolve(value) for value in target_organisms})
                )
                target_organisms = tuple(sorted((*ids, *catalog.names(ids))))
            identity = _result_identity(
                "homologs",
                seeds=[asdict(s) for s in seed_records],
                targets=_target_identity(target_organisms),
                depth=expansion_depth,
                metadata=fingerprint,
                endpoint=client.config.endpoint,
                dataset=client.config.dataset,
                virtual_schema=client.config.virtual_schema,
            )
            if not refresh:
                try:
                    result = HomologDataset(root)
                    if result.manifest["identity"] == identity:
                        return result
                except IncompleteDatasetError:
                    pass
            writer = DatasetWriter(root, identity, kind="homologs")
            seed_frame = pl.LazyFrame(
                [asdict(s) for s in seed_records],
                schema={c: pl.String for c in TABLES["seeds"]},
            )
            writer.write("seeds", seed_frame)
            if target_organisms == ():
                edges, features, provenance = (
                    _empty(TABLES[name])
                    for name in ("relationships", "features", "provenance")
                )
            else:
                edges, features, provenance = _discover(
                    client,
                    cache,
                    seed_records,
                    target_organisms,
                    expansion_depth,
                    writer.directory,
                    raw_fetch=_raw,
                    resolver=_resolve,
                )
            writer.write(
                "provenance",
                provenance.select(TABLES["provenance"]).sort(TABLES["provenance"]),
            )
            genes = (
                pl.concat(
                    [
                        seed_frame.select("organism_id", "gene_name"),
                        edges.select(
                            pl.col("target_organism_id").alias("organism_id"),
                            pl.col("target_gene_name").alias("gene_name"),
                        ),
                    ]
                )
                .filter(pl.col("organism_id").is_not_null())
                .unique()
            )
            seed_jobs = (
                ("features", batch, org)
                for _, batch, org in _jobs(
                    ((s.organism_id, s.gene_name) for s in seed_records),
                    client.config.batch_size,
                )
            )
            seed_features = _raw(client, cache, seed_jobs)
            if seed_features is not None:
                features = pl.concat(
                    [
                        features,
                        seed_features.rename(
                            dict(zip(FEATURE_ATTRIBUTES, TABLES["features"]))
                        ),
                    ]
                ).unique()
            features = features.join(genes, on=["organism_id", "gene_name"], how="semi")
            writer.write(
                "unmatched_genes",
                genes.join(
                    features.select("organism_id", "gene_name").unique(),
                    on=["organism_id", "gene_name"],
                    how="anti",
                ),
            )
            write_outcomes(writer, run, seed_frame, features, edges)
            write_evidence(writer, cache, client, edges)
            edges = _resolution_status(edges, features)
            writer.write("relationships", edges.sort(TABLES["relationships"]))
            writer.write("features", features.sort(TABLES["features"]))
            writer.write("genes", genes.sort("organism_id", "gene_name"))
            writer.write(
                "organisms",
                features.select("organism_id", "organism_name")
                .unique()
                .sort("organism_id"),
            )
            unresolved = edges.filter(
                (pl.col("source_resolution_status") == "missing_feature")
                | (pl.col("target_resolution_status") == "missing_feature")
            )
            writer.write("unresolved_relationships", unresolved)
            return writer.finish(
                metadata_fingerprint=fingerprint,
                endpoint=client.config.endpoint,
                metrics=run.metrics(),
                run_id=run.id,
                unresolved_identity_rows=writer.manifest["tables"][
                    "unresolved_relationships"
                ]["rows"],
            )
    finally:
        if owned:
            client.close()


def fetch_features(
    genes: Seeds,
    *,
    output_dir: str | Path,
    client: BioMartClient | None = None,
    refresh: bool = False,
    progress=None,
) -> HomologDataset:
    """Retrieve transcript-grain features for organism-qualified genes."""
    gene_keys = sorted({(s.organism_id, s.gene_name) for s in normalize_seeds(genes)})
    if not gene_keys:
        raise ValidationError("At least one gene is required")
    root = Path(output_dir)
    owned = client is None
    client = client or BioMartClient()
    try:
        with _run_lock(root), run_context(root, client, progress) as run:
            cache = RequestCache(root / "requests")
            with run.stage("metadata"):
                fingerprint = cache.metadata(client, refresh)
                catalog = client.catalog()
                fingerprint = cache.metadata(client)
            gene_keys = sorted(
                {(catalog.resolve(org), gene) for org, gene in gene_keys}
            )
            identity = _result_identity(
                "features",
                genes=gene_keys,
                metadata=fingerprint,
                endpoint=client.config.endpoint,
                dataset=client.config.dataset,
                virtual_schema=client.config.virtual_schema,
            )
            if not refresh:
                try:
                    previous = HomologDataset(root)
                    if previous.manifest["identity"] == identity:
                        return previous
                except IncompleteDatasetError:
                    pass
            writer = DatasetWriter(root, identity, kind="features")
            jobs = (
                ("features", batch, org)
                for _, batch, org in _jobs(gene_keys, client.config.batch_size)
            )

            def execute(job):
                return cache.fetch(client, *job, refresh=refresh)

            paths = [path for result in client.map(execute, jobs) for path in result]
            features = (
                pl.scan_parquet(paths).rename(
                    dict(zip(FEATURE_ATTRIBUTES, TABLES["features"]))
                )
                if paths
                else _empty(TABLES["features"])
            )
            wanted = pl.LazyFrame(
                [{"organism_id": o, "gene_name": g} for o, g in gene_keys]
            )
            features = features.join(
                wanted, on=["organism_id", "gene_name"], how="semi"
            ).unique()
            writer.write("genes", wanted)
            writer.write("features", features.sort(TABLES["features"]))
            writer.write(
                "organisms",
                features.select("organism_id", "organism_name")
                .unique()
                .sort("organism_id"),
            )
            writer.write(
                "unmatched_genes",
                wanted.join(
                    features.select("organism_id", "gene_name").unique(),
                    on=["organism_id", "gene_name"],
                    how="anti",
                ),
            )
            write_outcomes(writer, run, wanted, features)
            write_evidence(writer, cache, client)
            return writer.finish(
                metadata_fingerprint=fingerprint, metrics=client.metrics
            )
    finally:
        if owned:
            client.close()
