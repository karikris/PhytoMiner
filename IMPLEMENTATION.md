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
