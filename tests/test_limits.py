import pytest
from phytominer import Seed, fetch_homologs, RunLimits, BudgetExceededError, HomologDataset
from test_workflows import FixtureClient

@pytest.mark.parametrize('limits',[RunLimits(max_genes=1),RunLimits(max_output_bytes=1)])
def test_limits_preserve_publication(tmp_path,limits):
    old=fetch_homologs([Seed('1','a')],output_dir=tmp_path,client=FixtureClient())
    before=(tmp_path/'manifest.json').read_bytes()
    with pytest.raises(BudgetExceededError):
        fetch_homologs([Seed('1','a')],output_dir=tmp_path,client=FixtureClient(),limits=limits,refresh=True)
    assert (tmp_path/'manifest.json').read_bytes()==before
    assert HomologDataset(tmp_path).manifest==old.manifest

def test_http_budget_reservation(tmp_path):
    from phytominer.run import RunContext
    run=RunContext(tmp_path,FixtureClient(),limits=RunLimits(max_requests=1))
    run.before_http()
    with pytest.raises(BudgetExceededError):run.before_http()
