"""Optional invocation controls; defaults preserve unlimited local workflows."""

from dataclasses import dataclass
from math import isfinite
from .models import ValidationError


@dataclass(frozen=True)
class RunLimits:
    max_genes: int | None = None
    max_requests: int | None = None
    max_seconds: float | None = None
    max_output_bytes: int | None = None

    def __post_init__(self):
        for name in ("max_genes", "max_requests", "max_output_bytes"):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ValidationError(f"{name} must be a nonnegative integer")
        if self.max_seconds is not None and (
            not isfinite(self.max_seconds) or self.max_seconds <= 0
        ):
            raise ValidationError("max_seconds must be finite and positive")
