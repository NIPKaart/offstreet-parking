"""Python script for Garages Amsterdam data."""

import math

from odp_amsterdam import Garage, ODPAmsterdam
from odp_amsterdam.exceptions import ODPAmsterdamError

from app.cities import City
from app.records import (
    Collection,
    SourceError,
    capacity,
    timestamp,
    validate_observation,
    validate_record,
)


class Municipality(City):
    """Manage the location data of Amsterdam."""

    def __init__(self) -> None:
        """Initialize the class."""
        super().__init__(
            name="Amsterdam",
            country="Netherlands",
        )

    async def async_get_locations(self) -> list[Garage]:
        """Get garage data from API.

        Returns
        -------
            list: List of garages.

        """
        async with ODPAmsterdam() as client:
            garages: list[Garage] = await client.all_garages()
            print(f"{self.name} - data has been retrieved")
            return garages

    async def collect(self) -> Collection:
        """Select car facilities from the complete, non-paginated source feed."""
        garages = await fetch_car_garages()
        records = [catalog_record(garage) for garage in garages]
        records.sort(key=lambda record: record["external_id"])
        return Collection(records, len(records), 1, complete=True)

    async def observe(self) -> Collection:
        """Collect dated free spaces separately from metadata."""
        garages = await fetch_car_garages()
        records = [observation_record(garage) for garage in garages]
        records.sort(key=lambda record: record["external_id"])
        return Collection(records, len(records), 1, complete=True)


async def fetch_car_garages() -> list[Garage]:
    """Keep provider access and parsing in the universal package."""
    try:
        async with ODPAmsterdam() as client:
            return await client.all_garages(vehicle="car")
    except (ODPAmsterdamError, TimeoutError, ValueError, TypeError, KeyError) as error:
        message = "Amsterdam source retrieval failed"
        raise SourceError(message) from error


def known_capacity(value: object) -> int | None:
    """Treat 0 as unknown: the feed sends 0/0 for errors and status-only P+R."""
    return capacity(value) or None


def available(free: object, total: object) -> int | None:
    """Free spaces without a known capacity are the same placeholder."""
    return capacity(free) if known_capacity(total) is not None else None


def catalog_record(garage: Garage) -> dict[str, object]:
    """Map what defines a facility; what changes during the day is an observation."""
    if (
        not math.isfinite(garage.latitude)
        or not math.isfinite(garage.longitude)
        or not 52 <= garage.latitude <= 53
        or not 4 <= garage.longitude <= 6
        or garage.vehicle != "car"
    ):
        message = "Invalid Amsterdam facility location or vehicle type"
        raise ValueError(message)
    record = {
        "external_id": garage.garage_id,
        "name": garage.garage_name,
        "source_name": garage.source_name or garage.garage_name,
        "facility_type": str(garage.category),
        "geometry": {
            "type": "Point",
            "coordinates": [garage.longitude, garage.latitude],
        },
        "accessible_capacity": None,
    }
    validate_record(record)
    return record


def observation_record(garage: Garage) -> dict[str, object]:
    """Pass the operator's current values on; core owns freshness policy.

    Capacity belongs here, not in the catalog: it changes during the day (seen at
    the ArenA garages on 2026-09-28). Long-stay counts (season tickets) are not
    delivered, because they say nothing to visitors.
    """
    record = {
        "external_id": garage.garage_id,
        "observed_at": timestamp(garage.updated_at),
        "source_state": garage.state,
        "status": garage.status.value if garage.status else None,
        "capacity": known_capacity(garage.short_capacity),
        "available": available(garage.free_space_short, garage.short_capacity),
        "accessible_available": None,
    }
    validate_observation(record)
    return record
