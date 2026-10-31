import pytest
from phytominer.storage import write_batches
from phytominer.models import ServiceError
import pyarrow.parquet as pq

def test_atomic_failure_and_empty(tmp_path):
    path = tmp_path / 'data.parquet'
    def bad():
        yield [{'id':'001'}]
        raise ServiceError('truncated')
    with pytest.raises(ServiceError): write_batches(path, ('id',), bad())
    assert not path.exists()
    assert not list(tmp_path.glob('*.tmp'))
    assert write_batches(path, ('id',), [])['rows'] == 0
    assert pq.read_schema(path).names == ['id']

def test_roundtrip(tmp_path):
    path = tmp_path / 'data.parquet'
    result = write_batches(path, ('id','depth'), [[{'id':'001','depth':2},{'id':None,'depth':None}]])
    assert result['rows'] == 2
    assert pq.read_table(path).to_pylist() == [{'id':'001','depth':2},{'id':None,'depth':None}]
from phytominer.storage import RequestCache
from phytominer.biomart import BioMartClient
from phytominer.models import BatchSizeError

class FakeClient(BioMartClient):
    @property
    def metadata_fingerprint(self): return 'test-schema'
    def query(self, page, genes=(), organism_id=None):
        self.calls = getattr(self, 'calls', 0) + 1
        yield [dict(zip(self.build_query(page,genes,organism_id)[1], ['167','org','001','0001','001.1','0002']))]

def test_cache_resume_corruption_and_inputs(tmp_path):
    cache = RequestCache(tmp_path); client = FakeClient()
    paths = cache.fetch(client,'features',['001'],'167')
    assert cache.fetch(client,'features',['001'],'167') == paths
    assert client.calls == 1
    paths[0].write_bytes(b'corrupt')
    cache.fetch(client,'features',['001'],'167')
    assert client.calls == 2
    cache.fetch(client,'features',['002'],'167')
    assert client.calls == 3
    cache.fetch(client,'features',['002'],'167',refresh=True)
    assert client.calls == 4

def test_split_and_failed_batch(tmp_path):
    class Split(FakeClient):
        def query(self,page,genes=(),organism_id=None):
            if len(genes)>1: raise BatchSizeError('too large')
            yield from super().query(page,genes,organism_id)
    c=Split(); cache=RequestCache(tmp_path)
    paths=cache.fetch(c,'features',['a','b'],'167')
    assert len(paths)==2
    cache.fetch(c,'features',['a','b'],'167')
    assert c.calls==2
    class Fail(FakeClient):
        def query(self,*args,**kwargs):
            raise ServiceError('bad'); yield
    with pytest.raises(ServiceError): cache.fetch(Fail(),'features',['failed'],'167')
