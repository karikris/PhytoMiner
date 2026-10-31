"""Transactional, bounded Parquet writes and validated content-addressed cache."""
import hashlib
import json
import os
import tempfile
from pathlib import Path
lazy import pyarrow as pa
lazy import pyarrow.parquet as pq
from .models import ServiceError

SCHEMA_VERSION = 1

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def checksum(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()

def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(value, handle, sort_keys=True, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)

def arrow_schema(columns):
    return pa.schema([(name, pa.int64() if name == 'depth' else pa.string()) for name in columns])

def write_batches(path, columns, batches):
    """Only publish after the producer validates its completion marker."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, suffix='.parquet.tmp')
    os.close(fd)
    schema = arrow_schema(columns)
    rows = 0
    try:
        with pq.ParquetWriter(temp, schema, compression='zstd') as writer:
            for batch in batches:
                if batch:
                    table = pa.Table.from_pylist(batch, schema=schema)
                    writer.write_table(table, row_group_size=65536)
                    rows += len(batch)
        os.replace(temp, path)
        return {'rows': rows, 'sha256': checksum(path), 'columns': list(columns)}
    finally:
        Path(temp).unlink(missing_ok=True)

class RequestCache:
    def __init__(self, root, refresh=False):
        pa.schema([])  # Fail before worker dispatch if the columnar runtime is unavailable.
        pq.ParquetWriter
        self.refresh = refresh
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def metadata(self, client, refresh=False):
        identity = {'endpoint': client.config.endpoint, 'dataset': client.config.dataset,
                    'schema': client.config.virtual_schema}
        path = self.root / 'metadata.json'
        if not refresh and path.exists():
            try:
                saved = json.loads(path.read_text())
                if saved['identity'] == identity and saved['checksum'] == digest(saved['data']):
                    client.validate_metadata(saved['data'])
                    client._metadata = saved['data']
            except (ValueError, KeyError, ServiceError):
                pass
        if refresh:
            client._metadata = None
        data = client.metadata()
        atomic_json(path, {'identity': identity, 'checksum': digest(data), 'data': data})
        return client.metadata_fingerprint

    def valid(self, record, columns):
        try:
            for part in record['parts']:
                path = self.root / part['file']
                if path.parent != self.root or checksum(path) != part['sha256']:
                    return False
                file = pq.ParquetFile(path)
                if file.schema_arrow != arrow_schema(columns) or file.metadata.num_rows != part['rows']:
                    return False
            return record['status'] == 'complete'
        except (OSError, ValueError, KeyError, pa.ArrowException):
            return False

    def fetch(self, client, page, genes=(), organism_id=None, refresh=False):
        from .models import BatchSizeError
        refresh = refresh or self.refresh
        xml, columns = client.build_query(page, genes, organism_id)
        key = digest({'xml': xml, 'endpoint': client.config.endpoint,
                      'metadata': client.metadata_fingerprint, 'schema_version': SCHEMA_VERSION})
        manifest = self.root / (key + '.json')
        if manifest.exists() and not refresh:
            try:
                record = json.loads(manifest.read_text())
                if self.valid(record, columns):
                    return [self.root / p['file'] for p in record['parts']]
            except (ValueError, KeyError):
                pass
        path = self.root / (key + '.parquet')
        try:
            result = write_batches(path, columns, client.query(page, genes, organism_id))
            parts = [{'file': path.name, **result}]
        except BatchSizeError:
            if len(genes) <= 1:
                atomic_json(manifest, {'status': 'failed', 'query_hash': key})
                raise
            middle = len(genes) // 2
            paths = [*self.fetch(client, page, genes[:middle], organism_id, refresh),
                     *self.fetch(client, page, genes[middle:], organism_id, refresh)]
            parts = [{'file': p.name, 'rows': pq.ParquetFile(p).metadata.num_rows,
                      'sha256': checksum(p), 'columns': list(columns)} for p in paths]
        except Exception:
            atomic_json(manifest, {'status': 'failed', 'query_hash': key})
            raise
        atomic_json(manifest, {'status': 'complete', 'query_hash': key, 'parts': parts})
        return [self.root / part['file'] for part in parts]
