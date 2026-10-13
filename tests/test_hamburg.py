"""Hamburg mapping and full R2 delivery boundaries."""

import asyncio
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from hamburg import Collection as SourceCollection
from hamburg import ParkAndRide
from hamburg.exceptions import UDPHamburgError

import collector
from app.cities.germany import hamburg
from app.export import export_dataset
from app.observations import collect_observations
from app.records import Collection, SourceError
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

    def test_catalog_keeps_original_identity_and_no_observation_claims(self) -> None:
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
        result = SourceCollection([facility()], 1, 2, complete=True)
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
                    return_value=SourceCollection([facility()], 2, 1, complete=False)
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
                    return_value=SourceCollection(
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
        result = SourceCollection([facility()], 1, 1, complete=True)
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
                side_effect=["gent-key", SourceError("offline"), "key"],
            ) as deliver,
        ):
            self.assertEqual(collector.main(["--kind", "observations"]), 1)
            self.assertEqual(
                [call.args[2] for call in deliver.call_args_list],
                ["gent", "hamburg", "amsterdam"],
            )


class HamburgIdentityTests(unittest.TestCase):
    """Deliver original identity claims and reject inconsistent snapshots."""

    def test_source_refresh_preserves_original_source_ids(self) -> None:
        """Identity reconciliation belongs to core, with original claims intact."""
        for record in (facility(spot_id="12686527"), facility(spot_id="12686565")):
            self.assertEqual(
                hamburg.catalog_record(record)["external_id"], record.spot_id
            )
            self.assertEqual(
                hamburg.observation_record(record)["external_id"], record.spot_id
            )

    def test_changed_claims_are_delivered_for_core_review(self) -> None:
        """A rename or position change remains visible to the consumer."""
        for record in (facility(name="Other"), facility(longitude=10.16269)):
            with self.subTest(record=record):
                claim = hamburg.catalog_record(record)
                self.assertEqual(claim["name"], record.name)
                self.assertEqual(claim["geometry"]["coordinates"][0], record.longitude)

    def test_different_snapshot_identity_context_is_rejected(self) -> None:
        """A second refresh cannot supply claims for the first refresh's counts."""
        result = Collection(
            [hamburg.observation_record(facility())],
            1,
            1,
            complete=True,
            identity_records=[hamburg.catalog_record(facility(spot_id="other"))],
        )
        with (
            patch.object(
                hamburg.Municipality, "observe", AsyncMock(return_value=result)
            ),
            self.assertRaisesRegex(ValueError, "different source snapshots"),
        ):
            asyncio.run(collect_observations("hamburg"))

    def test_new_facility_is_delivered_for_core_review(self) -> None:
        """New source records are claims, not collector publication decisions."""
        result = SourceCollection(
            [facility(), facility(name="New site", spot_id="new")], 2, 1, complete=True
        )
        with (
            patch.object(hamburg, "fetch_collection", AsyncMock(return_value=result)),
            tempfile.TemporaryDirectory() as directory,
        ):
            output = Path(directory) / "catalog.json"
            asyncio.run(export_dataset("hamburg", output))
            self.assertEqual(json.loads(output.read_text())["source_count"], 2)
            observed = asyncio.run(collect_observations("hamburg"))
            self.assertEqual(observed["format"], "nipkaart-offstreet-observations-3")
            self.assertEqual(len(observed["identity_records"]), 2)

    def test_incomplete_identity_context_is_rejected(self) -> None:
        """The complete observation set requires a complete identity set."""
        result = Collection(
            [hamburg.observation_record(facility())],
            1,
            1,
            complete=True,
            identity_records=[],
        )
        with (
            patch.object(
                hamburg.Municipality, "observe", AsyncMock(return_value=result)
            ),
            self.assertRaises(ValueError),
        ):
            asyncio.run(collect_observations("hamburg"))

    def test_invalid_identity_context_is_rejected(self) -> None:
        """Claims must satisfy catalog geometry and the registered source bounds."""
        for claim in (
            {"external_id": "12675697"},
            hamburg.catalog_record(facility(longitude=4.9, latitude=52.37)),
        ):
            result = Collection(
                [hamburg.observation_record(facility())],
                1,
                1,
                complete=True,
                identity_records=[claim],
            )
            with (
                self.subTest(claim=claim),
                patch.object(
                    hamburg.Municipality, "observe", AsyncMock(return_value=result)
                ),
                self.assertRaises(ValueError),
            ):
                asyncio.run(collect_observations("hamburg"))

    def test_duplicate_source_ids_do_not_replace_export(self) -> None:
        """Two upstream records must not silently collapse into one facility."""
        result = SourceCollection([facility(), facility()], 2, 1, complete=True)
        with (
            patch.object(hamburg, "fetch_collection", AsyncMock(return_value=result)),
            tempfile.TemporaryDirectory() as directory,
        ):
            output = Path(directory) / "catalog.json"
            output.write_text("previous delivery")
            with self.assertRaises(ValueError):
                asyncio.run(export_dataset("hamburg", output))
            self.assertEqual(output.read_text(), "previous delivery")
            with self.assertRaises(ValueError):
                asyncio.run(collect_observations("hamburg"))


class HamburgLiveIdentityTests(unittest.TestCase):
    """One fetch supplies both live values and immutable identity evidence."""

    def test_rotating_ids_share_same_fetch_identity_context(self) -> None:
        """No registry or second catalog request is necessary after refresh."""
        before = SourceCollection([facility()], 1, 1, complete=True)
        after = SourceCollection([facility(spot_id="200")], 1, 1, complete=True)
        with patch.object(
            hamburg, "fetch_collection", AsyncMock(side_effect=[before, after])
        ) as fetch:
            first = asyncio.run(collect_observations("hamburg"))
            second = asyncio.run(collect_observations("hamburg"))
        self.assertEqual(fetch.await_count, 2)
        self.assertEqual(first["records"][0]["external_id"], "12675697")
        self.assertEqual(second["records"][0]["external_id"], "200")
        self.assertEqual(second["identity_records"][0]["external_id"], "200")
        self.assertEqual(
            first["identity_records"][0]["geometry"],
            second["identity_records"][0]["geometry"],
        )
        self.assertNotIn("capacity", second["identity_records"][0])
        self.assertEqual(second["records"][0]["observed_at"], "2026-10-10T20:00:00Z")
