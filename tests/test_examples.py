import runpy
from test_workflows import FixtureClient

def test_executable_example(tmp_path):
    run=runpy.run_path('examples/workflow.py')['run']
    dataset,counts,total=run(tmp_path,client=FixtureClient())
    assert total==dataset.scan('relationships').collect().height
    assert counts['reported_edges'].sum()==total
