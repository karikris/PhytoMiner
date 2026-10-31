from phytominer import Seed, fetch_homologs
from test_workflows import FixtureClient
from test_correctness import MissingFeatures

def test_outcomes_do_not_multiply_labels(tmp_path):
    d=fetch_homologs([Seed('1','a','X'),Seed('1','a','Y'),Seed('1','missing')],output_dir=tmp_path,client=FixtureClient())
    rows=d.scan('seed_outcomes').collect().to_dicts()
    assert len(rows)==2 and rows[0]['status']=='matched'
    d=fetch_homologs([Seed('1','a')],target_organisms=[],output_dir=tmp_path,client=FixtureClient())
    assert d.scan('seed_outcomes').collect()['status'].to_list()==['no_homologs']
    d=fetch_homologs([Seed('1','a')],output_dir=tmp_path,client=MissingFeatures({'org1'}),refresh=True)
    assert d.scan('seed_outcomes').collect()['feature_status'].to_list()==['missing_feature']
