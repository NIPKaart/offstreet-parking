"""Exercise NIPKaart catalog mapping without duplicating provider parsing."""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

from odp_amsterdam import Garage
from odp_amsterdam.exceptions import ODPAmsterdamError
from odp_amsterdam.models import GarageCategory, VehicleType

from app.cities.netherlands.amsterdam import Municipality, catalog_record
from app.datasets import DATASETS
from app.export import export_dataset, write_records
from app.records import Collection, SourceError, validate_record


def garage(**changes: object) -> Garage:
    """Build a small universal-package object at the adapter boundary."""
    return replace(
        Garage(
            garage_id="source-original-ID",
            garage_name="Example P+R",
            source_name="PR-123_ Example P+R (opendata)",
            vehicle=VehicleType.CAR,
            category=GarageCategory.PARK_AND_RIDE,
            state="ok",
            free_space_short=27,
            free_space_long=None,
            short_capacity=120,
            long_capacity=None,
            availability_pct=22.5,
            longitude=4.9,
            latitude=52.37,
            updated_at=datetime(2026, 9, 28, tzinfo=UTC),
        ),
        **changes,
    )


def record() -> dict[str, object]:
    """Return a valid catalog record for delivery recovery tests."""
    return catalog_record(garage())


class CatalogTests(unittest.TestCase):
    """Keep catalog claims separate from live or inferred accessibility claims."""

    def test_identity_location_and_capacity_are_preserved(self) -> None:
        """Source IDs remain stable and unknown values never become zero."""
        self.assertEqual(
            record(),
            {
                "external_id": "source-original-ID",
                "name": "Example P+R",
                "source_name": "PR-123_ Example P+R (opendata)",
                "facility_type": "park_and_ride",
                "geometry": {"type": "Point", "coordinates": [4.9, 52.37]},
                "short_capacity": 120,
                "long_capacity": None,
                "accessible_capacity": None,
            },
        )
        self.assertEqual(catalog_record(garage(long_capacity=0))["long_capacity"], 0)
        row = record()
        row["short_available"] = 27
        with self.assertRaises(ValueError):
            validate_record(row)

    def test_live_changes_do_not_change_the_catalog(self) -> None:
        """Daily reviews compare metadata; time, counts and state are observations."""
        changed = catalog_record(
            garage(
                free_space_short=0,
                free_space_long=5,
                availability_pct=0,
                state="closed",
                updated_at=datetime(2026, 9, 29, tzinfo=UTC),
            )
        )
        self.assertEqual(changed, record())

    def test_invalid_source_claims_fail_closed(self) -> None:
        """Refuse swapped coordinates, lossy counts, missing IDs and naive dates."""
        for changes in (
            {"latitude": 4.9, "longitude": 52.37},
            {"latitude": float("nan")},
            {"longitude": True},
            {"garage_id": ""},
            {"garage_name": " "},
            {"short_capacity": -1},
            {"short_capacity": 1.5},
            {"short_capacity": True},
            {"vehicle": VehicleType.BICYCLE},
        ):
            with (
                self.subTest(changes=changes),
                self.assertRaises((ValueError, TypeError)),
            ):
                catalog_record(garage(**changes))

    def test_collect_uses_complete_package_selection_and_sorts_ids(self) -> None:
        """No NIPKaart HTTP parser or default page cap sits between source and file."""
        with patch("app.cities.netherlands.amsterdam.ODPAmsterdam") as client_class:
            fetch = AsyncMock(
                return_value=[garage(garage_id="z"), garage(garage_id="a")]
            )
            client_class.return_value.__aenter__.return_value.all_garages = fetch
            result = asyncio.run(Municipality().collect())
        fetch.assert_awaited_once_with(vehicle="car")
        self.assertTrue(result.complete)
        self.assertEqual(result.total_count, 2)
        self.assertEqual([row["external_id"] for row in result.records], ["a", "z"])

    def test_failed_deliveries_leave_existing_file_intact(self) -> None:
        """Never replace a good artifact with empty, duplicate or incomplete data."""
        for result in (
            Collection([], 0, 1, complete=True),
            Collection([record()], 1, 1, complete=False),
            Collection([record()], 2, 1, complete=True),
            Collection([record(), record()], 2, 1, complete=True),
            Collection([record()], 1, 0, complete=True),
        ):
            with (
                self.subTest(result=result),
                tempfile.TemporaryDirectory() as directory,
            ):
                output = Path(directory) / "catalog.json"
                output.write_bytes(b"last good")
                with self.assertRaises(ValueError):
                    write_records(
                        DATASETS["amsterdam"], result, output, datetime.now(UTC)
                    )
                self.assertEqual(output.read_bytes(), b"last good")

    def test_reexport_keeps_facility_ids_and_renews_delivery_identity(self) -> None:
        """The finite command writes exactly the format later uploaded to R2."""
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "catalog.json"
            with patch.object(
                Municipality, "collect", new_callable=AsyncMock
            ) as collect:
                collect.return_value = Collection([record()], 1, 1, complete=True)
                self.assertEqual(asyncio.run(export_dataset("amsterdam", output)), 1)
                first = json.loads(output.read_text())
                asyncio.run(export_dataset("amsterdam", output))
                second = json.loads(output.read_text())
            self.assertEqual(first["format"], "nipkaart-offstreet-catalog-1")
            self.assertEqual(first["dataset"], "nl-amsterdam-garages")
            self.assertEqual(first["records"], second["records"])
            self.assertNotEqual(first["delivery_id"], second["delivery_id"])
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])

    def test_size_limit_and_failed_rename_preserve_the_previous_file(self) -> None:
        """Oversize and interrupted writes do not leave a partial final file."""
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "catalog.json"
            output.write_bytes(b"last good")
            result = Collection([record()], 1, 1, complete=True)
            with patch("app.export.MAX_BYTES", 1), self.assertRaises(ValueError):
                write_records(DATASETS["amsterdam"], result, output, datetime.now(UTC))
            with (
                patch.object(Path, "replace", side_effect=OSError),
                self.assertRaises(OSError),
            ):
                write_records(DATASETS["amsterdam"], result, output, datetime.now(UTC))
            self.assertEqual(output.read_bytes(), b"last good")
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])

    def test_provider_error_does_not_create_an_output(self) -> None:
        """A failed package response cannot become an empty catalog."""
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "catalog.json"
            with patch("app.cities.netherlands.amsterdam.ODPAmsterdam") as client_class:
                client_class.return_value.__aenter__.return_value.all_garages = (
                    AsyncMock(
                        side_effect=ODPAmsterdamError("Source failed"),
                    )
                )
                with self.assertRaises(SourceError):
                    asyncio.run(export_dataset("amsterdam", output))
            self.assertFalse(output.exists())

    def test_source_deadline_preserves_existing_output(self) -> None:
        """Bound the whole collection even when an upstream client hangs."""

        async def blocked() -> Collection:
            await asyncio.sleep(10)
            return Collection([], 0, 1, complete=False)

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "catalog.json"
            output.write_bytes(b"last good")
            with (
                patch.object(Municipality, "collect", side_effect=blocked),
                patch("app.export.FETCH_TIMEOUT", 0.001),
                self.assertRaises(TimeoutError),
            ):
                asyncio.run(export_dataset("amsterdam", output))
            self.assertEqual(output.read_bytes(), b"last good")
