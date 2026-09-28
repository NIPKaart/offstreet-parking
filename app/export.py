"""Fetch one live source and atomically write the candidate catalog contract."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from app.datasets import DATASETS
from app.records import validate_record

if TYPE_CHECKING:
    from app.datasets import Dataset
    from app.records import Collection

FORMAT = "nipkaart-offstreet-catalog-3"
MAX_RECORDS = 10000
MAX_BYTES = 32 * 1024 * 1024
FETCH_TIMEOUT = 180


def validate_payload(payload: dict, dataset: Dataset) -> None:
    """Reject mismatched, incomplete or corrupt files before creating an object."""
    if (
        payload["format"] != FORMAT
        or payload["dataset"] != dataset.code
        or payload.get("source") != dataset.description.as_dict()
        or payload["selection"] != dataset.selection
        or payload["complete"] is not True
    ):
        message = "Invalid or incomplete catalog envelope"
        raise ValueError(message)
    count = payload["source_count"]
    if (
        isinstance(count, bool)
        or not isinstance(count, int)
        or not 0 < count <= MAX_RECORDS
        or not isinstance(payload["records"], list)
        or len(payload["records"]) != count
    ):
        message = "Invalid catalog record count"
        raise ValueError(message)
    UUID(payload["delivery_id"])
    if datetime.fromisoformat(payload["retrieved_at"]).utcoffset() is None:
        message = "Retrieval start must include a timezone"
        raise ValueError(message)
    west, south, east, north = dataset.description.bounds
    for record in payload["records"]:
        validate_record(record)
        longitude, latitude = record["geometry"]["coordinates"]
        if not (west <= longitude <= east and south <= latitude <= north):
            message = "Facility lies outside the dataset bounds"
            raise ValueError(message)
    if (
        len({record["external_id"] for record in payload["records"]})
        != payload["source_count"]
    ):
        message = "Duplicate facility source IDs"
        raise ValueError(message)


def write_records(
    dataset: Dataset,
    result: Collection,
    output: Path,
    retrieved_at: datetime,
) -> int:
    """Keep the last valid file intact unless the entire delivery is valid."""
    if (
        not result.complete
        or not 0 < result.total_count <= MAX_RECORDS
        or result.pages_fetched < 1
    ):
        msg = "Source delivery is empty, incomplete or exceeds the pilot limit"
        raise ValueError(msg)
    records = result.records
    if (
        len(records) != result.total_count
        or len({record["external_id"] for record in records}) != result.total_count
    ):
        msg = "Source count does not match unique records"
        raise ValueError(msg)
    if retrieved_at.tzinfo is None:
        msg = "Retrieval start must include a timezone"
        raise ValueError(msg)
    payload = {
        "format": FORMAT,
        "dataset": dataset.code,
        "delivery_id": str(uuid4()),
        "retrieved_at": retrieved_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "selection": dataset.selection,
        "source": dataset.description.as_dict(),
        "complete": True,
        "source_count": result.total_count,
        "records": records,
    }
    validate_payload(payload, dataset)
    write_payload(payload, output)
    return len(records)


def encode(payload: dict) -> bytes:
    """Serialize one bounded delivery exactly as it is written and uploaded."""
    data = (json.dumps(payload, ensure_ascii=False, allow_nan=False) + "\n").encode()
    if len(data) > MAX_BYTES:
        msg = "Delivery exceeds the 32 MiB pilot limit"
        raise ValueError(msg)
    return data


def write_payload(payload: dict, output: Path) -> None:
    """Complete a local file atomically so a failure keeps the previous one."""
    data = encode(payload)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=output.parent,
            prefix=".parking-",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


async def export_dataset(city: str, output: Path) -> int:
    """Bound source collection and write only its verified complete result."""
    dataset = DATASETS[city]
    retrieved_at = datetime.now(UTC)
    async with asyncio.timeout(FETCH_TIMEOUT):
        result = await dataset.source().collect()
    return write_records(dataset, result, output, retrieved_at)
