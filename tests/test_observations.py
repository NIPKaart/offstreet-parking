"""Exercise freshness and failure boundaries for the separate live export."""

import asyncio
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app.cities.netherlands.amsterdam import Municipality, observation_record
from app.datasets import DATASETS
from app.export import validate_payload
from app.observations import export_observations
from app.records import Collection
from tests.test_catalog import garage

FETCHED = datetime(2026, 9, 28, 0, 1, tzinfo=UTC)


class ObservationTests(unittest.TestCase):
    """Keep zero, unknown, historical and unavailable observations distinct."""

    def test_current_counts_keep_unknown_and_zero_distinct(self) -> None:
        """Retain source categories without adding them or implying accessibility."""
        record = observation_record(garage(free_space_short=0), FETCHED, 300)
        self.assertEqual(record["external_id"], "source-original-ID")
        self.assertEqual(record["status"], "current")
        self.assertEqual(record["observed_at"], "2026-09-28T00:00:00Z")
        self.assertEqual(record["valid_until"], "2026-09-28T00:05:00Z")
        self.assertEqual(record["short_stay"], {"capacity": 120, "available": 0})
        self.assertIsNone(record["long_stay"])
        self.assertEqual(record["accessible"], {"capacity": None, "available": None})

    def test_optional_long_stay_keeps_partial_data_and_zero(self) -> None:
        """Only absent source data omits the group; zero is a known count."""
        for total, available in ((40, 12), (None, 12), (40, None), (0, 0)):
            with self.subTest(total=total, available=available):
                record = observation_record(
                    garage(long_capacity=total, free_space_long=available), FETCHED, 300
                )
                self.assertEqual(
                    record["long_stay"], {"capacity": total, "available": available}
                )
                self.assertEqual(
                    record["short_stay"], {"capacity": 120, "available": 27}
                )

    def test_expired_measurement_is_historical_at_the_exact_boundary(self) -> None:
        """Never refresh an observation's expiry merely by fetching it again."""
        for fetched in (FETCHED + timedelta(minutes=4), FETCHED + timedelta(days=1)):
            with self.subTest(fetched=fetched):
                record = observation_record(garage(), fetched, 300)
                self.assertEqual(record["status"], "stale")
                self.assertEqual(record["short_stay"]["available"], 27)
                self.assertEqual(record["valid_until"], "2026-09-28T00:05:00Z")

    def test_unusable_source_observations_do_not_claim_free_spaces(self) -> None:
        """An error, missing clock or future clock cannot claim current availability."""
        for changes in (
            {"state": "closed"},
            {"state": "error"},
            {"updated_at": None},
            {"updated_at": FETCHED + timedelta(seconds=1)},
        ):
            with self.subTest(changes=changes):
                record = observation_record(
                    garage(long_capacity=40, free_space_long=12, **changes),
                    FETCHED,
                    300,
                )
                self.assertEqual(record["status"], "unavailable")
                self.assertEqual(
                    record["long_stay"], {"capacity": 40, "available": None}
                )
                self.assertIsNone(record["short_stay"]["available"])
                self.assertIsNone(record["accessible"]["available"])

    def test_invalid_counts_and_timestamps_fail_closed(self) -> None:
        """Reject lossy, negative or timezone-free source values."""
        for changes in (
            {"free_space_short": -1},
            {"free_space_long": True},
            {"free_space_short": 1.5},
            {"updated_at": datetime(2026, 9, 28, tzinfo=None)},  # noqa: DTZ001
        ):
            with (
                self.subTest(changes=changes),
                self.assertRaises((ValueError, TypeError)),
            ):
                observation_record(garage(**changes), FETCHED, 300)

    def test_live_export_uses_car_selection_and_cannot_be_uploaded_as_catalog(
        self,
    ) -> None:
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
            self.assertEqual(payload["format"], "nipkaart-offstreet-observations-1")
            self.assertEqual(payload["dataset"], "nl-amsterdam-garages")
            self.assertEqual(payload["max_age_seconds"], 300)
            self.assertEqual([r["external_id"] for r in payload["records"]], ["a", "z"])
            with self.assertRaises(ValueError):
                validate_payload(payload, DATASETS["amsterdam"])

    def test_incomplete_selection_and_invalid_age_preserve_previous_export(
        self,
    ) -> None:
        """A broken fetch cannot erase the last complete observation artifact."""
        record = observation_record(garage(), FETCHED, 300)
        for result in (
            Collection([], 0, 1, complete=True),
            Collection([record], 1, 1, complete=False),
            Collection([record], 2, 1, complete=True),
            Collection([record, record], 2, 1, complete=True),
        ):
            with (
                self.subTest(result=result),
                tempfile.TemporaryDirectory() as directory,
            ):
                output = Path(directory) / "observations.json"
                output.write_bytes(b"last good")
                with patch.object(
                    Municipality, "observe", new_callable=AsyncMock
                ) as fetch:
                    fetch.return_value = result
                    with self.assertRaises(ValueError):
                        asyncio.run(export_observations("amsterdam", output))
                    for age in (0, -1, True):
                        with self.assertRaises(ValueError):
                            asyncio.run(export_observations("amsterdam", output, age))
                self.assertEqual(output.read_bytes(), b"last good")
