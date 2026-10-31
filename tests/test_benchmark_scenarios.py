import runpy
import pytest

@pytest.mark.parametrize('scenario',['low','high'])
def test_varied_benchmark_known_counts(scenario):
    run=runpy.run_path('scripts/benchmark_dataset.py')['run']
    report=run(1000,scenario)
    assert report['sql_polars_match'] and report['scenario']==scenario
