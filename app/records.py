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


def validate_record(record: dict[str, Any]) -> None:
    """Validate the catalog-only wire format, including persisted retries."""
    if set(record) != {
        "external_id",
        "name",
        "source_name",
        "facility_type",
        "geometry",
        "short_stay",
        "long_stay",
        "accessible",
        "source_observed_at",
    }:
        message = "Unexpected catalog fields"
        raise ValueError(message)
    for field in ("external_id", "name", "source_name"):
        if not isinstance(record[field], str) or not record[field].strip():
            message = "Facility ID and name must be nonempty source strings"
            raise ValueError(message)
    if record["facility_type"] not in ("garage", "park_and_ride"):
        message = "Unsupported facility type"
        raise ValueError(message)
    validate_geometry(record["geometry"])
    for field in ("short_stay", "long_stay", "accessible"):
        group = record[field]
        if field == "long_stay" and group is None:
            continue
        validate_group(group, ("capacity",))
    if record["source_observed_at"] is not None:
        validate_timestamp(record["source_observed_at"])


def validate_group(group: object, fields: tuple[str, ...]) -> None:
    """Require exactly the given counts, preserving unknown and zero."""
    if not isinstance(group, dict) or set(group) != set(fields):
        message = f"Parking groups must contain exactly {', '.join(fields)}"
        raise ValueError(message)
    for field in fields:
        value = group[field]
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value < 0
        ):
            message = "Parking counts must be nonnegative integers or null"
            raise ValueError(message)


def validate_timestamp(value: object) -> datetime:
    """Parse a persisted wire timestamp and require an explicit timezone."""
    if not isinstance(value, str):
        message = "Timestamps must be ISO 8601 strings"
        raise TypeError(message)
    parsed = datetime.fromisoformat(value)
    timestamp(parsed)
    return parsed


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
