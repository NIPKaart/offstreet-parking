"""Gent selection, original identities, measurements and delivery failure boundaries."""

import asyncio
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from odp_gent import Collection as SourceCollection
from odp_gent import ParkingFacility
from odp_gent.exceptions import ODPGentError

from app.cities.belgium import gent
from app.datasets import DATASETS
from app.export import export_dataset
from app.observations import collect_observations
from app.records import SourceError
from collector import deliver_observations, run_once


def facility(**changes: object) -> ParkingFacility:
    """Construct a small universal-package object without provider parsing."""
    return replace(
        ParkingFacility(
            facility_id="https://stad.gent/parking/example",
            name="Example",
            parking_type="carPark",
            longitude=3.72,
            latitude=51.05,
            updated_at=datetime(2026, 10, 13, 10, 3, tzinfo=UTC),
            total_capacity=100,
            free_space=0,
            is_open=True,
            temporary_closed=False,
        ),
        **changes,
    )


class GentTests(unittest.TestCase):
    """Keep two streams compatible without treating grounds as garages."""

    def test_catalog_keeps_original_identity_and_source_name(self) -> None:
        """Neither coordinate nor portal hash defines the facility identity."""
        self.assertEqual(
            gent.catalog_record(facility()),
            {
                "external_id": "https://stad.gent/parking/example",
                "name": "Example",
                "source_name": "Example",
                "facility_type": "garage",
                "geometry": {"type": "Point", "coordinates": [3.72, 51.05]},
            },
        )
        self.assertEqual(
            gent.catalog_record(facility(free_space=80, total_capacity=150)),
            gent.catalog_record(facility()),
        )

    def test_verified_grounds_and_pr_keep_their_facility_type(self) -> None:
        """Original-ID overrides distinguish garages/P+R from surface lots."""
        for identity, expected in gent.FACILITY_TYPES.items():
            with self.subTest(identity=identity):
                self.assertEqual(
                    gent.catalog_record(
                        facility(
                            facility_id=identity, parking_type="offStreetParkingGround"
                        )
                    )["facility_type"],
                    expected,
                )
        self.assertEqual(
            gent.facility_type(facility(parking_type="offStreetParkingGround")),
            "parking_lot",
        )
        with self.assertRaises(ValueError):
            gent.facility_type(facility(parking_type="unknown"))

    def test_original_time_zero_and_unknown_health_are_preserved(self) -> None:
        """General counts never become an accessible availability claim."""
        self.assertEqual(
            gent.observation_record(facility()),
            {
                "external_id": "https://stad.gent/parking/example",
                "observed_at": "2026-10-13T10:03:00Z",
                "source_state": "ok",
                "status": "counting",
                "capacity": 100,
                "available": 0,
            },
        )

    def test_missing_measurements_remain_unknown(self) -> None:
        """No fabricated time, zero or operational health is introduced."""
        data = gent.observation_record(
            facility(
                updated_at=None,
                total_capacity=None,
                free_space=None,
                is_open=None,
                temporary_closed=None,
            )
        )
        for field in ("observed_at", "status", "capacity", "available"):
            self.assertIsNone(data[field])
        self.assertEqual(
            gent.observation_record(facility(total_capacity=None, free_space=None))[
                "status"
            ],
            "open",
        )

    def test_closure_flags_override_counting_without_rewriting_counts(self) -> None:
        """A closed site can still report nonzero counts; preserve both claims."""
        for changes in ({"is_open": False}, {"temporary_closed": True}):
            data = gent.observation_record(facility(free_space=20, **changes))
            self.assertEqual(data["status"], "closed")
            self.assertEqual(data["available"], 20)

    def test_invalid_counts_time_and_coordinates_fail(self) -> None:
        """Lossy counts and undated local times never enter a delivery."""
        for changes in (
            {"free_space": -1},
            {"total_capacity": True},
            {"updated_at": datetime(2026, 10, 13).replace(tzinfo=None)},  # noqa: DTZ001
        ):
            with (
                self.subTest(changes=changes),
                self.assertRaises((ValueError, TypeError)),
            ):
                gent.observation_record(facility(**changes))
        with self.assertRaises(ValueError):
            gent.catalog_record(facility(longitude=float("nan")))

    def test_selection_is_complete_sorted_and_identical_in_both_streams(self) -> None:
        """Filter only after complete retrieval; catalog/observations share IDs."""
        result = SourceCollection(
            [
                facility(facility_id="b"),
                facility(facility_id="a"),
                facility(facility_id="surface", parking_type="offStreetParkingGround"),
            ],
            3,
            2,
            complete=True,
        )
        with patch.object(gent, "fetch_collection", new=AsyncMock(return_value=result)):
            data = asyncio.run(gent.Municipality().collect())
            observations = asyncio.run(collect_observations("gent"))
        self.assertEqual(data.total_count, 3)
        self.assertEqual(data.pages_fetched, 2)
        self.assertEqual(
            [row["external_id"] for row in data.records], ["a", "b", "surface"]
        )
        self.assertEqual(
            [row["external_id"] for row in observations["records"]],
            ["a", "b", "surface"],
        )
        self.assertEqual(observations["format"], "nipkaart-offstreet-observations-2")

    def test_failed_and_partial_retrieval_never_replace_a_catalog(self) -> None:
        """Package errors and inconsistent source counts fail before filtering."""
        for response in (
            ODPGentError("offline"),
            SourceCollection([facility()], 2, 1, complete=True),
            SourceCollection([facility()], 1, 1, complete=False),
            SourceCollection([facility(), facility()], 2, 1, complete=True),
        ):
            with (
                self.subTest(response=response),
                tempfile.TemporaryDirectory() as directory,
                patch.object(gent, "ODPGent") as client_class,
            ):
                method = (
                    client_class.return_value.__aenter__.return_value.parking_collection
                )
                if isinstance(response, Exception):
                    method.side_effect = response
                else:
                    method.return_value = response
                output = Path(directory) / "catalog.json"
                output.write_text("previous", encoding="utf-8")
                with self.assertRaises(SourceError):
                    asyncio.run(export_dataset("gent", output))
                self.assertEqual(output.read_text(), "previous")
                method.assert_awaited_once_with(max_records=10000)

    def test_r2_catalog_and_observations_use_registered_dataset(self) -> None:
        """Reuse conditional uploads and isolated pending state for Gent."""
        rows = SourceCollection([facility()], 1, 1, complete=True)
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(gent, "fetch_collection", new=AsyncMock(return_value=rows)),
            patch("collector.put") as upload,
        ):
            run_once(MagicMock(), "test", Path(directory), city="gent")
            catalog_key, catalog_bytes = upload.call_args.args[2:]
            self.assertTrue(catalog_key.startswith("offstreet/be-gent-parking/"))
            catalog = json.loads(catalog_bytes)
            self.assertEqual(catalog["source"], DATASETS["gent"].description.as_dict())
            self.assertEqual(
                catalog["source"]["area"]["municipality"],
                {"scheme": "be-ins", "code": "44021", "name": "Gent"},
            )
            self.assertTrue(
                (Path(directory) / "be-gent-parking" / "last.json").exists()
            )
            deliver_observations(MagicMock(), "test", city="gent")
            key, data = upload.call_args.args[2:]
            self.assertTrue(key.startswith("offstreet-observations/be-gent-parking/"))
            self.assertEqual(
                json.loads(data)["records"][0]["external_id"],
                catalog["records"][0]["external_id"],
            )
