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

    async def observe(self) -> Collection:
        """Retrieve dated observations for the same facility identities."""


@dataclass(frozen=True)
class SourceDescription:
    """How core recognises, attributes and approves a dataset (core ADR 0013)."""

    name: str
    publisher: str
    source_url: str
    licence: str | None
    terms_url: str
    attribution: str
    country: str
    subdivision: str
    municipality_scheme: str
    municipality_code: str
    municipality_name: str
    bounds: tuple[float, float, float, float]
    expected_interval_hours: int

    def as_dict(self) -> dict[str, object]:
        """Return the `source` block sent in every catalog delivery."""
        return {
            "name": self.name,
            "publisher": self.publisher,
            "source_url": self.source_url,
            "licence": self.licence,
            "terms_url": self.terms_url,
            "attribution": self.attribution,
            "area": {
                "country": self.country,
                "subdivision": self.subdivision,
                "municipality": {
                    "scheme": self.municipality_scheme,
                    "code": self.municipality_code,
                    "name": self.municipality_name,
                },
            },
            "bounds": list(self.bounds),
            "expected_interval_hours": self.expected_interval_hours,
        }


@dataclass(frozen=True)
class Dataset:
    """One delivery identity, selection and isolated collector state location."""

    code: str
    selection: str
    source: Callable[[], Source]
    description: SourceDescription


DATASETS = {
    "amsterdam": Dataset(
        code="nl-amsterdam-garages",
        selection="car-garages-and-pr",
        source=amsterdam.Municipality,
        # Licence and terms verified on data.overheid.nl on 2026-09-28.
        description=SourceDescription(
            name="Amsterdam parkeergarages en P+R",
            publisher="Gemeente Amsterdam",
            source_url="https://p-info.vorin-amsterdam.nl/v1/ParkingLocation.json",
            licence="CC-BY-4.0",
            terms_url="https://data.overheid.nl/dataset/9orkef6t-au29g",
            attribution=(
                "Gemeente Amsterdam; Actuele beschikbaarheid Parkeergarages; CC-BY 4.0."
            ),
            country="NL",
            subdivision="NL-NH",
            municipality_scheme="nl-cbs",
            municipality_code="GM0363",
            municipality_name="Amsterdam",
            bounds=(4.65, 52.2, 5.15, 52.5),
            expected_interval_hours=24,
        ),
    ),
}
