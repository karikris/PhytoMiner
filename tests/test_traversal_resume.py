import pytest
from phytominer import Seed, fetch_homologs, RunLimits, BudgetExceededError
from test_workflows import FixtureClient

def test_level_checkpoint_resume_and_corruption(tmp_path):
    c=FixtureClient()
    def stop(event):
        if event['event']=='level_completed':raise RuntimeError('interrupted after level')
    with pytest.raises(RuntimeError):fetch_homologs([Seed('1','a')],target_organisms=['1','2'],expansion_depth=4,output_dir=tmp_path,client=c,progress=stop)
    assert list((tmp_path/'traversal').glob('*.json'))
    before=len([x for x in c.calls if x[0]=='orthologs']);events=[]
    result=fetch_homologs([Seed('1','a')],target_organisms=['1','2'],expansion_depth=4,output_dir=tmp_path,client=c,progress=events.append)
    assert result.scan('relationships').collect().height==2
    assert any(e['event']=='traversal_resumed' for e in events)
    assert len([x for x in c.calls if x[0]=='orthologs'])-before==1
    with pytest.raises(BudgetExceededError):fetch_homologs([Seed('1','a')],target_organisms=['1','2'],expansion_depth=5,output_dir=tmp_path,client=c,limits=RunLimits(max_genes=1))
    result=fetch_homologs([Seed('1','a')],target_organisms=['1','2'],expansion_depth=5,output_dir=tmp_path,client=c,limits=RunLimits(max_genes=10))
    assert result.scan('relationships').collect().height==2
