"""Validate the capacity supplied by a source without losing information."""

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


class SourceError(Exception):
    """A source request failed before a complete selection could be collected."""


def capacity(value: object) -> int | None:
    """Keep unknown separate from zero and reject lossy integer coercion."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise TypeError(value)
    try:
        number = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError(value) from error
    if not number.is_finite() or number < 0 or number != number.to_integral_value():
        raise ValueError(value)
    return int(number)


@dataclass
class Collection:
    """Normalized source claims accompanied by source completeness evidence."""

    records: list[dict[str, Any]]
    total_count: int
    pages_fetched: int
    complete: bool


def timestamp(value: datetime | None) -> str | None:
    """Keep absent source dates unknown and require an explicit timezone."""
    if value is None:
        return None
    if value.utcoffset() is None:
        message = "Source timestamp must include a timezone"
        raise ValueError(message)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


CATALOG_FIELDS = {
    "external_id",
    "name",
    "source_name",
    "facility_type",
    "geometry",
    "accessible_capacity",
}
OBSERVATION_FIELDS = {
    "external_id",
    "observed_at",
    "source_state",
    "status",
    "capacity",
    "available",
    "accessible_available",
}
OBSERVATION_STATUSES = {"counting", "open", "full", "closed", "malfunction"}


def validate_record(record: dict[str, Any]) -> None:
    """Validate the catalog-only wire format, including persisted retries."""
    if set(record) != CATALOG_FIELDS:
        message = "Unexpected catalog fields"
        raise ValueError(message)
    for field in ("external_id", "name", "source_name"):
        validate_text(record[field])
    if record["facility_type"] not in ("garage", "park_and_ride"):
        message = "Unsupported facility type"
        raise ValueError(message)
    validate_geometry(record["geometry"])
    validate_counts(record, ("accessible_capacity",))


def validate_observation(record: dict[str, Any]) -> None:
    """Validate one observation: source identity, optional time and counts."""
    if set(record) != OBSERVATION_FIELDS:
        message = "Unexpected observation fields"
        raise ValueError(message)
    validate_text(record["external_id"])
    if record["source_state"] is not None:
        validate_text(record["source_state"])
    if record["status"] is not None and record["status"] not in OBSERVATION_STATUSES:
        message = "Unsupported operator status"
        raise ValueError(message)
    if record["observed_at"] is not None:
        timestamp(datetime.fromisoformat(record["observed_at"]))
    validate_counts(record, ("capacity", "available", "accessible_available"))


def validate_text(value: object) -> None:
    """Require a nonempty source string."""
    if not isinstance(value, str) or not value.strip():
        message = "Source IDs, names and states must be nonempty strings"
        raise ValueError(message)


def validate_counts(record: dict[str, Any], fields: tuple[str, ...]) -> None:
    """Keep unknown (null) separate from zero; reject other values."""
    for field in fields:
        value = record[field]
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value < 0
        ):
            message = f"{field} must be a nonnegative integer or null"
            raise ValueError(message)


def validate_geometry(geometry: dict[str, Any]) -> None:
    """Require finite longitude/latitude coordinates in GeoJSON order."""
    if set(geometry) != {"type", "coordinates"} or geometry["type"] != "Point":
        message = "Expected a WGS84 Point"
        raise ValueError(message)
    coordinates = geometry["coordinates"]
    if (
        not isinstance(coordinates, list)
        or len(coordinates) != 2
        or any(
            type(value) not in (int, float) or not math.isfinite(value)
            for value in coordinates
        )
        or not -180 <= coordinates[0] <= 180
        or not -90 <= coordinates[1] <= 90
    ):
        message = "Invalid WGS84 coordinates"
        raise ValueError(message)
