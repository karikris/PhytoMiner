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
