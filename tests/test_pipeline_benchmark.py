import runpy

def test_pipeline_benchmark_counts_and_stages():
    run=runpy.run_path('scripts/benchmark_pipeline.py')['run_pipeline']
    result=run(6,2)
    assert result['resume']['query_calls']==0 and result['network_requests']==0
    assert result['parse_seconds']>0
    assert result['initial']['metrics']['stages']['traversal']>0
    assert result['initial']['metrics']['rows']>0
