# 0.3.0 acceptance map

All tasks have local acceptance evidence. Close issues only after exact-SHA remote CI succeeds.

| Issue | Task | Commit | Evidence |
| --- | --- | --- | --- |
| [#20](https://github.com/karikris/PhytoMiner/issues/20) | 1.1 | 6a64c6d | tests/test_correctness.py |
| [#18](https://github.com/karikris/PhytoMiner/issues/18) | 1.2 | b551cb1 | tests/test_contracts.py |
| [#21](https://github.com/karikris/PhytoMiner/issues/21) | 1.3 | f60ae19 | Ruff and Pyright CI |
| [#26](https://github.com/karikris/PhytoMiner/issues/26) | 1.4 | 1e566cc | scripts/check_minimum.py |
| [#10](https://github.com/karikris/PhytoMiner/issues/10) | 2.1 | bb6f4d2 | tests/test_schema3.py |
| [#12](https://github.com/karikris/PhytoMiner/issues/12) | 2.2 | b77c0fd | tests/test_derived.py |
| [#4](https://github.com/karikris/PhytoMiner/issues/4) | 2.3 | a781662 | tests/test_evidence.py |
| [#17](https://github.com/karikris/PhytoMiner/issues/17) | 2.4 | 9a1d4de | tests/test_run.py |
| [#1](https://github.com/karikris/PhytoMiner/issues/1) | 3.1 | 654ae15 | tests/test_catalog.py |
| [#7](https://github.com/karikris/PhytoMiner/issues/7) | 3.2 | 6550018 | tests/test_catalog.py |
| [#3](https://github.com/karikris/PhytoMiner/issues/3) | 3.3 | b764cac | tests/test_outcomes.py |
| [#5](https://github.com/karikris/PhytoMiner/issues/5) | 4.1 | fad1e4b | tests/test_limits.py |
| [#15](https://github.com/karikris/PhytoMiner/issues/15) | 4.2 | ffd9c94 | tests/test_limits.py |
| [#16](https://github.com/karikris/PhytoMiner/issues/16) | 4.3 | d717cf7 | tests/test_transport.py |
| [#6](https://github.com/karikris/PhytoMiner/issues/6) | 5.1 | f21a567 | tests/test_traversal_resume.py |
| [#8](https://github.com/karikris/PhytoMiner/issues/8) | 5.2 | 019d6f3 | tests/test_early_filter.py |
| [#19](https://github.com/karikris/PhytoMiner/issues/19) | 6.1 | d586ccf | tests/test_annotations_strict.py |
| [#14](https://github.com/karikris/PhytoMiner/issues/14) | 6.2 | 0e7402b | tests/test_verification.py |
| [#13](https://github.com/karikris/PhytoMiner/issues/13) | 6.3 | c958b65 | tests/test_maintenance.py |
| [#22](https://github.com/karikris/PhytoMiner/issues/22) | 7.1 | 2d12189 | tests/test_properties.py |
| [#23](https://github.com/karikris/PhytoMiner/issues/23) | 7.2 | 5aa80f3 | tests/test_examples.py |
| [#24](https://github.com/karikris/PhytoMiner/issues/24) | 7.3 | aa4aaa9 | tests/test_pipeline_benchmark.py |
| [#25](https://github.com/karikris/PhytoMiner/issues/25) | 7.4 | final release SHA | tests/test_benchmark_scenarios.py |

All seven local phase gates passed. Phase 1 includes the lowest-direct environment;
phase 2 schema/provenance identity; phase 3 catalog/cache/outcomes; phase 4 shared
limits and cancellation; phase 5 validated resume/filter equivalence; phase 6
annotation and cross-process lease cleanup; phase 7 generated invariants, meaningful
examples and low/high-cardinality full-pipeline benchmarks.

See VALIDATION_0.3.0.json and OPERATIONS.md for measured results and behavioral limits.
