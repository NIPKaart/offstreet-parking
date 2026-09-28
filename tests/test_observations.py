"""Exercise the observation mapping and its failure boundaries."""

import asyncio
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

from odp_amsterdam import GarageStatus

from app.cities.netherlands.amsterdam import Municipality, observation_record
from app.datasets import DATASETS
from app.export import validate_payload
from app.observations import collect_observations, export_observations
from app.records import Collection, validate_observation
from tests.test_catalog import garage


class ObservationTests(unittest.TestCase):
    """Pass source values on; keep zero, unknown and accessibility distinct."""

    def test_source_time_state_status_and_counts_are_passed_on(self) -> None:
        """Core decides freshness; capacity and status travel with the count."""
        record = observation_record(
            garage(
                free_space_short=0,
                short_capacity=328,
                long_capacity=40,
                free_space_long=12,
                status=GarageStatus.CLOSED,
            )
        )
        self.assertEqual(
            record,
            {
                "external_id": "source-original-ID",
                "observed_at": "2026-09-28T00:00:00Z",
                "source_state": "ok",
                "status": "closed",
                "capacity": 328,
                "available": 0,
            },
        )

    def test_placeholder_counts_become_unknown(self) -> None:
        """Without a known capacity, a reported 0 free spaces is not "full"."""
        record = observation_record(
            garage(
                state="error",
                short_capacity=0,
                free_space_short=0,
                status=GarageStatus.MALFUNCTION,
            )
        )
        self.assertEqual(record["source_state"], "error")
        self.assertEqual(record["status"], "malfunction")
        self.assertIsNone(record["capacity"])
        self.assertIsNone(record["available"])

    def test_unknown_values_stay_unknown(self) -> None:
        """Missing time or counts never become zero or a fetch time."""
        record = observation_record(
            garage(updated_at=None, free_space_short=None, state=None)
        )
        self.assertIsNone(record["observed_at"])
        self.assertIsNone(record["source_state"])
        self.assertIsNone(record["status"])
        self.assertIsNone(record["available"])

    def test_invalid_source_values_fail_closed(self) -> None:
        """Reject lossy, negative or timezone-free source values."""
        for changes in (
            {"free_space_short": -1},
            {"short_capacity": True},
            {"free_space_short": 1.5},
            {"garage_id": ""},
            {"updated_at": datetime(2026, 9, 28, tzinfo=None)},  # noqa: DTZ001
        ):
            with (
                self.subTest(changes=changes),
                self.assertRaises((ValueError, TypeError)),
            ):
                observation_record(garage(**changes))
        with self.assertRaises(ValueError):
            validate_observation(
                {**observation_record(garage()), "accessible_capacity": None}
            )
        with self.assertRaises(ValueError):
            validate_observation({**observation_record(garage()), "status": "GETAL"})

    def test_export_uses_car_selection_and_cannot_pass_as_catalog(self) -> None:
        """The two streams share source identity but have different contracts."""
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "observations.json"
            with patch("app.cities.netherlands.amsterdam.ODPAmsterdam") as client:
                fetch = AsyncMock(
                    return_value=[garage(garage_id="z"), garage(garage_id="a")]
                )
                client.return_value.__aenter__.return_value.all_garages = fetch
                self.assertEqual(
                    asyncio.run(export_observations("amsterdam", output)), 2
                )
            fetch.assert_awaited_once_with(vehicle="car")
            payload = json.loads(output.read_text())
            self.assertEqual(payload["format"], "nipkaart-offstreet-observations-2")
            self.assertEqual(payload["dataset"], "nl-amsterdam-garages")
            self.assertEqual([r["external_id"] for r in payload["records"]], ["a", "z"])
            self.assertLessEqual(
                datetime.fromisoformat(payload["fetched_at"]), datetime.now(UTC)
            )
            with self.assertRaises((ValueError, KeyError)):
                validate_payload(payload, DATASETS["amsterdam"])

    def test_incomplete_selection_is_rejected(self) -> None:
        """A broken fetch cannot become a delivery."""
        record = observation_record(garage())
        for result in (
            Collection([], 0, 1, complete=True),
            Collection([record], 1, 1, complete=False),
            Collection([record], 2, 1, complete=True),
            Collection([record, record], 2, 1, complete=True),
        ):
            with (
                self.subTest(result=result),
                patch.object(Municipality, "observe", new_callable=AsyncMock) as fetch,
            ):
                fetch.return_value = result
                with self.assertRaises(ValueError):
                    asyncio.run(collect_observations("amsterdam"))
