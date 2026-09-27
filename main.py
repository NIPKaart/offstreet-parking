"""Inspect existing offstreet sources without core credentials or data writes."""

import argparse
import asyncio

from app.cities.germany import hamburg
from app.cities.netherlands import amsterdam


class CityProvider:
    """Select an existing source wrapper without opening a database connection."""

    def provide_city(
        self, city_name: str
    ) -> amsterdam.Municipality | hamburg.Municipality:
        """Return the selected city."""
        match city_name:
            case "amsterdam":
                return amsterdam.Municipality()
            case "hamburg":
                return hamburg.Municipality()
            case _:
                msg = f"{city_name} is not a valid city."
                raise ValueError(msg)


def main(argv: list[str] | None = None) -> int:
    """Default to offline help; source inspection never loads core credentials."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fetch",
        choices=("amsterdam", "hamburg"),
        help="Fetch one source once and print its record count; no database writes.",
    )
    args = parser.parse_args(argv)
    if args.fetch:
        city = CityProvider().provide_city(args.fetch)
        records = asyncio.run(city.async_get_locations())
        print(f"{len(records)} source records retrieved; no data written.")
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
