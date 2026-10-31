from phytominer import Seed, fetch_homologs
from test_workflows import FixtureClient

def test_events_resume_refresh(tmp_path):
    client=FixtureClient()
    a=fetch_homologs([Seed('1','a')],output_dir=tmp_path,client=client)
    before=a.scan('retrieval_events').collect().to_dicts()
    assert before and a.scan('relationship_evidence').collect().height==1
    b=fetch_homologs([Seed('1','a')],output_dir=tmp_path,client=client)
    assert b.scan('retrieval_events').collect().to_dicts()==before
    c=fetch_homologs([Seed('1','a')],output_dir=tmp_path,client=client,refresh=True)
    assert {r['event_id'] for r in c.scan('retrieval_events').collect().to_dicts()}.isdisjoint({r['event_id'] for r in before})
