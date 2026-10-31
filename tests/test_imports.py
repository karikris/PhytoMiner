import subprocess
import sys
import pytest

def run(code, *flags):
    return subprocess.run([sys.executable,*flags,'-c',code],check=True,text=True,capture_output=True,timeout=30)

def test_subsystem_import_boundaries():
    run("""
import sys
from phytominer import Seed, ClientConfig, BioMartClient, HomologDataset
Seed('1','a'); ClientConfig(); BioMartClient()
HomologDataset.__name__
assert not {'polars','duckdb','pyarrow','requests'} & sys.modules.keys()
""")

def test_concurrent_first_use():
    run("""
from concurrent.futures import ThreadPoolExecutor
lazy import polars as pl
with ThreadPoolExecutor(max_workers=4) as e:
    assert list(e.map(lambda _:pl.DataFrame({'x':[1]}).height,range(8))) == [1]*8
""")

def test_deferred_failure_has_use_site():
    run("""
lazy import phytominer_missing_dependency_for_test
try:
    phytominer_missing_dependency_for_test.example
except ModuleNotFoundError as error:
    assert error.name == 'phytominer_missing_dependency_for_test'
else:
    raise AssertionError('deferred dependency error missing')
""")

def test_global_lazy_mode_is_isolated():
    run("""
import phytominer
from phytominer import Seed
assert Seed('1','a').gene_name == 'a'
""",'-X','lazy_imports=all')
