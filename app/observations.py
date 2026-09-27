"""Export dated facility observations separately from the catalog delivery."""

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
    write_payload(
        {
            "format": "nipkaart-offstreet-observations-1",
            "dataset": dataset.code,
            "selection": dataset.selection,
            "delivery_id": str(uuid4()),
            "fetched_at": timestamp(fetched_at),
            "max_age_seconds": max_age,
            "source_count": result.total_count,
            "records": result.records,
        },
        output,
    )
    return result.total_count
