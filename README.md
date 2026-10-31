# PhytoMiner

Phytozome BioMart XML retrieval with Polars, Parquet and DuckDB, on **Python 3.15+**.
Version 0.3.0 provides a new dataset API. See [migration notes](docs/MIGRATION.md).

```bash
pip install phytominer==0.3.0
# Development: uv sync --locked --extra dev
```

Retrieve reported seed relationships and enrich distinct genes with transcript-level
features. Seed labels stay separate from relationship evidence.

```python
from phytominer import Seed, fetch_homologs

dataset = fetch_homologs(
    [Seed('167', 'AT1G01090', label='NDHA')],
    output_dir='phytominer-output',
)
print(dataset.summary().collect())
relationships = dataset.scan('relationships')  # Polars LazyFrame
```

```python
with dataset.connect() as connection:
    rows = connection.sql('SELECT count(*) FROM relationships').fetchall()
    print(rows)
```

`scan(table)` returns a lazy frame; call `collect()` only when needed. `connect()`
returns a caller-owned DuckDB connection with views over the same Parquet files.
DuckDB 2 uses `fetchall()` on relations.

For explicit expansion, supply `expansion_depth=1` to search one additional level
and `target_organisms=['167', '454']` to bound traversal and results. Exact organism
names reported by BioMart are also accepted; use stable proteome IDs where possible.
Seeds may start outside the traversal boundary. Relationship labels always describe
the reported source/target edge; provenance records the root seed and depth.

```python
from phytominer import fetch_features, join_annotations

features = fetch_features([Seed('167', 'AT1G01090')], output_dir='features-output')
annotated = join_annotations(dataset, 'annotations.tsv')
annotated.sink_parquet('annotated_genes.parquet')
```

Annotations require `organism_id` and `gene_name`, or explicit column-name mappings.
Duplicate keys are rejected. CSV/TSV inputs default to headers and string columns;
headerless input requires `has_header=False, column_names=[...]`. Parquet is also
supported. `annotation_match` distinguishes matched rows. Supply a separate
`output_dir` to persist annotations as a derived dataset.

## Data and resume behavior

Tables include `seeds`, `genes`, `organisms`, `relationships`, `provenance`,
`features`, `unmatched_genes`, and `unresolved_relationships`. Features retain all
transcripts. Relationships retain organism names alongside organism IDs.

Phytozome can report relationships whose genes are absent from feature queries.
Those relationships remain in the output. Requested source IDs stay populated;
unresolved target IDs stay null. Schema-2 relationships include
`source_resolution_status` and `target_resolution_status`, each `resolved` or
`missing_feature`. Either missing side places the row in `unresolved_relationships`
and contributes to `manifest['unresolved_identity_rows']`.
Expansion skips identities it cannot resolve; ambiguous identities raise an error.
An unmatched gene is distinct from a successfully resolved gene with no homologs.

An unchanged validated run resumes without network retrieval. Request identity,
metadata fingerprints, checksums, schemas and row counts guard cache reuse.
Use `refresh=True` to refresh metadata and request results. A metadata fingerprint
does not detect every remote data update. New generations are staged privately and validated before the root manifest is
replaced atomically. Failed replacements leave the last complete generation
readable; first-ever incomplete runs remain unavailable. Existing reader handles
stay pinned to their generation. Only one writer may use an output directory; after a
crash remove `.writer.lock` only after confirming the original process has stopped.
Old table generations are retained; remove unused run directories explicitly.

## Concurrency and lazy imports

`BioMartClient(ClientConfig(...))` configures retrieval. Defaults: two workers,
100 identifiers per batch, two starts/second, four attempts, and 10/120-second
connect/read timeouts. Workers may be set from one to four. A shared cooldown
honors `Retry-After`; throttling reduces concurrency to one for the rest of the run.
These are conservative client settings, not published server quotas. Seven small
live requests succeeded at concurrency levels one, two and four; sustained capacity
has not been established.

Explicit Python 3.15 lazy imports defer analytics engines. Package/API imports load
none of them; opening a dataset loads Arrow for validation, scanning loads Polars,
and SQL access loads DuckDB. The library does not change global lazy-import mode.

## Development and validation

```bash
uv sync --locked --extra dev
uv run --no-sync pytest -q
uv run --no-sync python scripts/benchmark_imports.py
uv build
```

CI validates Python 3.15.2 on Linux, macOS and Windows. Offline tests require no
Phytozome access. `examples/workflow.py` is an executable live example, tested with
an injected fixture client. Details and research evidence: [implementation ledger](IMPLEMENTATION.md).

License: [MIT](LICENSE).

Measured workload results and limitations: [validation report](docs/validation.json).

Target selection is explicit: `target_organisms=None` retrieves all reported
organisms; `target_organisms=[]` retrieves no relationships and skips ortholog
requests while retaining seed feature enrichment. Selections are normalized once,
so duplicate or reordered selections resume equivalently. Processing-contract
changes rebuild published results from compatible validated raw checkpoints.

See [operational contracts](docs/OPERATIONS.md) for schema 3, organism resolution,
seed outcomes, limits/cancellation, traversal resume, annotation normalization,
verification modes, shared scheduling, and reader-safe cleanup.
