"""Hamburg mapping and full R2 delivery boundaries."""

import asyncio
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from hamburg import ParkAndRide, ParkAndRideCollection
from hamburg.exceptions import UDPHamburgError

import collector
from app.cities.germany import hamburg
from app.export import export_dataset
from app.observations import collect_observations
from app.records import SourceError
from collector import run_once


def facility(**changes: object) -> ParkAndRide:
    """Build a small package DTO with source identity and measurement time."""
    return replace(
        ParkAndRide(
            spot_id="12675697",
            name="Volksdorf",
            park_type="Parkhaus",
            address="Example",
            construction_year=None,
            public_transport_line="U1",
            disabled_parking_spaces=3,
            tickets={},
            url=None,
            free_space=0,
            capacity=357,
            availability_pct=None,
            longitude=10.16169,
            latitude=53.64967,
            updated_at=datetime(2026, 10, 10, 20, tzinfo=UTC),
        ),
        **changes,
    )


class HamburgTests(unittest.TestCase):
    """Preserve P+R semantics, unknown measurements and complete collections."""

    def test_catalog_keeps_source_identity_and_no_observation_claims(self) -> None:
        """The P+R garage stays a P+R, not an ordinary garage."""
        self.assertEqual(
            hamburg.catalog_record(facility()),
            {
                "external_id": "12675697",
                "name": "Volksdorf",
                "source_name": "Volksdorf",
                "facility_type": "park_and_ride",
                "geometry": {"type": "Point", "coordinates": [10.16169, 53.64967]},
            },
        )

    def test_observations_keep_zero_and_original_time(self) -> None:
        """Zero available spaces is a measured zero, never accessible occupancy."""
        self.assertEqual(
            hamburg.observation_record(facility()),
            {
                "external_id": "12675697",
                "observed_at": "2026-10-10T20:00:00Z",
                "source_state": "ok",
                "status": "counting",
                "capacity": 357,
                "available": 0,
            },
        )

    def test_absent_values_and_time_stay_unknown(self) -> None:
        """No fetch time or static accessible capacity becomes a live claim."""
        data = hamburg.observation_record(
            facility(free_space=None, capacity=None, updated_at=None)
        )
        self.assertIsNone(data["capacity"])
        self.assertIsNone(data["available"])
        self.assertIsNone(data["observed_at"])
        self.assertIsNone(data["status"])

    def test_package_completeness_drives_export_and_observations(self) -> None:
        """Use the full collection API for both streams."""
        result = ParkAndRideCollection([facility()], 1, 2, complete=True)
        with (
            patch.object(hamburg, "UDPHamburg") as client_class,
            tempfile.TemporaryDirectory() as directory,
        ):
            client = client_class.return_value.__aenter__.return_value
            client.park_and_ride_collection = AsyncMock(return_value=result)
            output = Path(directory) / "catalog.json"
            self.assertEqual(asyncio.run(export_dataset("hamburg", output)), 1)
            catalog = json.loads(output.read_text())
            self.assertEqual(catalog["dataset"], "de-hamburg-pr")
            self.assertEqual(catalog["selection"], "pr-all")
            self.assertEqual(
                catalog["source"]["area"]["municipality"]["code"], "02000000"
            )
            observations = asyncio.run(collect_observations("hamburg"))
            self.assertEqual(observations["dataset"], catalog["dataset"])
            self.assertEqual(
                observations["records"][0]["external_id"],
                catalog["records"][0]["external_id"],
            )
            self.assertEqual(client.park_and_ride_collection.await_count, 2)
            client.park_and_ride_collection.assert_awaited_with(max_records=10000)

    def test_incomplete_collection_preserves_previous_export(self) -> None:
        """Reject partial results instead of replacing a retained snapshot."""
        with (
            patch.object(
                hamburg,
                "fetch_collection",
                AsyncMock(
                    return_value=ParkAndRideCollection(
                        [facility()], 2, 1, complete=False
                    )
                ),
            ),
            tempfile.TemporaryDirectory() as directory,
        ):
            output = Path(directory) / "catalog.json"
            output.write_text("previous delivery")
            with self.assertRaises(ValueError):
                asyncio.run(export_dataset("hamburg", output))
            self.assertEqual(output.read_text(), "previous delivery")
            with self.assertRaises(ValueError):
                asyncio.run(collect_observations("hamburg"))

    def test_failed_source_produces_no_collection(self) -> None:
        """Provider errors become bounded collector failures."""
        with patch.object(hamburg, "UDPHamburg") as client_class:
            client = client_class.return_value.__aenter__.return_value
            client.park_and_ride_collection = AsyncMock(
                side_effect=UDPHamburgError("offline")
            )
            with self.assertRaises(SourceError):
                asyncio.run(hamburg.Municipality().collect())

    def test_outside_bounds_does_not_replace_export(self) -> None:
        """A source result outside Hamburg cannot escape the registered bounds."""
        with (
            patch.object(
                hamburg,
                "fetch_collection",
                AsyncMock(
                    return_value=ParkAndRideCollection(
                        [facility(longitude=4.9, latitude=52.37)], 1, 1, complete=True
                    )
                ),
            ),
            tempfile.TemporaryDirectory() as directory,
        ):
            output = Path(directory) / "catalog.json"
            output.write_text("previous delivery")
            with self.assertRaises(ValueError):
                asyncio.run(export_dataset("hamburg", output))
            self.assertEqual(output.read_text(), "previous delivery")


class HamburgDeliveryTests(unittest.TestCase):
    """Keep retries and multi-source execution isolated by dataset."""

    def test_pending_catalog_is_retried_without_fetching_new_data(self) -> None:
        """An uncertain upload preserves Hamburg's exact delivery identity."""
        result = ParkAndRideCollection([facility()], 1, 1, complete=True)
        client = MagicMock()
        client.put_object.side_effect = [OSError("interrupted"), None]
        with (
            patch.object(
                hamburg, "fetch_collection", AsyncMock(return_value=result)
            ) as fetch,
            tempfile.TemporaryDirectory() as directory,
        ):
            with self.assertRaises(OSError):
                run_once(client, "test", Path(directory), "hamburg")
            pending = Path(directory) / "de-hamburg-pr" / "pending.json"
            original = pending.read_bytes()
            key = run_once(client, "test", Path(directory), "hamburg")
            self.assertTrue(key.startswith("offstreet/de-hamburg-pr/"))
            self.assertEqual((pending.parent / "last.json").read_bytes(), original)
            self.assertEqual(client.put_object.call_args.kwargs["Body"], original)
            self.assertFalse(pending.exists())
            fetch.assert_awaited_once()

    def test_one_source_failure_does_not_skip_the_other_source(self) -> None:
        """All-source execution reports failure while delivering healthy sources."""
        with (
            patch.dict(
                collector.os.environ,
                {
                    "R2_ENDPOINT": "https://example.test",
                    "R2_BUCKET": "test",
                    "AWS_ACCESS_KEY_ID": "test",
                    "AWS_SECRET_ACCESS_KEY": "test",
                },
            ),
            patch.object(collector.boto3, "client"),
            patch.object(
                collector,
                "deliver_observations",
                side_effect=[SourceError("offline"), "key"],
            ) as deliver,
        ):
            self.assertEqual(collector.main(["--kind", "observations"]), 1)
            self.assertEqual(
                [call.args[2] for call in deliver.call_args_list],
                ["hamburg", "amsterdam"],
            )
