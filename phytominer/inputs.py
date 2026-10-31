"""Canonical scientific input identities."""

from .storage import digest
from .models import ValidationError, Seed

PROCESSING_CONTRACT_VERSION = 3


def _result_identity(kind, **inputs):
    return digest(
        {
            "kind": kind,
            "processing_contract_version": PROCESSING_CONTRACT_VERSION,
            **inputs,
        }
    )


def _target_identity(targets):
    return (
        {"mode": "all"}
        if targets is None
        else {"mode": "selected", "organisms": list(targets)}
    )


def _normalize_targets(targets):
    if targets is None:
        return None
    if isinstance(targets, (str, bytes)):
        raise ValidationError(
            "Target organisms must be an iterable of nonempty strings"
        )
    try:
        values = tuple(targets)
    except TypeError as exc:
        raise ValidationError(
            "Target organisms must be an iterable of nonempty strings"
        ) from exc
    if any(
        not isinstance(value, str) or not value.strip() or value != value.strip()
        for value in values
    ):
        raise ValidationError("Target organisms must be nonempty, trimmed strings")
    return tuple(sorted(set(values)))


def normalize_seeds(values) -> list[Seed]:
    from .models import Seed

    result = []
    for value in values:
        if isinstance(value, Seed):
            result.append(value)
            continue
        try:
            fields = dict(value)
            if set(fields) - {"organism_id", "gene_name", "label"}:
                raise ValueError("Unknown seed fields")
            organism, gene = fields.get("organism_id"), fields.get("gene_name")
            if not isinstance(organism, str) or not isinstance(gene, str):
                raise ValueError("Seed organism_id and gene_name must be strings")
            result.append(Seed(organism, gene, fields.get("label")))
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"Invalid seed: {exc}") from exc
    return result
