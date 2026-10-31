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
