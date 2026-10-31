import pytest
from phytominer import plan_cleanup, execute_cleanup, inspect_cache, ValidationError
from test_derived import parent

def test_cleanup_protects_pinned_and_published(tmp_path):
    old=parent(tmp_path,'a');old_generation=next(iter(old.manifest['tables'].values()))['file'].split('/')[1]
    current=parent(tmp_path,'b')
    assert not plan_cleanup(tmp_path)['generations']
    old.close()
    plan=plan_cleanup(tmp_path)
    assert plan['generations']==['tables/'+old_generation]
    assert execute_cleanup(tmp_path,plan)
    assert current.scan('genes').collect()['gene_name'].to_list()==['b']
    assert inspect_cache(tmp_path)['leases']
    with pytest.raises(ValidationError):execute_cleanup(tmp_path,plan)
    current.close()

def test_writer_blocks_cleanup(tmp_path):
    (tmp_path/'.writer.lock').touch()
    assert plan_cleanup(tmp_path)['generations']==[]
