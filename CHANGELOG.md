# Changelog

## 0.3.0

This release replaces the previous InterMine API with BioMart XML retrieval and
a new dataset API. Python 3.15 is required for explicit lazy imports; analytics
use Polars, Parquet and DuckDB. See [migration notes](docs/MIGRATION.md).

- Resolve organisms from cached configuration metadata and reuse verified identities.
- Add schema-3 kinds, seed outcomes, persistent retrieval evidence and per-run diagnostics.
- Add optional budgets, cancellation, shared endpoint scheduling and level resume.
- Validate annotation interpretation and strengthen derived content identity.
- Add verification modes, reader leases, cache inventory and explicit safe cleanup.
- Add typing/static checks, minimum-dependency CI, generated invariants and realistic benchmarks.

- Distinguish unrestricted and empty target filters, including cached results.
- Preserve requested source identity when BioMart feature records are missing.
- Report missing feature evidence on either relationship side in schema 2.
- Keep schema-1 reads and compatible raw-request checkpoints supported.
- Publish validated generations atomically without hiding prior complete output.
- Add regression and failure-injection coverage across the three fixes.
