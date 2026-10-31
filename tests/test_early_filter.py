from phytominer import Seed,fetch_homologs
from test_workflows import FixtureClient

def test_target_prefilter_avoids_unwanted_enrichment(tmp_path):
    c=FixtureClient()
    d=fetch_homologs([Seed('1','a')],target_organisms=['1'],output_dir=tmp_path/'filtered',client=c)
    assert d.scan('relationships').collect().is_empty()
    assert not [call for call in c.calls if call[0]=='resolve']
    full=fetch_homologs([Seed('1','a')],output_dir=tmp_path/'full',client=FixtureClient())
    expected=full.scan('relationships').filter(__import__('polars').col('target_organism_id')=='1').collect()
    assert expected.height==d.scan('relationships').collect().height
