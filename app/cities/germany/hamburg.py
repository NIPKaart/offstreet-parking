"""Deliver Hamburg's complete P+R selection through the offstreet contracts."""

from hamburg import Collection as SourceCollection
from hamburg import ParkAndRide, UDPHamburg
from hamburg.exceptions import UDPHamburgError

from app.records import (
    Collection,
    SourceError,
    capacity,
    timestamp,
    validate_observation,
    validate_record,
)


class Municipality:
    """Keep source retrieval in the package; map only NIPKaart delivery claims."""

    async def collect(self) -> Collection:
        """Collect catalog metadata without live counts."""
        result = await fetch_collection()
        records = [catalog_record(record) for record in result.records]
        records.sort(key=lambda record: record["external_id"])
        return Collection(
            records, result.total_count, result.pages_fetched, result.complete
        )

    async def observe(self) -> Collection:
        """Preserve original measurement times, including missing and stale values."""
        result = await fetch_collection()
        records = [observation_record(record) for record in result.records]
        records.sort(key=lambda record: record["external_id"])
        return Collection(
            records, result.total_count, result.pages_fetched, result.complete
        )


async def fetch_collection() -> SourceCollection[ParkAndRide]:
    """Reject failed or partial collection before the exporter sees any records."""
    try:
        async with UDPHamburg() as client:
            return await client.park_and_ride_collection(max_records=10000)
    except (UDPHamburgError, TimeoutError, ValueError, TypeError, KeyError) as error:
        message = "Hamburg source retrieval failed"
        raise SourceError(message) from error


def catalog_record(record: ParkAndRide) -> dict[str, object]:
    """All records in the P+R source are P+R facilities, even its parking garages."""
    data = {
        "external_id": record.spot_id,
        "name": record.name,
        "source_name": record.name,
        "facility_type": "park_and_ride",
        "geometry": {
            "type": "Point",
            "coordinates": [record.longitude, record.latitude],
        },
    }
    validate_record(data)
    return data


def observation_record(record: ParkAndRide) -> dict[str, object]:
    """Deliver general occupancy; no accessible-space availability is inferred."""
    total = capacity(record.capacity)
    free = capacity(record.free_space)
    data = {
        "external_id": record.spot_id,
        "observed_at": timestamp(record.updated_at),
        "source_state": "ok",
        "status": "counting" if total is not None and free is not None else None,
        "capacity": total,
        "available": free,
    }
    validate_observation(data)
    return data
