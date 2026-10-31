"""Versioned manifests over compact canonical Parquet tables."""

import json
import os
import uuid
from copy import deepcopy
from pathlib import Path
from datetime import datetime, timezone
lazy import duckdb
lazy import polars as pl
lazy import pyarrow.parquet as pq
lazy import pyarrow as pa
from .storage import atomic_json, checksum
from .models import TABLES, TABLES_V1, IncompleteDatasetError, ValidationError

DATASET_SCHEMA_VERSION = 2


def _validate_manifest(root, manifest):
    """Validate an unpublished candidate or an existing published generation."""
    root = Path(root)
    try:
        if manifest["status"] != "complete" or manifest["schema_version"] not in (
            1,
            DATASET_SCHEMA_VERSION,
        ):
            raise ValueError("Incomplete or unsupported manifest")
        schemas = TABLES_V1 if manifest["schema_version"] == 1 else TABLES
        for name, record in manifest["tables"].items():
            path = (root / record["file"]).resolve()
            if (
                not path.is_relative_to(root.resolve())
                or checksum(path) != record["sha256"]
            ):
                raise ValueError("Invalid dataset file")
            with pq.ParquetFile(path) as file:
                if name in schemas:
                    if file.schema_arrow.names != list(schemas[name]):
                        raise ValueError("Invalid dataset table schema")
                    for field in file.schema_arrow:
                        valid_type = (
                            pa.types.is_int64(field.type)
                            if field.name == "depth"
                            else (
                                pa.types.is_string(field.type)
                                or pa.types.is_large_string(field.type)
                            )
                        )
                        if not valid_type:
                            raise ValueError("Invalid dataset column type")
                if file.metadata.num_rows != record["rows"]:
                    raise ValueError("Invalid dataset row count")
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        pa.ArrowException,
    ) as exc:
        raise IncompleteDatasetError(f"Cannot open dataset: {exc}") from exc


class DatasetWriter:
    def __init__(self, root, identity):
        self.root = Path(root)
        self.generation = uuid.uuid4().hex
        self.directory = self.root / "tables" / self.generation
        self.directory.mkdir(parents=True, exist_ok=True)
        from . import __version__

        self.manifest = {
            "package_version": __version__,
            "schema_version": DATASET_SCHEMA_VERSION,
            "status": "incomplete",
            "identity": identity,
            "tables": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        atomic_json(self.directory / "manifest.json", self.manifest)

    def write(self, name, frame):
        columns = TABLES.get(name)
        if columns is not None:
            frame = frame.select(
                [
                    pl.col(c).cast(pl.Int64 if c == "depth" else pl.String, strict=True)
                    for c in columns
                ]
            )
        path = self.directory / (name + ".parquet")
        temp = path.with_suffix(".parquet.tmp")
        try:
            frame.sink_parquet(temp, compression="zstd", row_group_size=65536)
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)
        self.manifest["tables"][name] = {
            "file": path.relative_to(self.root).as_posix(),
            "sha256": checksum(path),
            "rows": pq.ParquetFile(path).metadata.num_rows,
        }
        atomic_json(self.directory / "manifest.json", self.manifest)

    def finish(self, **details):
        candidate = {**self.manifest, **details, "status": "complete"}
        pinned = HomologDataset._from_manifest(self.root, candidate)
        atomic_json(self.directory / "manifest.json", pinned.manifest)
        atomic_json(self.root / "manifest.json", pinned.manifest)
        self.manifest = deepcopy(pinned.manifest)
        return pinned


class HomologDataset:
    def __init__(self, root):
        self.root = Path(root)
        try:
            manifest = json.loads((self.root / "manifest.json").read_text())
        except (OSError, ValueError) as exc:
            raise IncompleteDatasetError(f"Cannot open dataset: {exc}") from exc
        _validate_manifest(self.root, manifest)
        self.manifest = deepcopy(manifest)

    @classmethod
    def _from_manifest(cls, root, manifest):
        _validate_manifest(root, manifest)
        result = cls.__new__(cls)
        result.root = Path(root)
        result.manifest = deepcopy(manifest)
        return result

    def scan(self, table):
        if table not in self.manifest["tables"]:
            raise ValidationError(f"Unknown table: {table}")
        return pl.scan_parquet(self.root / self.manifest["tables"][table]["file"])

    def summary(self):
        """Count reported edges and distinct genes without label/transcript fanout."""
        return (
            self.scan("relationships")
            .group_by("target_organism_id", "target_organism_name", "relationship")
            .agg(
                pl.col("target_gene_name").n_unique().alias("homolog_genes"),
                pl.struct("source_organism_id", "source_gene_name")
                .n_unique()
                .alias("query_genes"),
                pl.len().alias("reported_edges"),
            )
            .sort("target_organism_id", "target_organism_name", "relationship")
        )

    def connect(self, database=":memory:"):
        """Return a caller-owned DuckDB connection with Parquet-backed views."""
        connection = duckdb.connect(str(database))
        try:
            for name, record in self.manifest["tables"].items():
                connection.read_parquet(
                    str((self.root / record["file"]).resolve())
                ).create_view(name, replace=True)
        except Exception:
            connection.close()
            raise
        return connection
