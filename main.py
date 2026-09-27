"""Inspect offstreet sources or explicitly run the legacy MySQL writer."""

import argparse
import asyncio
import os
import time
from datetime import datetime

import pytz
from dotenv import load_dotenv

from app.cities import City
from app.cities.germany import hamburg
from app.cities.netherlands import amsterdam


class CityProvider:
    """Select an existing source wrapper without opening a database connection."""

    def provide_city(self, city_name: str) -> City:
        """Return the selected city."""
        match city_name:
            case "amsterdam":
                return amsterdam.Municipality()
            case "hamburg":
                return hamburg.Municipality()
            case _:
                msg = f"{city_name} is not a valid city."
                raise ValueError(msg)


def run_legacy(selected_city: str, wait_time: int) -> None:
    """Run the existing continuous database writer, including its quiet hour."""
    provided_city = CityProvider().provide_city(selected_city)
    while True:
        local_zone = pytz.timezone("Europe/Amsterdam")
        current_time = datetime.now(tz=local_zone).strftime("%H:%M:%S")

        print(f"-------- START {selected_city} ---------")

        # Check if the city is in the list of cities
        if selected_city == "hamburg":
            local_time: datetime = datetime.now(tz=local_zone)
            if local_time.hour >= 1:
                # Get the data from the selected city
                data_set = asyncio.run(provided_city.async_get_locations())
                # Upload the data to the database
                provided_city.upload_data(data_set, current_time)
            else:
                print(
                    "Hamburg: Not updating database, time between 00:00 and 01:00.",
                )
        else:
            # Get the data from the selected city
            data_set = asyncio.run(provided_city.async_get_locations())
            # Upload the data to the database
            provided_city.upload_data(data_set, current_time)

        # Wait for the next update
        print(f"--------- DONE {selected_city} ---------")
        time.sleep(60 * wait_time)


def main(argv: list[str] | None = None) -> int:
    """Default to offline help; source inspection never loads core credentials."""
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--fetch",
        choices=("amsterdam", "hamburg"),
        help="Fetch one source once and print its record count; no database writes.",
    )
    modes.add_argument(
        "--legacy",
        action="store_true",
        help="Run the continuous legacy MySQL writer using CITY and WAIT_TIME.",
    )
    args = parser.parse_args(argv)
    if args.fetch:
        city = CityProvider().provide_city(args.fetch)
        records = asyncio.run(city.async_get_locations())
        print(f"{len(records)} source records retrieved; no data written.")
        return 0
    if args.legacy:
        load_dotenv()
        selected_city = os.getenv("CITY", "").lower()
        if selected_city not in ("amsterdam", "hamburg"):
            parser.error("CITY must be amsterdam or hamburg for --legacy")
        try:
            wait_time = int(os.getenv("WAIT_TIME", ""))
        except ValueError:
            parser.error("WAIT_TIME must be a positive integer for --legacy")
        if wait_time <= 0:
            parser.error("WAIT_TIME must be a positive integer for --legacy")
        run_legacy(selected_city, wait_time)
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
