"""Collect dated facility observations separately from the catalog delivery."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from app.datasets import DATASETS
from app.export import FETCH_TIMEOUT, MAX_RECORDS, write_payload
from app.records import timestamp

if TYPE_CHECKING:
    from pathlib import Path

FORMAT = "nipkaart-offstreet-observations-2"


async def collect_observations(city: str) -> dict:
    """Return one complete observation delivery or raise without partial data."""
    dataset = DATASETS[city]
    fetched_at = datetime.now(UTC)
    async with asyncio.timeout(FETCH_TIMEOUT):
        result = await dataset.source().observe()
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
    return {
        "format": FORMAT,
        "dataset": dataset.code,
        "selection": dataset.selection,
        "delivery_id": str(uuid4()),
        "fetched_at": timestamp(fetched_at),
        "source_count": result.total_count,
        "records": result.records,
    }


async def export_observations(city: str, output: Path) -> int:
    """Write one complete observation delivery to a local file."""
    payload = await collect_observations(city)
    write_payload(payload, output)
    return payload["source_count"]
