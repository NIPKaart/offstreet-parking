"""Test recovery using real SDK request validation without source or bucket access."""

from __future__ import annotations

import base64
import fcntl
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import boto3
from botocore.response import StreamingBody
from botocore.stub import Stubber

from app.cities.netherlands.amsterdam import observation_record
from app.export import encode
from collector import deliver_observations, run_once, upload
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
    """Deliver live counts without local state; a failure simply skips a run."""

    def setUp(self) -> None:
        """Use dummy credentials with botocore's in-process stub."""
        self.client = boto3.client(
            "s3",
            region_name="auto",
            aws_access_key_id="test",
            aws_secret_access_key="test",  # noqa: S106 - dummy SDK stub credentials
        )
        self.payload = {
            "format": "nipkaart-offstreet-observations-1",
            "dataset": DATASET,
            "selection": "car-garages-and-pr",
            "delivery_id": str(uuid4()),
            "fetched_at": "2026-09-28T09:01:11.123456Z",
            "source_count": 1,
            "records": [observation_record(garage())],
        }

    def test_fetch_uploads_to_time_ordered_prefix(self) -> None:
        """Observation keys never collide with or list among catalog deliveries."""
        data = encode(self.payload)
        key = (
            f"offstreet-observations/{DATASET}/"
            f"20260928T090111Z-{self.payload['delivery_id']}.json"
        )
        with Stubber(self.client) as stub:
            stub.add_response(
                "put_object",
                {},
                {
                    "Bucket": "test",
                    "Key": key,
                    "Body": data,
                    "ContentType": "application/json",
                    "ChecksumSHA256": base64.b64encode(
                        hashlib.sha256(data).digest()
                    ).decode("ascii"),
                    "Metadata": {"sha256": hashlib.sha256(data).hexdigest()},
                    "IfNoneMatch": "*",
                },
            )
            with patch(
                "collector.collect_observations",
                new_callable=AsyncMock,
                return_value=self.payload,
            ):
                self.assertEqual(deliver_observations(self.client, "test"), key)
            stub.assert_no_pending_responses()

    def test_failed_fetch_publishes_nothing(self) -> None:
        """A source failure makes no bucket request."""
        with (
            Stubber(self.client),
            patch("collector.collect_observations", side_effect=TimeoutError),
            self.assertRaises(TimeoutError),
        ):
            deliver_observations(self.client, "test")
