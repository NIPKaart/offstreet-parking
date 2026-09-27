"""Register deliverable datasets separately from source-specific HTTP clients."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from app.cities.netherlands import amsterdam

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.records import Collection


class Source(Protocol):
    """Produce normalized records and explicit evidence of a complete selection."""

    async def collect(self) -> Collection:
        """Retrieve a complete selection or raise without delivering partial data."""


@dataclass(frozen=True)
class Dataset:
    """One delivery identity, selection and isolated collector state location."""

    code: str
    selection: str
    source: Callable[[], Source]


DATASETS = {
    "amsterdam": Dataset(
        code="nl-amsterdam-garages",
        selection="car-garages-and-pr",
        source=amsterdam.Municipality,
    ),
}
