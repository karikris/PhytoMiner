"""Canonical scientific input identities."""
from .storage import digest
from .models import ValidationError

PROCESSING_CONTRACT_VERSION = 2


def _result_identity(kind, **inputs):
    return digest({'kind': kind, 'processing_contract_version': PROCESSING_CONTRACT_VERSION, **inputs})


def _target_identity(targets):
    return {'mode': 'all'} if targets is None else {'mode': 'selected', 'organisms': list(targets)}


def _normalize_targets(targets):
    if targets is None:
        return None
    if isinstance(targets, (str, bytes)):
        raise ValidationError('Target organisms must be an iterable of nonempty strings')
    try:
        values = tuple(targets)
    except TypeError as exc:
        raise ValidationError('Target organisms must be an iterable of nonempty strings') from exc
    if any(not isinstance(value, str) or not value.strip() or value != value.strip() for value in values):
        raise ValidationError('Target organisms must be nonempty, trimmed strings')
    return tuple(sorted(set(values)))
