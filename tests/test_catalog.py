import pytest
from phytominer import Seed, fetch_homologs, ValidationError
from test_workflows import FixtureClient

def test_catalog_selection_and_empty(tmp_path):
    c=FixtureClient();catalog=c.catalog()
    assert catalog.resolve('org2')=='2'
    with pytest.raises(ValidationError):catalog.resolve('typo')
    a=fetch_homologs([Seed('1','a')],target_organisms=['2'],output_dir=tmp_path,client=c)
    b=fetch_homologs([Seed('1','a')],target_organisms=['org2'],output_dir=tmp_path,client=c)
    assert a.manifest['identity']==b.manifest['identity']
    empty=fetch_homologs([Seed('1','missing')],target_organisms=['2'],output_dir=tmp_path,client=c)
    assert empty.scan('relationships').collect().is_empty()

def test_identity_cache_reuses_features_across_different_queries(tmp_path):
    c=FixtureClient()
    fetch_homologs([Seed('1','a')],output_dir=tmp_path,client=c)
    before=len([x for x in c.calls if x[0]=='resolve'])
    fetch_homologs([Seed('1','b')],output_dir=tmp_path,client=c)
    assert len([x for x in c.calls if x[0]=='resolve'])==before
    fetch_homologs([Seed('1','b')],output_dir=tmp_path,client=c,refresh=True)
    assert len([x for x in c.calls if x[0]=='resolve'])>before
