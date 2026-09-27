"""Export offstreet accessible parking to a local file for core review."""

import argparse
import asyncio
from pathlib import Path

from app.datasets import DATASETS
from app.export import export_dataset
from app.records import SourceError


def main() -> None:
    """Fetch one complete selection; never publish or connect to core."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", required=True, choices=DATASETS)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        count = asyncio.run(export_dataset(args.city, args.output))
    except (
        SourceError,
        OSError,
        ValueError,
        TypeError,
        KeyError,
    ) as error:
        parser.exit(1, f"Export failed: {error}\n")
    print(f"Exported {count} records; complete source selection ready for core review.")


if __name__ == "__main__":
    main()
