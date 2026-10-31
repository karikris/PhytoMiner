"""Versioned manifests over compact canonical Parquet tables."""
import json
import os
import uuid
from pathlib import Path
from datetime import datetime, timezone
lazy import polars as pl
lazy import pyarrow.parquet as pq
from .storage import atomic_json, checksum, SCHEMA_VERSION
from .models import TABLES, IncompleteDatasetError, ValidationError

class DatasetWriter:
    def __init__(self, root, identity):
        self.root = Path(root)
        self.generation = uuid.uuid4().hex
        self.directory = self.root / 'tables' / self.generation
        self.directory.mkdir(parents=True, exist_ok=True)
        self.manifest = {'schema_version': SCHEMA_VERSION, 'status': 'incomplete',
            'identity': identity, 'tables': {}, 'created_at': datetime.now(timezone.utc).isoformat()}
        atomic_json(self.root / 'manifest.json', self.manifest)

    def write(self, name, frame):
        columns = TABLES.get(name)
        if columns is not None:
            frame = frame.select([pl.col(c).cast(pl.Int64 if c == 'depth' else pl.String, strict=True) for c in columns])
        path = self.directory / (name + '.parquet')
        temp = path.with_suffix('.parquet.tmp')
        try:
            frame.sink_parquet(temp, compression='zstd', row_group_size=65536)
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)
        self.manifest['tables'][name] = {'file': path.relative_to(self.root).as_posix(),
            'sha256': checksum(path), 'rows': pq.ParquetFile(path).metadata.num_rows}

    def finish(self, **details):
        self.manifest.update(details, status='complete')
        atomic_json(self.root / 'manifest.json', self.manifest)
        return HomologDataset(self.root)

class HomologDataset:
    def __init__(self, root):
        self.root = Path(root)
        try:
            self.manifest = json.loads((self.root / 'manifest.json').read_text())
            if self.manifest['status'] != 'complete' or self.manifest['schema_version'] != SCHEMA_VERSION:
                raise ValueError('Incomplete or unsupported manifest')
            for record in self.manifest['tables'].values():
                path = (self.root / record['file']).resolve()
                if not path.is_relative_to(self.root.resolve()) or checksum(path) != record['sha256']:
                    raise ValueError('Invalid dataset file')
                if pq.ParquetFile(path).metadata.num_rows != record['rows']:
                    raise ValueError('Invalid dataset row count')
        except (OSError, ValueError, KeyError) as exc:
            raise IncompleteDatasetError(f'Cannot open dataset: {exc}') from exc

    def scan(self, table):
        if table not in self.manifest['tables']:
            raise ValidationError(f'Unknown table: {table}')
        return pl.scan_parquet(self.root / self.manifest['tables'][table]['file'])
