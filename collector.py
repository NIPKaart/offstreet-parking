"""Deliver a complete, retryable offstreet JSON object to private R2."""

from __future__ import annotations

import argparse
import asyncio
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.datasets import DATASETS
from app.export import MAX_BYTES, export_dataset, validate_payload
from app.records import SourceError

if TYPE_CHECKING:
    from botocore.client import BaseClient


def upload(
    client: BaseClient, bucket: str, pending: Path, city: str = "amsterdam"
) -> str:
    """Create an immutable delivery; verify matching bytes after an uncertain PUT."""
    with pending.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        message = "Pending delivery exceeds 32 MiB"
        raise ValueError(message)
    payload = json.loads(data)
    validate_payload(payload, DATASETS[city])
    delivery_id = str(UUID(payload["delivery_id"]))
    key = f"offstreet/{payload['dataset']}/{delivery_id}.json"
    digest = hashlib.sha256(data).hexdigest()
    print(f"Uploading {key} sha256={digest}", flush=True)
    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType="application/json",
            ContentMD5=base64.b64encode(
                hashlib.md5(data, usedforsecurity=False).digest(),
            ).decode("ascii"),
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


def run_once(
    client: BaseClient, bucket: str, directory: Path, city: str = "amsterdam"
) -> str:
    """Keep the pending artifact until acknowledged; never fetch its replacement."""
    dataset = DATASETS[city]
    directory = directory / dataset.code
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "delivery.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        pending = directory / "pending.json"
        if not pending.exists():
            for temporary in directory.glob(".parking-*.tmp"):
                temporary.unlink()
            asyncio.run(export_dataset(city, pending))
        sync_directory(directory)
        key = upload(client, bucket, pending, city)
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
        run_once(client, bucket, args.directory, args.city)
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
