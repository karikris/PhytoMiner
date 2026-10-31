"""Phytozome XML retrieval and columnar analytics (Python 3.15+)."""
__version__ = "0.2.0"

lazy from .models import ClientConfig, Seed, PhytoMinerError, ValidationError, ServiceError, IncompleteDatasetError

__all__ = ['ClientConfig', 'Seed', 'PhytoMinerError', 'ValidationError', 'ServiceError', 'IncompleteDatasetError']
lazy from .biomart import BioMartClient
lazy from .dataset import HomologDataset
lazy from .workflows import fetch_homologs
__all__ += ['BioMartClient', 'HomologDataset', 'fetch_homologs']
