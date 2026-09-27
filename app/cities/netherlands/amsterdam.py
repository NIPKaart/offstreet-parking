"""Python script for Garages Amsterdam data."""

import math

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
        try:
            async with ODPAmsterdam() as client:
                garages = await client.all_garages(vehicle="car")
        except (
            ODPAmsterdamError,
            TimeoutError,
            ValueError,
            TypeError,
            KeyError,
        ) as error:
            message = "Amsterdam catalog retrieval failed"
            raise SourceError(message) from error
        records = [catalog_record(garage) for garage in garages]
        records.sort(key=lambda record: record["external_id"])
        return Collection(records, len(records), 1, complete=True)


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
        "facility_type": str(garage.category),
        "geometry": {
            "type": "Point",
            "coordinates": [garage.longitude, garage.latitude],
        },
        "capacity": {
            "general_short_stay": capacity(garage.short_capacity),
            "general_long_stay": capacity(garage.long_capacity),
            "accessible": None,
        },
        "metadata_updated_at": None,
        "source_observed_at": timestamp(garage.updated_at),
    }
    validate_record(record)
    return record
