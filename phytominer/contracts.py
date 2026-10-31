"""Static transport and input contracts, without analytics imports."""

from collections.abc import Iterable, Iterator, Mapping
from typing import Any, Protocol
from .models import ClientConfig, Seed

type SeedInput = Seed | Mapping[str, str | None]
type Seeds = Iterable[SeedInput]
type Targets = Iterable[str] | None


class ClientProtocol(Protocol):
    config: ClientConfig
    metrics: list[dict[str, Any]]

    def metadata(self) -> dict[str, str]: ...
    def query(
        self, page: str, genes: Iterable[str] = (), organism_id: str | None = None
    ) -> Iterator[list[dict[str, str | None]]]: ...
    def close(self) -> None: ...
