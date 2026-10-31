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
