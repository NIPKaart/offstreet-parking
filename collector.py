"""Deliver a complete offstreet catalog or observation object to private R2."""

from __future__ import annotations

import argparse
import asyncio
import base64
import fcntl
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.datasets import DATASETS
from app.export import MAX_BYTES, export_dataset, validate_payload
from app.observations import expired, export_observations, validate_observations
from app.records import SourceError, validate_timestamp

if TYPE_CHECKING:
    from botocore.client import BaseClient


KINDS = ("catalog", "observations")


def read_pending(pending: Path, city: str, kind: str) -> tuple[bytes, dict]:
    """Read and validate persisted bytes exactly as they will be uploaded."""
    with pending.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        message = "Pending delivery exceeds 32 MiB"
        raise ValueError(message)
    payload = json.loads(data)
    if kind == "observations":
        validate_observations(payload, DATASETS[city])
    else:
        validate_payload(payload, DATASETS[city])
    return data, payload


def object_key(payload: dict, kind: str) -> str:
    """Separate streams by prefix; order observation keys by retrieval time."""
    delivery_id = str(UUID(payload["delivery_id"]))
    if kind == "observations":
        fetched_at = validate_timestamp(payload["fetched_at"]).astimezone(UTC)
        return (
            f"offstreet-observations/{payload['dataset']}/"
            f"{fetched_at:%Y%m%dT%H%M%SZ}-{delivery_id}.json"
        )
    return f"offstreet/{payload['dataset']}/{delivery_id}.json"


def upload(
    client: BaseClient,
    bucket: str,
    pending: Path,
    city: str = "amsterdam",
    kind: str = "catalog",
) -> str:
    """Create an immutable delivery; verify matching bytes after an uncertain PUT."""
    data, payload = read_pending(pending, city, kind)
    key = object_key(payload, kind)
    digest = hashlib.sha256(data).hexdigest()
    print(f"Uploading {key} sha256={digest}", flush=True)
    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType="application/json",
            ChecksumSHA256=base64.b64encode(hashlib.sha256(data).digest()).decode(
                "ascii"
            ),
            Metadata={"sha256": digest},
            IfNoneMatch="*",
        )
    except ClientError as error:
        if error.response["ResponseMetadata"]["HTTPStatusCode"] != 412:
            raise
        response = client.get_object(Bucket=bucket, Key=key)
        with response["Body"] as stream:
            existing = stream.read(MAX_BYTES + 1)
        if existing != data:
            message = "Remote delivery identity already exists with different bytes"
            raise ValueError(message) from error
    return key


def run_once(  # noqa: PLR0913 - two independent stream options
    client: BaseClient,
    bucket: str,
    directory: Path,
    city: str = "amsterdam",
    *,
    kind: str = "catalog",
    max_age: int = 300,
) -> str:
    """Retry a pending catalog until acknowledged; expire pending observations."""
    dataset = DATASETS[city]
    directory = directory / dataset.code
    if kind == "observations":
        directory /= "observations"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "delivery.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        pending = directory / "pending.json"
        if (
            kind == "observations"
            and pending.exists()
            and expired(read_pending(pending, city, kind)[1], datetime.now(UTC))
        ):
            pending.unlink()
            print("Discarded expired pending observations", flush=True)
        if not pending.exists():
            for temporary in directory.glob(".parking-*.tmp"):
                temporary.unlink()
            if kind == "observations":
                asyncio.run(export_observations(city, pending, max_age))
            else:
                asyncio.run(export_dataset(city, pending))
        sync_directory(directory)
        key = upload(client, bucket, pending, city, kind)
        pending.replace(directory / "last.json")
        sync_directory(directory)
        print(f"Delivered {key}", flush=True)
        return key


def sync_directory(directory: Path) -> None:
    """Persist renames before acknowledging delivery or starting its upload."""
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def main() -> None:
    """Require R2 credentials and keep credential-bearing errors out of logs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("/data"))
    parser.add_argument("--city", choices=DATASETS, default="amsterdam")
    parser.add_argument("--kind", choices=KINDS, default="catalog")
    parser.add_argument("--max-age-seconds", type=int, default=300)
    args = parser.parse_args()
    try:
        endpoint = os.environ["R2_ENDPOINT"]
        bucket = os.environ["R2_BUCKET"]
        if not endpoint.startswith("https://") or not bucket:
            parser.error("R2_ENDPOINT must use HTTPS and R2_BUCKET must be set")
        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name="auto",
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
            config=Config(
                connect_timeout=10,
                read_timeout=30,
                retries={"mode": "standard", "total_max_attempts": 3},
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )
        run_once(
            client,
            bucket,
            args.directory,
            args.city,
            kind=args.kind,
            max_age=args.max_age_seconds,
        )
    except (
        BotoCoreError,
        ClientError,
        SourceError,
        OSError,
        ValueError,
        TypeError,
        KeyError,
    ) as error:
        parser.exit(
            1, f"Collector failed ({type(error).__name__}); pending file retained\n"
        )


if __name__ == "__main__":
    main()
