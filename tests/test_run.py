import json
from phytominer import Seed, fetch_homologs
from test_workflows import FixtureClient

def test_run_metrics_isolated_and_progress(tmp_path):
    c=FixtureClient();events=[]
    a=fetch_homologs([Seed('1','a')],output_dir=tmp_path,client=c,progress=events.append)
    assert a.manifest['metrics']['cache_misses']>0
    fetch_homologs([Seed('1','a')],output_dir=tmp_path,client=c)
    runs=[json.loads(p.read_text()) for p in (tmp_path/'.runs').glob('*.json')]
    assert len(runs)==2
    assert any(r['metrics']['cache_misses']==0 for r in runs)
    assert c.run is None and events[0]['event']=='run_started'
    assert events[-1]['status']=='complete'
