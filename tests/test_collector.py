"""Test recovery using real SDK request validation without source or bucket access."""

from __future__ import annotations

import base64
import fcntl
import hashlib
import io
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import boto3
from botocore.response import StreamingBody
from botocore.stub import Stubber

from app.cities.netherlands.amsterdam import observation_record
from collector import run_once, upload
from tests.test_catalog import garage, record

DATASET = "nl-amsterdam-garages"


class CollectorTests(unittest.TestCase):
    """Keep the exact delivery on failures and refuse identity conflicts."""

    def setUp(self) -> None:
        """Use dummy credentials with botocore's in-process stub."""
        self.client = boto3.client(
            "s3",
            region_name="auto",
            aws_access_key_id="test",
            aws_secret_access_key="test",  # noqa: S106 - dummy SDK stub credentials
        )
        self.data = (
            json.dumps(
                {
                    "dataset": DATASET,
                    "delivery_id": str(uuid4()),
                    "format": "nipkaart-offstreet-catalog-1",
                    "selection": "car-garages-and-pr",
                    "complete": True,
                    "source_count": 1,
                    "retrieved_at": "2026-09-28T00:00:00Z",
                    "records": [record()],
                }
            )
            + "\n"
        ).encode()
        self.key = f"offstreet/{DATASET}/{json.loads(self.data)['delivery_id']}.json"
        self.parameters = {
            "Bucket": "test",
            "Key": self.key,
            "Body": self.data,
            "ContentType": "application/json",
            "ChecksumSHA256": base64.b64encode(
                hashlib.sha256(self.data).digest()
            ).decode("ascii"),
            "Metadata": {"sha256": hashlib.sha256(self.data).hexdigest()},
            "IfNoneMatch": "*",
        }

    def test_failed_upload_retries_without_fetching(self) -> None:
        """Failed upload and restart retain identical bytes and identity."""
        with tempfile.TemporaryDirectory() as directory, Stubber(self.client) as stub:
            root = Path(directory)
            path = root / DATASET
            path.mkdir()
            pending = path / "pending.json"
            pending.write_bytes(self.data)
            (path / "last.json").write_bytes(b"last good")
            stub.add_client_error(
                "put_object",
                service_error_code="ServiceUnavailable",
                http_status_code=503,
                expected_params=self.parameters,
            )
            stub.add_response("put_object", {}, self.parameters)
            with patch("collector.export_dataset", new_callable=AsyncMock) as fetch:
                with self.assertRaises(self.client.exceptions.ClientError):
                    run_once(self.client, "test", root)
                self.assertEqual(pending.read_bytes(), self.data)
                self.assertEqual((path / "last.json").read_bytes(), b"last good")
                self.assertEqual(run_once(self.client, "test", root), self.key)
                fetch.assert_not_awaited()
            self.assertFalse(pending.exists())
            self.assertEqual((path / "last.json").read_bytes(), self.data)
            stub.assert_no_pending_responses()

    def test_uncertain_upload_compares_remote_bytes(self) -> None:
        """Lost acknowledgement is recoverable; conflicting bytes never replace data."""
        for remote in (self.data, b"different"):
            with (
                self.subTest(remote=remote),
                tempfile.TemporaryDirectory() as directory,
                Stubber(self.client) as stub,
            ):
                root = Path(directory)
                path = root / DATASET
                path.mkdir()
                pending = path / "pending.json"
                pending.write_bytes(self.data)
                stub.add_client_error(
                    "put_object",
                    service_error_code="PreconditionFailed",
                    http_status_code=412,
                    expected_params=self.parameters,
                )
                stub.add_response(
                    "get_object",
                    {
                        "Body": StreamingBody(io.BytesIO(remote), len(remote)),
                    },
                    {"Bucket": "test", "Key": self.key},
                )
                if remote == self.data:
                    self.assertEqual(run_once(self.client, "test", root), self.key)
                else:
                    with self.assertRaisesRegex(ValueError, "different bytes"):
                        run_once(self.client, "test", root)
                    self.assertEqual(pending.read_bytes(), self.data)
                stub.assert_no_pending_responses()

    def test_failed_fetch_preserves_last_delivery(self) -> None:
        """Source failure causes no upload and leaves the last good artifact intact."""
        with tempfile.TemporaryDirectory() as directory, Stubber(self.client):
            root = Path(directory)
            path = root / DATASET
            path.mkdir()
            (path / "last.json").write_bytes(b"last good")
            with (
                patch("collector.export_dataset", side_effect=TimeoutError),
                self.assertRaises(TimeoutError),
            ):
                run_once(self.client, "test", root)
            self.assertEqual((path / "last.json").read_bytes(), b"last good")
            self.assertFalse((path / "pending.json").exists())

    def test_successful_fetch_uploads_saved_file(self) -> None:
        """The existing exporter feeds the uploader without another mapping layer."""

        async def collect(_city: str, path: Path) -> None:
            path.write_bytes(self.data)  # noqa: ASYNC240 - tiny local test input

        with tempfile.TemporaryDirectory() as directory, Stubber(self.client) as stub:
            stub.add_response("put_object", {}, self.parameters)
            with patch("collector.export_dataset", side_effect=collect):
                run_once(self.client, "test", Path(directory))
            self.assertEqual(
                (Path(directory) / DATASET / "last.json").read_bytes(), self.data
            )

    def test_invalid_pending_is_retained_without_upload(self) -> None:
        """Corrupt or oversized disk state fails closed instead of refetching."""
        with tempfile.TemporaryDirectory() as directory, Stubber(self.client):
            pending = Path(directory) / "pending.json"
            pending.write_bytes(self.data)
            with patch("collector.MAX_BYTES", 1), self.assertRaises(ValueError):
                upload(self.client, "test", pending)
            self.assertEqual(pending.read_bytes(), self.data)

    def test_wrong_or_incomplete_pending_never_reaches_the_bucket(self) -> None:
        """Do not turn manual/corrupt disk state into an accepted snapshot."""
        for changes in (
            {"dataset": "another-dataset"},
            {"format": "nipkaart-municipal-pilot-1"},
            {"complete": False},
            {"source_count": 2},
            {"records": []},
            {"delivery_id": "not-a-uuid"},
        ):
            with (
                self.subTest(changes=changes),
                tempfile.TemporaryDirectory() as directory,
                Stubber(self.client),
            ):
                root = Path(directory)
                path = root / DATASET
                path.mkdir()
                pending = path / "pending.json"
                raw = json.dumps({**json.loads(self.data), **changes}).encode()
                pending.write_bytes(raw)
                with patch("collector.export_dataset", new_callable=AsyncMock) as fetch:
                    with self.assertRaises(ValueError):
                        run_once(self.client, "test", root)
                    fetch.assert_not_awaited()
                self.assertEqual(pending.read_bytes(), raw)

    def test_overlapping_collector_cannot_fetch_or_upload(self) -> None:
        """A second command must respect the persisted delivery lock."""
        with tempfile.TemporaryDirectory() as directory, Stubber(self.client):
            root = Path(directory)
            path = root / DATASET
            path.mkdir()
            with (path / "delivery.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with patch("collector.export_dataset", new_callable=AsyncMock) as fetch:
                    with self.assertRaises(BlockingIOError):
                        run_once(self.client, "test", root)
                    fetch.assert_not_awaited()


class ObservationCollectorTests(unittest.TestCase):
    """Deliver live counts separately and never catch up on expired files."""

    def setUp(self) -> None:
        """Build one small observation file and its time-ordered object key."""
        self.client = boto3.client(
            "s3",
            region_name="auto",
            aws_access_key_id="test",
            aws_secret_access_key="test",  # noqa: S106 - dummy SDK stub credentials
        )
        self.fetched = datetime.now(UTC).replace(microsecond=0)
        self.delivery_id = str(uuid4())
        self.data = self.payload(self.fetched, self.delivery_id)
        self.key = (
            f"offstreet-observations/{DATASET}/"
            f"{self.fetched:%Y%m%dT%H%M%SZ}-{self.delivery_id}.json"
        )

    def payload(self, fetched: datetime, delivery_id: str) -> bytes:
        """Serialize an observation delivery exactly like the exporter."""
        observation = observation_record(
            garage(updated_at=fetched - timedelta(seconds=30)), fetched, 300
        )
        return (
            json.dumps(
                {
                    "format": "nipkaart-offstreet-observations-1",
                    "dataset": DATASET,
                    "selection": "car-garages-and-pr",
                    "delivery_id": delivery_id,
                    "fetched_at": fetched.isoformat().replace("+00:00", "Z"),
                    "max_age_seconds": 300,
                    "source_count": 1,
                    "records": [observation],
                }
            )
            + "\n"
        ).encode()

    def parameters(self, key: str, data: bytes) -> dict[str, object]:
        """Expect the same immutable, checksummed PUT as catalog delivery."""
        return {
            "Bucket": "test",
            "Key": key,
            "Body": data,
            "ContentType": "application/json",
            "ChecksumSHA256": base64.b64encode(hashlib.sha256(data).digest()).decode(
                "ascii"
            ),
            "Metadata": {"sha256": hashlib.sha256(data).hexdigest()},
            "IfNoneMatch": "*",
        }

    def test_fetch_uploads_to_separate_time_ordered_prefix(self) -> None:
        """Observations never share catalog state, keys or validation."""

        async def observe(_city: str, path: Path, max_age: int) -> None:
            self.assertEqual(max_age, 120)
            path.write_bytes(self.data)  # noqa: ASYNC240 - tiny local test input

        with tempfile.TemporaryDirectory() as directory, Stubber(self.client) as stub:
            root = Path(directory)
            stub.add_response("put_object", {}, self.parameters(self.key, self.data))
            with (
                patch("collector.export_observations", side_effect=observe),
                patch("collector.export_dataset", new_callable=AsyncMock) as catalog,
            ):
                self.assertEqual(
                    run_once(
                        self.client, "test", root, kind="observations", max_age=120
                    ),
                    self.key,
                )
                catalog.assert_not_awaited()
            path = root / DATASET / "observations"
            self.assertEqual((path / "last.json").read_bytes(), self.data)
            self.assertFalse((root / DATASET / "last.json").exists())
            stub.assert_no_pending_responses()

    def test_fresh_pending_is_retried_without_fetching(self) -> None:
        """A recent failed upload keeps its identity like a catalog delivery."""
        with tempfile.TemporaryDirectory() as directory, Stubber(self.client) as stub:
            root = Path(directory)
            path = root / DATASET / "observations"
            path.mkdir(parents=True)
            (path / "pending.json").write_bytes(self.data)
            stub.add_response("put_object", {}, self.parameters(self.key, self.data))
            with patch(
                "collector.export_observations", new_callable=AsyncMock
            ) as fetch:
                run_once(self.client, "test", root, kind="observations")
                fetch.assert_not_awaited()
            stub.assert_no_pending_responses()

    def test_expired_pending_is_replaced_by_a_new_fetch(self) -> None:
        """Old measurements are dropped rather than uploaded late."""
        old = self.payload(self.fetched - timedelta(seconds=300), str(uuid4()))

        async def observe(_city: str, path: Path, _max_age: int) -> None:
            path.write_bytes(self.data)  # noqa: ASYNC240 - tiny local test input

        with tempfile.TemporaryDirectory() as directory, Stubber(self.client) as stub:
            root = Path(directory)
            path = root / DATASET / "observations"
            path.mkdir(parents=True)
            (path / "pending.json").write_bytes(old)
            stub.add_response("put_object", {}, self.parameters(self.key, self.data))
            with patch("collector.export_observations", side_effect=observe):
                self.assertEqual(
                    run_once(self.client, "test", root, kind="observations"),
                    self.key,
                )
            self.assertEqual((path / "last.json").read_bytes(), self.data)
            stub.assert_no_pending_responses()

    def test_failed_fetch_publishes_nothing(self) -> None:
        """A source failure leaves no pending file and makes no request."""
        with tempfile.TemporaryDirectory() as directory, Stubber(self.client):
            root = Path(directory)
            with (
                patch("collector.export_observations", side_effect=TimeoutError),
                self.assertRaises(TimeoutError),
            ):
                run_once(self.client, "test", root, kind="observations")
            self.assertEqual(list((root / DATASET / "observations").glob("*.json")), [])

    def test_streams_reject_each_others_files(self) -> None:
        """A catalog cannot be uploaded as observations, nor the reverse."""
        catalog = CollectorTests("setUp")
        catalog.setUp()
        for kind, data in (("observations", catalog.data), ("catalog", self.data)):
            with (
                self.subTest(kind=kind),
                tempfile.TemporaryDirectory() as directory,
                Stubber(self.client),
            ):
                pending = Path(directory) / "pending.json"
                pending.write_bytes(data)
                with self.assertRaises((ValueError, KeyError)):
                    upload(self.client, "test", pending, kind=kind)
