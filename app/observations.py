"""Export dated facility observations separately from the catalog delivery."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from app.datasets import DATASETS
from app.export import FETCH_TIMEOUT, MAX_RECORDS, write_payload
from app.records import timestamp, validate_group, validate_timestamp

if TYPE_CHECKING:
    from pathlib import Path

    from app.datasets import Dataset

FORMAT = "nipkaart-offstreet-observations-1"
STATUSES = ("current", "stale", "unavailable")
GROUP_FIELDS = ("capacity", "available")


def validate_observation(record: dict[str, Any]) -> None:
    """Validate one dated observation, including persisted retries."""
    if set(record) != {
        "external_id",
        "observed_at",
        "valid_until",
        "status",
        "source_state",
        "short_stay",
        "long_stay",
        "accessible",
    }:
        message = "Unexpected observation fields"
        raise ValueError(message)
    if not isinstance(record["external_id"], str) or not record["external_id"].strip():
        message = "Facility ID must be a nonempty source string"
        raise ValueError(message)
    if record["status"] not in STATUSES:
        message = "Unsupported observation status"
        raise ValueError(message)
    if record["source_state"] is not None and not isinstance(
        record["source_state"], str
    ):
        message = "Source state must be a string or null"
        raise ValueError(message)
    validate_observation_time(record)
    for field in ("short_stay", "long_stay", "accessible"):
        group = record[field]
        if field == "long_stay" and group is None:
            continue
        validate_group(group, GROUP_FIELDS)
        if record["status"] == "unavailable" and group["available"] is not None:
            message = "Unavailable observations cannot claim free spaces"
            raise ValueError(message)


def validate_observation_time(record: dict[str, Any]) -> None:
    """Require a dated, expiring measurement unless it is unavailable."""
    if (record["observed_at"] is None) != (record["valid_until"] is None):
        message = "Observation time and expiry must both be known or unknown"
        raise ValueError(message)
    if record["observed_at"] is None:
        if record["status"] != "unavailable":
            message = "Undated observations cannot be current or stale"
            raise ValueError(message)
    elif validate_timestamp(record["valid_until"]) <= validate_timestamp(
        record["observed_at"]
    ):
        message = "Observation expiry must follow its observation time"
        raise ValueError(message)


def validate_observations(payload: dict, dataset: Dataset) -> None:
    """Reject mismatched, incomplete or corrupt observation files before upload."""
    if (
        set(payload)
        != {
            "format",
            "dataset",
            "selection",
            "delivery_id",
            "fetched_at",
            "max_age_seconds",
            "source_count",
            "records",
        }
        or payload["format"] != FORMAT
        or payload["dataset"] != dataset.code
        or payload["selection"] != dataset.selection
    ):
        message = "Invalid observation envelope"
        raise ValueError(message)
    UUID(payload["delivery_id"])
    validate_timestamp(payload["fetched_at"])
    for field in ("max_age_seconds", "source_count"):
        value = payload[field]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            message = f"{field} must be a positive integer"
            raise ValueError(message)
    records = payload["records"]
    if (
        payload["source_count"] > MAX_RECORDS
        or not isinstance(records, list)
        or len(records) != payload["source_count"]
    ):
        message = "Invalid observation record count"
        raise ValueError(message)
    for record in records:
        validate_observation(record)
    if len({record["external_id"] for record in records}) != len(records):
        message = "Duplicate facility source IDs"
        raise ValueError(message)


def expired(payload: dict, now: datetime) -> bool:
    """Report whether a pending live delivery has aged out entirely."""
    fetched_at = validate_timestamp(payload["fetched_at"])
    return fetched_at + timedelta(seconds=payload["max_age_seconds"]) <= now


async def export_observations(city: str, output: Path, max_age: int = 300) -> int:
    """Fetch a complete selection; never publish or overwrite with partial results."""
    if isinstance(max_age, bool) or not isinstance(max_age, int) or max_age <= 0:
        message = "Maximum observation age must be a positive number of seconds"
        raise ValueError(message)
    dataset = DATASETS[city]
    fetched_at = datetime.now(UTC)
    async with asyncio.timeout(FETCH_TIMEOUT):
        result = await dataset.source().observe(fetched_at, max_age)
    if (
        not result.complete
        or result.pages_fetched < 1
        or not 0 < result.total_count <= MAX_RECORDS
        or len(result.records) != result.total_count
        or len({record["external_id"] for record in result.records})
        != result.total_count
    ):
        message = "Observation selection is empty, incomplete or contains duplicate IDs"
        raise ValueError(message)
    payload = {
        "format": FORMAT,
        "dataset": dataset.code,
        "selection": dataset.selection,
        "delivery_id": str(uuid4()),
        "fetched_at": timestamp(fetched_at),
        "max_age_seconds": max_age,
        "source_count": result.total_count,
        "records": result.records,
    }
    validate_observations(payload, dataset)
    write_payload(payload, output)
    return result.total_count
