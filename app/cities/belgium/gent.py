"""Select Gent garages, parking lots and P+R from the complete live source feed."""

from odp_gent import Collection as SourceCollection
from odp_gent import ODPGent, ParkingFacility
from odp_gent.exceptions import ODPGentError

from app.records import (
    Collection,
    SourceError,
    capacity,
    timestamp,
    validate_observation,
    validate_record,
)

# Gent's type field labels some verified garages as parking grounds. These
# original IDs have explicit facility evidence in docs/sources.md.
FACILITY_TYPES = {
    "https://be.parkindigo.com/nl/car-park/parking-dok-noord": "garage",
    (
        "https://stad.gent/nl/mobiliteit-openbare-werken/parkeren/"
        "parkings-gent/parking-tolhuis"
    ): "garage",
    (
        "https://stad.gent/nl/mobiliteit-openbare-werken/parkeren/"
        "parkings-gent/parking-ledeberg"
    ): "park_and_ride",
    (
        "https://stad.gent/nl/mobiliteit-openbare-werken/parkeren/"
        "parkings-gent/parking-het-getouw"
    ): "garage",
    (
        "https://stad.gent/nl/mobiliteit-openbare-werken/parkeren/"
        "park-and-ride-pr/pr-loopexpo"
    ): "park_and_ride",
}


class Municipality:
    """Keep source HTTP/parsing in the package and selection in the collector."""

    async def collect(self) -> Collection:
        """Deliver facility metadata without counts or fabricated identities."""
        result = await fetch_collection()
        records = [catalog_record(row) for row in selected(result)]
        return Collection(records, len(records), result.pages_fetched, result.complete)

    async def observe(self) -> Collection:
        """Deliver the same selection and preserve original measurement times."""
        result = await fetch_collection()
        records = [observation_record(row) for row in selected(result)]
        return Collection(records, len(records), result.pages_fetched, result.complete)


async def fetch_collection() -> SourceCollection:
    """Reject partial source data before filtering could mask its missing rows."""
    try:
        async with ODPGent() as client:
            result = await client.parking_collection(max_records=10000)
        if (
            not result.complete
            or result.pages_fetched < 1
            or len(result.records) != result.total_count
            or len({row.facility_id for row in result.records}) != result.total_count
        ):
            message = "Incomplete Gent source selection"
            raise SourceError(message)
    except (ODPGentError, TimeoutError, ValueError, TypeError, KeyError) as error:
        message = "Gent source retrieval failed"
        raise SourceError(message) from error
    return result


def selected(result: SourceCollection) -> list[ParkingFacility]:
    """Apply the same deterministic facility selection to both streams."""
    return sorted(
        result.records,
        key=lambda row: row.facility_id,
    )


def facility_type(row: ParkingFacility) -> str:
    """Use reviewed ID overrides where the generic source type is misleading."""
    if row.facility_id in FACILITY_TYPES:
        return FACILITY_TYPES[row.facility_id]
    if row.parking_type == "carPark":
        return "garage"
    if row.parking_type == "offStreetParkingGround":
        return "parking_lot"
    message = "Unknown Gent parking type"
    raise ValueError(message)


def catalog_record(row: ParkingFacility) -> dict[str, object]:
    """Coordinates are location claims, never the facility identity."""
    record = {
        "external_id": row.facility_id,
        "name": row.name,
        "source_name": row.name,
        "facility_type": facility_type(row),
        "geometry": {
            "type": "Point",
            "coordinates": [row.longitude, row.latitude],
        },
    }
    validate_record(record)
    return record


def observation_record(row: ParkingFacility) -> dict[str, object]:
    """Map source opening flags and general counts after successful source retrieval."""
    total, free = capacity(row.total_capacity), capacity(row.free_space)
    status = None
    if row.temporary_closed is True or row.is_open is False:
        status = "closed"
    elif total is not None and free is not None:
        status = "counting"
    elif row.is_open is True:
        status = "open"
    record = {
        "external_id": row.facility_id,
        "observed_at": timestamp(row.updated_at),
        "source_state": "ok",
        "status": status,
        "capacity": total,
        "available": free,
    }
    validate_observation(record)
    return record
