"""Collect dated facility observations separately from the catalog delivery."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from app.datasets import DATASETS
from app.export import FETCH_TIMEOUT, MAX_RECORDS, validate_payload, write_payload
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
    payload = {
        "format": FORMAT,
        "dataset": dataset.code,
        "selection": dataset.selection,
        "delivery_id": str(uuid4()),
        "fetched_at": timestamp(fetched_at),
        "source_count": result.total_count,
        "records": result.records,
    }
    if result.identity_records is not None:
        validate_payload(
            {
                "format": "nipkaart-offstreet-catalog-3",
                "dataset": dataset.code,
                "selection": dataset.selection,
                "source": dataset.description.as_dict(),
                "delivery_id": payload["delivery_id"],
                "retrieved_at": payload["fetched_at"],
                "complete": True,
                "source_count": result.total_count,
                "records": result.identity_records,
            },
            dataset,
        )
        if {record["external_id"] for record in result.identity_records} != {
            record["external_id"] for record in result.records
        }:
            message = (
                "Identity claims and observations belong to different source snapshots"
            )
            raise ValueError(message)
        payload["format"] = "nipkaart-offstreet-observations-3"
        payload["identity_records"] = result.identity_records
    return payload


async def export_observations(city: str, output: Path) -> int:
    """Write one complete observation delivery to a local file."""
    payload = await collect_observations(city)
    write_payload(payload, output)
    return payload["source_count"]
