"""Export an offstreet catalog or dated observations to a local file."""

import argparse
import asyncio
from pathlib import Path

from app.datasets import DATASETS
from app.export import export_dataset
from app.observations import export_observations
from app.records import SourceError


def main() -> None:
    """Fetch one complete selection; never publish or connect to core."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", required=True, choices=DATASETS)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--kind", choices=("catalog", "observations"), default="catalog"
    )
    args = parser.parse_args()
    try:
        if args.kind == "observations":
            count = asyncio.run(export_observations(args.city, args.output))
        else:
            count = asyncio.run(export_dataset(args.city, args.output))
    except (
        SourceError,
        OSError,
        ValueError,
        TypeError,
        KeyError,
    ) as error:
        parser.exit(1, f"Export failed: {error}\n")
    print(f"Exported {count} {args.kind} records to {args.output}.")


if __name__ == "__main__":
    main()
