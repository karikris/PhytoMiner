# Migrating to 1.0

This is a breaking release. All InterMine implementation, dependencies, service
configuration, pipeline wrappers and plotting have been removed. Existing CSV
checkpoints are not imported because they lack validated query identity.

Use organism-qualified `Seed` records and `fetch_homologs` instead of the previous
three-stage pipeline. Direct reported relationships are the default; chained
searches require an explicit expansion depth and organism boundary. Labels and
root provenance are separate tables and no longer determine deduplication.

The new API returns a `HomologDataset`, with `scan` for Polars LazyFrames and
`connect` for DuckDB views. Parquet replaces CSV checkpoints and canonical output.
Use native Polars export methods when CSV is needed for another tool.

Names are snake_case. Relationship identity includes source and target organisms,
genes, group and reported relationship. Organism names remain alongside nullable
IDs so unavailable feature records cannot silently erase relationship evidence.
Unknown relationship categories are preserved. There is no relationship ranking
that discards alternative evidence.

Use `fetch_features` for transcript-grain features and `join_annotations` for
explicit local annotations. Sequence, expression, coexpression and cluster queries
are outside 1.0. No visualization is generated implicitly.

Python 3.15 is required because the package uses explicit lazy-import syntax.
Dependency versions validated during implementation are recorded in `uv.lock`.
Development and CI use CPython 3.15.2; free-threaded builds are not supported by
this trial. No package is published automatically by push or release events.
