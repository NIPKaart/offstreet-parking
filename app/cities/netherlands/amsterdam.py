"""Python script for Garages Amsterdam data."""

import math
from datetime import datetime, timedelta

from odp_amsterdam import Garage, ODPAmsterdam
from odp_amsterdam.exceptions import ODPAmsterdamError

from app.cities import City
from app.records import Collection, SourceError, capacity, timestamp, validate_record


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

    async def observe(self, fetched_at: datetime, max_age: int) -> Collection:
        """Collect point-in-time capacity and availability separately from metadata."""
        garages = await fetch_car_garages()
        records = [
            observation_record(garage, fetched_at, max_age) for garage in garages
        ]
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


def catalog_record(garage: Garage) -> dict[str, object]:
    """Map package metadata; occupancy never becomes accessible availability."""
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
        "short_stay": {
            "capacity": capacity(garage.short_capacity),
            "available": capacity(garage.free_space_short),
        },
        "long_stay": {
            "capacity": capacity(garage.long_capacity),
            "available": capacity(garage.free_space_long),
        }
        if garage.long_capacity is not None or garage.free_space_long is not None
        else None,
        "accessible": {"capacity": None, "available": None},
        "source_observed_at": timestamp(garage.updated_at),
    }
    validate_record(record)
    return record


def observation_record(
    garage: Garage, fetched_at: datetime, max_age: int
) -> dict[str, object]:
    """Keep dated source counts distinct from facility and accessible availability."""
    catalog = catalog_record(garage)
    observed_at = garage.updated_at
    valid_until = observed_at + timedelta(seconds=max_age) if observed_at else None
    status = "unavailable"
    if garage.state == "ok" and observed_at and observed_at <= fetched_at:
        status = "current" if valid_until > fetched_at else "stale"
    return {
        "external_id": garage.garage_id,
        "observed_at": timestamp(observed_at),
        "valid_until": timestamp(valid_until),
        "status": status,
        "source_state": garage.state,
        "short_stay": {
            "capacity": catalog["short_stay"]["capacity"],
            "available": capacity(garage.free_space_short)
            if status != "unavailable"
            else None,
        },
        "long_stay": {
            "capacity": capacity(garage.long_capacity),
            "available": capacity(garage.free_space_long)
            if status != "unavailable"
            else None,
        }
        if garage.long_capacity is not None or garage.free_space_long is not None
        else None,
        "accessible": {"capacity": None, "available": None},
    }
