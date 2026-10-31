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

## 1.0.1 correctness update

`None` and empty target selection have different result identities. Empty
selection skips ortholog queries and returns no relationships; seed features may
still be fetched. Reordered/duplicate selections normalize equivalently.

Processed identities now include processing-contract version 2. Old processed
outputs are rebuilt; compatible validated raw XML checkpoints remain reusable.
No forced remote refetch is needed unless `refresh=True` is requested.

New dataset writes use schema 2 and include source/target resolution statuses.
Missing source features do not erase relationships: the request's organism ID is
authoritative. `resolved` means matching feature evidence verifies the identity;
`missing_feature` marks missing evidence. Either missing side contributes to the
unresolved table/count. Missing target IDs stay null and cannot be traversed.
Conflicting identity mappings fail rather than override requested identity.

Schema-1 datasets remain readable by Polars/SQL with their original columns;
missing diagnostic columns are not fabricated. Old erroneous outputs should be
recomputed through the workflows to receive the corrected processing contract.

Generation-private manifests now hold incomplete work. A candidate is fully
validated before root-manifest publication. Failed refresh/replacement attempts
keep the previous publication readable and preserve validated raw checkpoints.
Previously opened dataset handles continue reading their original generation.
