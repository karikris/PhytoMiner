# PhytoMiner 0.3.0 operational contracts

Python 3.15 and explicit lazy imports remain required. Schema 3 adds dataset kinds,
retrieval events, relationship evidence and seed outcomes. Schemas 1 and 2 remain
readable without inventing absent diagnostics. Processing contract 3 invalidates
old processed outputs while compatible raw XML checkpoints remain reusable.

## Selection, evidence and outcomes

Catalog entries come from organism ID and ortholog-name configuration options,
matched through unique display labels. IDs, canonical names and exact unique labels
are accepted. Invalid/ambiguous selections raise ValidationError; valid organisms
with no evidence return empty results. Catalog caches share the metadata snapshot.
A catalog organism mapping does not certify that a gene exists.

Targets are filtered locally before enrichment, using catalog names. No unverified
remote restriction is sent. Source identity remains request-authoritative. Missing
feature evidence is explicit and unresolved target IDs cannot be traversed.

Each unique seed has matched, no_homologs or missing_gene status and a separate
feature_status. Failed/unprocessed seeds are private run diagnostics and never
published as successful results. Labels do not multiply outcomes.

retrieval_events retain timestamps and query hashes; relationship_evidence joins
reported relationship columns to event_id. Resume preserves events, refresh creates
new events. Incidental retrieval timestamps/event IDs are excluded from derived
scientific content identity. Annotation format, mappings, headers and whitespace
interpretation are included.

## Run controls and resume

Pass RunLimits(max_genes=..., max_requests=..., max_seconds=...,
max_output_bytes=...) and optionally CancellationToken via cancel=token.
Limits are optional. HTTP attempts include retries and metadata, per invocation.
Elapsed deadlines are per invocation; graph/output limits cover discovered state
and the generation output. Raw request cache storage is outside the output budget.
Output checks happen at bounded write/stage boundaries, not byte-by-byte.

Stops raise BudgetExceededError, DeadlineExceededError or CancelledError, retain
validated checkpoints, and leave the last complete generation published. Cancellation
is cooperative: queued/backoff work checks promptly, but an in-flight socket can
remain blocked until its capped read timeout. This is not a hard realtime deadline.

Completed expansion levels checkpoint frontier, visited pairs, queried pairs and
checksummed artifacts as JSON. Compatible runs resume the latest valid level; larger
budgets can be supplied. Corruption or changed scientific input causes reconstruction
from compatible raw checkpoints. Never deserialize executable checkpoint objects.

progress=callback receives structured run/stage/level events. .runs/<run-id>.json
contains isolated cache/HTTP counters, request metrics, timings and stop reasons.
A client may be reused sequentially; simultaneous runs on one client are rejected.

Endpoint rate/concurrency/cooldown coordination is process-local, using the most
restrictive live participating clients. Close unused clients. Separate processes
require external coordination; no cross-process service quota is claimed.

## Annotation validation

CSV/TSV identifiers are strings. Parquet key columns must already be strings.
Missing columns, mapping collisions, reserved annotation_match/underscore-prefixed
names, blank/null keys and duplicates are rejected. Whitespace defaults to reject;
whitespace='trim' is explicit and duplicates are checked after trimming.

## Opening and cleanup

HomologDataset(root, verify='full') checks checksums, metadata and scientific key
contracts. verify='metadata' explicitly skips checksums and row-value uniqueness/null
checks, retaining schema, path containment and row counts. It cannot detect every
same-shape content corruption. Full verification remains the default.

Dataset handles are context managers and hold reader leases. Keep a handle open
while using its lazy frames or DuckDB connections. close() releases its lease;
finalization is best effort. Unknown/stale leases remain protected after crashes.
Reclaim a stale lease only after explicitly confirming its process/readers stopped.

inspect_cache(root) reports generations, request states and leases. plan_cleanup(root)
is a dry run listing exact candidate files. execute_cleanup(root, plan) revalidates
the plan under the maintenance lock and rejects stale plans. Published, pinned,
checkpoint-referenced generations and active writers are protected. Raw request
files are retained conservatively; cleanup reclaims unreferenced generations only.
Never remove a writer/maintenance lock until its owning operation is confirmed stopped.
