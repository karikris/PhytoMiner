# Reviewed improvement backlog

Prepared issue payloads: [backlog-issues.json](backlog-issues.json). Publish only after the final code SHA passes all CI jobs.

| ID | Improvement | Priority | Status after 1.0.1 |
| --- | --- | --- | --- |
| B01 | Validate organism selections against a cached catalog | P1 | Open follow-up |
| B02 | Preserve authoritative source identity when features are missing | P1 | Addressed; verify then close |
| B03 | Add per-seed outcome statuses | P1 | Open follow-up |
| B04 | Attach retrieval timestamps and query provenance to evidence | P1 | Open follow-up |
| B05 | Bound expansion by genes requests time and output size | P1 | Open follow-up |
| B06 | Persist traversal state for expansion resume | P2 | Open follow-up |
| B07 | Reuse resolved organism and gene identities | P2 | Open follow-up |
| B08 | Restrict target organisms before expensive enrichment | P2 | Open follow-up |
| B09 | Replace positional normalization with explicit mappings | P1 | Addressed; verify then close |
| B10 | Define complete schemas for every dataset kind | P1 | Open follow-up |
| B11 | Version processing contracts in result identity | P1 | Addressed; verify then close |
| B12 | Strengthen derived dataset identity | P1 | Open follow-up |
| B13 | Add cache inspection and safe garbage collection | P2 | Open follow-up |
| B14 | Offer explicit dataset verification modes | P2 | Open follow-up |
| B15 | Add cancellation and overall run deadlines | P1 | Open follow-up |
| B16 | Coordinate endpoint limits across clients | P2 | Open follow-up |
| B17 | Add per-run metrics and stage diagnostics | P2 | Open follow-up |
| B18 | Improve public typing and exception contracts | P2 | Open follow-up |
| B19 | Strengthen annotation import validation | P1 | Open follow-up |
| B20 | Separate workflow orchestration components | P2 | Open follow-up |
| B21 | Add formatting linting and static checking | P2 | Open follow-up |
| B22 | Add property based scientific and cache tests | P1 | Open follow-up |
| B23 | Require meaningful nonempty documentation fixtures | P2 | Open follow-up |
| B24 | Benchmark the complete retrieval workflow | P2 | Open follow-up |
| B25 | Diversify benchmark data and cardinalities | P2 | Open follow-up |
| B26 | Test minimum supported dependency versions | P2 | Open follow-up |

Publication is idempotent by stable hidden markers. Reconcile existing open and
closed issues before creating; record URLs immediately in a local ignored receipt.
Do not assign users or create milestones. B10 is only partially addressed by the
current schema work. Final tracking issue links every item.

All 23 remaining items are implemented for 1.0.2; see [acceptance map](ACCEPTANCE_1.0.2.md). GitHub closures follow the final exact-SHA CI gate. The JSON payloads retain the original 1.0.1 review snapshot.
