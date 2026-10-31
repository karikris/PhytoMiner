"""Phytozome XML retrieval and columnar analytics (Python 3.15+)."""

__version__ = "1.0.1"
lazy from .models import (
    ClientConfig,
    Seed,
    PhytoMinerError,
    ValidationError,
    ServiceError,
    IncompleteDatasetError,
)
lazy from .biomart import BioMartClient
lazy from .dataset import HomologDataset
lazy from .workflows import fetch_homologs
lazy from .workflows import fetch_features, join_annotations
lazy from .models import (
    AnnotationError,
    CancelledError,
    DeadlineExceededError,
    BudgetExceededError,
)


lazy from .limits import RunLimits, CancellationToken

lazy from .maintenance import inspect_cache, plan_cleanup, execute_cleanup

__all__ = [
    "ClientConfig",
    "Seed",
    "PhytoMinerError",
    "ValidationError",
    "ServiceError",
    "IncompleteDatasetError",
]
__all__ += ["BioMartClient", "HomologDataset", "fetch_homologs"]

__all__ += ["fetch_features", "join_annotations"]

__all__ += [
    "AnnotationError",
    "CancelledError",
    "DeadlineExceededError",
    "BudgetExceededError",
]

__all__ += ["RunLimits"]

__all__ += ["CancellationToken"]

__all__ += ["inspect_cache", "plan_cleanup", "execute_cleanup"]
