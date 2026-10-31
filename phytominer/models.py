"""Lightweight public configuration, identity and table contracts."""
from dataclasses import dataclass
from urllib.parse import urlparse

class PhytoMinerError(Exception):
    """Base error; failed requests are never represented as empty data."""

class ValidationError(PhytoMinerError, ValueError):
    pass

class ServiceError(PhytoMinerError):
    pass

class BatchSizeError(ServiceError):
    pass

class IncompleteDatasetError(PhytoMinerError):
    pass

@dataclass(frozen=True)
class Seed:
    organism_id: str
    gene_name: str
    label: str | None = None

    def __post_init__(self):
        for value in (self.organism_id, self.gene_name):
            if not isinstance(value, str) or not value.strip() or value != value.strip() or any(c in value for c in ',\t\r\n'):
                raise ValidationError('Identifiers must be nonempty, trimmed strings without delimiters')
        if self.label is not None and not isinstance(self.label, str):
            raise ValidationError('Seed label must be a string or None')

@dataclass(frozen=True)
class ClientConfig:
    endpoint: str = 'https://phytozome-next.jgi.doe.gov/biomart/martservice'
    dataset: str = 'phytozome'
    virtual_schema: str = 'zome_mart'
    max_workers: int = 2
    batch_size: int = 100
    requests_per_second: float = 2.0
    connect_timeout: float = 10.0
    read_timeout: float = 120.0
    attempts: int = 4

    def __post_init__(self):
        if not 1 <= self.max_workers <= 4 or not 1 <= self.batch_size <= 10000:
            raise ValidationError('workers must be 1..4 and batch_size 1..10000')
        if self.attempts < 1 or min(self.requests_per_second, self.connect_timeout, self.read_timeout) <= 0:
            raise ValidationError('Rate, timeouts and attempts must be positive')
        if urlparse(self.endpoint).scheme not in ('https', 'http'):
            raise ValidationError('An HTTP(S) endpoint is required')

ORTHOLOG_ATTRIBUTES = (
    'ortholog_group', 'ortholog__dm_gene_name', 'ortholog__dm_organism_name',
    'ortholog__dm_ortholog_gene_name', 'ortholog__dm_ortholog_organism_name',
    'ortholog__dm_relationship',
)
FEATURE_ATTRIBUTES = ('organism_id', 'organism_name', 'gene_name1', 'gene_id', 'transcript_name1', 'transcript_id')
TABLES = {
    'seeds': ('organism_id', 'gene_name', 'label'),
    'organisms': ('organism_id', 'organism_name'),
    'genes': ('organism_id', 'gene_name'),
    'relationships': ('source_organism_id', 'source_gene_name', 'target_organism_id', 'target_gene_name', 'ortholog_group', 'relationship'),
    'provenance': ('root_organism_id', 'root_gene_name', 'source_organism_id', 'source_gene_name', 'target_organism_id', 'target_gene_name', 'depth'),
    'features': ('organism_id', 'organism_name', 'gene_name', 'pac_gene_id', 'transcript_name', 'pac_transcript_id'),
}
