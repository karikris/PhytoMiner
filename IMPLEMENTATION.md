# Implementation ledger

Work stays on main. Each task: version-aware GitHits research, implementation,
local acceptance checks, commit, clean-tree handshake. Each phase: cumulative
checks, push, exact-SHA remote CI success before the next phase. Corrective commits
are additive. No package publication.

## 1.1 Runtime foundation
GitHits: github:python/cpython@v3.15.2, Doc/whatsnew/3.15.rst:238-248
confirms explicit lazy imports are restricted to module scope.
GitHits: pypi:pytest@9.2.0, doc/en/how-to/unittest.rst:200-210 verifies
fixture patterns. Python installer catalog was stale; selected official standalone
CPython 3.15.2 release 20261026 directly. CI uses setup-python 3.15.2.
Legacy dependencies are temporarily retained for baseline verification in this
one task and removed in 1.2. Publishing automation is removed pending release.
Acceptance: CPython 3.15.2 install and analytics imports available; existing nine
baseline tests pass; wheel and sdist build. Task handshake PASS.

## 1.2 Legacy removal
Previous handshake: bc2a588 (nine baseline tests and build passed).
GitHits: github:python/cpython@v3.15.2 Doc/reference/import.rst:391-401
confirms sys.modules is observable import evidence. Removed all old runtime
modules, tests and outdated review; no compatibility facade retained.
Acceptance: replacement import/removal tests pass and dependency lock excludes
the old backend and dataframe/plotting stack. Task handshake PASS.

## 1.3 Lightweight contracts
Previous handshake: 7371279. GitHits: CPython v3.15.2
Doc/library/dataclasses.rst:569-575 verifies post-init validation;
Doc/reference/simple_stmts.rst:892-902 verifies lazy exported names.
Delivered frozen seed/configuration contracts, typed exceptions and table grains.
Acceptance: all eight contract tests pass; fresh-process import remains light.
Task handshake PASS. Phase 1 ready for remote verification.

## Phase 1 remote handshake
740c3b5: run 41176375569 PASS on Linux, macOS, Windows; origin/main matches.

## 2.1 Metadata
Previous task: 740c3b5. GitHits pypi:requests@2.34.2 src/requests/adapters.py
and hosted models.raise_for_status verify transport/status APIs. Live official
dataset metadata confirms phytozome and separate attribute pages.
Acceptance: metadata/schema/organism identity tests and cumulative suite PASS.

## 2.2 XML and streaming parser
Previous handshake: f07311d. GitHits requests@2.34.2
src/requests/models.py:990-1028 confirms iter_lines with stream=True avoids
whole-response loading. Explicit UTF-8 encoding; fixed attribute-order parser.
Acceptance: escaping, unknown page, error/HTML, truncation, empty and bounded
batch tests plus cumulative suite PASS. Yielded batches remain provisional until
completion; phase 3 storage commits only after generator exhaustion.

## 2.3 Transport scheduler
Previous handshake: a810d1c. GitHits CPython v3.15.2
Doc/library/concurrent.futures.rst:642-652 verifies wait/pending-future semantics.
Requests 2.34.2 streaming API evidence reused. Worker-local connection reuse,
bounded futures, shared start limiter, retry-after cooldown and serial downgrade.
Acceptance: local HTTP server verifies retry, rate, concurrency and terminal
failures; cumulative tests PASS. BatchSizeError signals transactional splitting
in the storage consumer rather than yielding duplicate retry data.

## Phase 2 remote handshake
81a1beb: run 41176606924 PASS on all three platforms. Live adapter ortholog
query returned 585 rows. Global organism enumeration is slow and will not be
used in workflows: resolve discovered names through bounded feature queries.

## 3.1 Atomic persistence
Previous handshake: 81a1beb. GitHits pyarrow@26.0.0
pyarrow/parquet/core.py:1068-1151 confirms schema-bound ParquetWriter and
compression. Bounded row groups, Zstandard and atomic promotion after producer
completion. Acceptance: truncation never publishes; empty/null/string-ID typed
round trips and cumulative suite PASS.

## 3.2 Validated resume
Previous handshake: 8cda75c.
GitHits CPython v3.15.2 Doc/library/os.rst:2882-2892 verifies same-filesystem
atomic replacement. Query hashes include XML/endpoint/metadata/schema version;
checksums, schemas and row counts validate every reused part. Split results are
cached transactionally. Metadata snapshots support offline unchanged resume.
Acceptance: corruption, input changes, refresh, failed queries and split-cache
resume tests plus cumulative suite PASS.

## 3.3 Dataset publication
Previous handshake: ad984c8.
GitHits polars@2.1.0 src/polars/lazyframe/frame.py:2463-2472 confirms
sink_parquet Zstandard and row-group options. Each generation has compact tables;
manifest is published atomically only after all writes. Incomplete runs cannot
be opened. Acceptance: publication/incomplete/corruption tests and cumulative
suite PASS; phase 3 ready for remote handshake.

## Phase 3 remote handshake
e7cc854: run 41176856442 PASS on Linux/macOS/Windows.

## 4.1 Direct retrieval
Previous handshake: e7cc854. GitHits polars@2.1.0 LazyFrame join/unique
APIs researched; local fixtures verify identity-qualified joins. Discover target
organism identities through bounded unscoped feature queries, avoiding the slow
whole-genome organism scan. Gene-name resolution is checked against exact
reported organism names; ambiguous/missing identities fail visibly.
Acceptance: duplicate evidence, multiple labels, transcript grain, novel
relationships, empty results, target selection and offline resume PASS.

## 4.2 Bounded expansion
Previous handshake: f187234.
GitHits polars@2.1.0 src/polars/lazyframe/frame.py:6074-6082 verifies semi/anti
joins. Breadth-first traversal persists each level, tracks visited pairs per
root and queries each pair once globally. Direct edges retain reported values;
root discovery depth is separate. Acceptance: cycles, boundaries, multiple roots,
query-once and depth tests plus cumulative suite PASS.

## 4.3 Features and annotations
Previous handshake: 4661494. GitHits polars@2.1.0
src/polars/io/csv/functions.py:558-950 verifies explicit headers/schema handling;
LazyFrame.join validate=m:1 evidence reused. Scoped feature API preserves every
transcript; unmatched genes are explicit. CSV/TSV/Parquet annotations join on
organism+gene with duplicate-key rejection and optional derived dataset output.
Acceptance: transcript grain, organism-qualified annotation matching, unmatched
flags, duplicate rejection and cumulative suite PASS.

## Phase 4 corrective handshake
Review found refresh should replace canonical request checkpoints rather than
use a separate transient namespace. Corrected and added a regression test;
cleaned exception/annotation handling. GitHits atomic replacement evidence from
3.2 applies. Cumulative suite PASS; phase gate restarts on corrected SHA.

## Phase 4 live-data corrective handshake
Live AT1G01090 retrieval found five reported target genes missing from features
among 586 distinct source/target references. Preserve reported organism names in
relationships/provenance, leave unresolved IDs null, expose an explicit
unresolved_relationships table and manifest count, and skip those nodes during
expansion. Ambiguous mappings still fail. This evidence-driven adjustment avoids
both data loss and invented IDs. Added a stale-target regression test. GitHits
Polars left-join/null-preservation contracts apply. Cumulative suite PASS.

## Phase 4 remote handshake
b080c9d: run 41177295268 PASS on all platforms. Live all-target run retains
585 relationships with five explicitly unresolved target identities; Sorghum-only
run returns one edge, two genes and two feature records. Unchanged live resume
makes zero HTTP requests. Fixtures match across workers 1/2/4.

## 5.1 Lazy analytics
Previous handshake: b080c9d. GitHits polars@2.1.0 group_by/agg/struct/n_unique
API evidence checked. summary() is lazy and counts unique edges, query genes and
target genes without joining labels/transcripts. Acceptance: lazy result and
scientific-grain regression plus cumulative suite PASS.

## 5.2 DuckDB views
Previous handshake: b4903ee. GitHits duckdb@2.0.0
duckdb/_relation.py:2836-2842 verifies relation.create_view(name, replace=True).
Use relation APIs instead of interpolating file paths in SQL. Connection is
caller-owned; Parquet remains canonical. Acceptance: SQL/Polars count parity,
transcript counts and quoted-path tests plus cumulative suite PASS.

5.2 pre-commit handshake caught DuckDB 2.0 removal of relation.fetchone();
verified upstream and changed examples/tests to fetchall(). Cumulative rerun PASS.

## 5.3 Lazy-import trial
Previous handshake: 903a768. GitHits CPython v3.15.2
Doc/whatsnew/3.15.rst:179-240 confirms first-use failures and isolated global
mode. Explicit module-scope lazy imports; transport/Arrow resolve before worker
dispatch. Opening a dataset uses Arrow to validate Parquet metadata; SQL access
then loads DuckDB and scanning loads Polars. Package/API imports load none of
these engines. Fresh-process tests cover boundaries, concurrent first use,
deferred exceptions and isolated global mode. Benchmark measures import, first
use, total time and Python allocation peak (not total native RSS).
Acceptance: cumulative suite and benchmark PASS.

## Phase 5 remote handshake
c7fc527: run 41177526286 PASS on all three platforms. Fresh-process import
benchmark (median of three): lazy import 0.000208s, first analytics use 0.349935s,
total 0.350226s; eager harness import 0.425372s, first use 0.020374s, total
0.445756s. Harness eagerly imports requests too; this is a scenario comparison,
not an isolated causal speedup claim. Python allocation peaks 24.8/30.3 MB.

## 6.1 Documentation and examples
Previous handshake: c7fc527. GitHits DuckDB 2.0 relation.create_view/fetchall and
Polars 2.1 scan/sink APIs rechecked. Added migration guide and executable example
with fixture injection. Docs explicitly describe unresolved IDs, traversal depth,
cache refresh, lock recovery and conservative concurrency. Acceptance: executable
example and cumulative suite PASS; no live access in ordinary tests.

## 6.2 Installation and performance
Previous handshake: 946fa70. GitHits Arrow@26.0.0
pyarrow/parquet/core.py:540-603 verifies bounded iter_batches; Polars 2.1
group aggregation and DuckDB 2.0 relation APIs checked. Added isolated wheel
installation and million-row benchmark to each platform CI job. Deterministic
worker tests and SQL-without-Polars import tests PASS. Local cumulative suite: 44
tests. Benchmark removed a redundant full-edge deduplication from summaries
because canonical relationship tables are already deduplicated at ingestion.
One million synthetic rows: 0.205s, 442046-byte Parquet, 619737088-byte peak process
RSS, matching SQL/Polars counts, zero network. These are measurements on this
machine and repetitive data, not memory/throughput guarantees. See validation.json
for small workload and import comparison. Installed-wheel smoke test PASS.

## 6.3 Release audit and preparation
Previous handshake: dcc2d6d. GitHits CPython v3.15.2
Doc/library/zipfile.rst:309-311,437-441 verifies distribution inspection APIs.
Prepared 1.0.0 with a single version source, Python 3.15.2 development pin, SPDX
license metadata and no publication workflow. Clean builds exclude every removed
module. Audits inspect runtime source, wheel, sdist and dependency declarations.
Final review tightened integer/finite configuration checks, query identity,
manifest package/schema metadata, response metrics and transactional stream
retries. Connection failures do not trigger futile batch splitting. Executed all
README Python blocks with fixture injection. Local acceptance: 51 tests PASS,
wheel/sdist build PASS, isolated wheel install PASS, legacy audit PASS.
Final remote handshake is performed on this task's commit; SHA and CI run are
reported in the completion message, avoiding a self-referential commit hash.

## Task commit index

| Task | Commit |
| --- | --- |
| 1.1 Runtime | bc2a588 |
| 1.2 Removal | 7371279 |
| 1.3 Contracts | 740c3b5 |
| 2.1 Metadata | f07311d |
| 2.2 XML/parser | a810d1c |
| 2.3 Scheduler | 81a1beb |
| 3.1 Atomic Parquet | 8cda75c |
| 3.2 Resume | ad984c8 |
| 3.3 Publication | e7cc854 |
| 4.1 Direct search | f187234 |
| 4.2 Expansion | 4661494 |
| 4.3 Enrichment | 54b9893 |
| Phase 4 refresh correction | db34525 |
| Phase 4 live-data correction | b080c9d |
| 5.1 Polars | b4903ee |
| 5.2 DuckDB | 903a768 |
| 5.3 Lazy imports | c7fc527 |
| 6.1 Examples/docs | 946fa70 |
| 6.2 Performance/install | dcc2d6d |
| 6.3 Final audit | Final completion SHA |

# 1.0.1 correctness work

Stay on main; commit each task after tests/diff checks. Push once after four
local phase handshakes, then require exact-SHA CI before issue publication.

## Task 1.1 — Target selection
Base: 32c177a. GitHits CPython v3.15.2 Doc/builtins/stdtypes.rst:1754-1764
verifies tuple(iterable) materializes iterators. Normalize once; None and empty
selection stay distinct, selections sort/deduplicate, empty selection skips
ortholog requests. Targeted regressions and cumulative suite PASS; clean-tree
commit handshake required before 1.2.

## Task 1.2 — Processed-result identity
Previous handshake: Task 1.1 commit. GitHits CPython v3.15.2 JSON serialization
contracts checked. Canonical target mode and processing contract version 2 apply
to all processed workflow identities; raw XML cache hashes remain unchanged.
Both request orders, equivalent selections, and old-result rebuild from raw cache
pass with the cumulative suite. Task commit/clean-tree handshake PASS.
