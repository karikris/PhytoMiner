"""Fresh-process lazy/eager startup and first-use measurements; no network."""
import json
import statistics
import subprocess
import sys

CODE = '''
import json, time, tracemalloc
tracemalloc.start()
start=time.perf_counter()
import phytominer
{imports}
import_seconds=time.perf_counter()-start
first=time.perf_counter()
import polars as pl
import duckdb
import pyarrow as pa
assert pl.DataFrame({{"x":[1]}}).height == 1
with duckdb.connect() as c:
    assert c.sql("select 1").fetchall() == [(1,)]
pa.table({{"x":[1]}})
print(json.dumps({{"import_seconds":import_seconds,"first_use_seconds":time.perf_counter()-first,"total_seconds":time.perf_counter()-start,"python_peak_bytes":tracemalloc.get_traced_memory()[1]}}))
'''

def benchmark(repeats=3):
    result={}
    for mode,imports in [('lazy',''),('eager','import polars, duckdb, pyarrow, requests')]:
        samples=[json.loads(subprocess.check_output([sys.executable,'-c',CODE.format(imports=imports)],text=True)) for _ in range(repeats)]
        result[mode]={key:statistics.median(s[key] for s in samples) for key in samples[0]}
    return result

if __name__=='__main__':
    print(json.dumps(benchmark(),indent=2))
