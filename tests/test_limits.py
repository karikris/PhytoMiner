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

def test_cancel_and_deadline_cleanup(tmp_path):
    import time
    from phytominer import CancellationToken, CancelledError, DeadlineExceededError
    token=CancellationToken();token.cancel()
    with pytest.raises(CancelledError):fetch_homologs([Seed('1','a')],output_dir=tmp_path,client=FixtureClient(),cancel=token)
    assert not (tmp_path/'.writer.lock').exists()
    class Slow(FixtureClient):
        def metadata(self): time.sleep(.01); return super().metadata()
    with pytest.raises(DeadlineExceededError):fetch_homologs([Seed('1','a')],output_dir=tmp_path,client=Slow(),limits=RunLimits(max_seconds=.001))
    assert not (tmp_path/'manifest.json').exists()

def test_cancel_during_shared_wait_and_real_http_budget(tmp_path):
    import threading,time
    from phytominer import BioMartClient,ClientConfig,CancellationToken,CancelledError
    from phytominer.run import run_context
    from test_transport import server
    with server([200]) as (url,state),BioMartClient(ClientConfig(endpoint=url,requests_per_second=100)) as c:
        with pytest.raises(BudgetExceededError):
            with run_context(tmp_path,c,limits=RunLimits(max_requests=0)):
                with c._request('GET'):pass
        assert state['calls']==0
        token=CancellationToken();c._next_start=time.monotonic()+10
        timer=threading.Timer(.03,token.cancel);timer.start()
        try:
            with pytest.raises(CancelledError):
                with run_context(tmp_path,c,cancel=token):
                    with c._request('GET'):pass
        finally:timer.join()
        assert state['calls']==0 and c._active==0


def test_cancel_private_seed_diagnostics(tmp_path):
    import json
    from phytominer import CancellationToken,CancelledError
    token=CancellationToken();token.cancel()
    with pytest.raises(CancelledError):fetch_homologs([Seed('1','a')],output_dir=tmp_path,client=FixtureClient(),cancel=token)
    row=json.loads(next((tmp_path/'.runs').glob('*.json')).read_text())
    assert row['seed_outcomes'][0]['status']=='not_processed'

def test_cancel_during_stream_does_not_commit_raw_batch(tmp_path,monkeypatch):
    from contextlib import contextmanager
    from phytominer import BioMartClient,CancellationToken,CancelledError
    from phytominer.run import run_context
    from phytominer.storage import RequestCache
    token=CancellationToken()
    class Response:
        def iter_lines(self,**kwargs):
            yield 'group\ta\torg1\tb\torg2\tone-to-one'
            token.cancel()
            yield '[success]'
    @contextmanager
    def request(*args,**kwargs):yield Response()
    with BioMartClient() as c:
        monkeypatch.setattr(c,'metadata',lambda:{'fixture':'stream'})
        monkeypatch.setattr(c,'_request',request)
        cache=RequestCache(tmp_path/'requests')
        with pytest.raises(CancelledError):
            with run_context(tmp_path,c,cancel=token):cache.fetch(c,'orthologs',['a'],'1')
        assert not list((tmp_path/'requests').glob('*.parquet'))
