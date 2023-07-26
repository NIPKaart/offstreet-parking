"""Upload tool for off-street parking into NIPKaart system."""
import asyncio
import os
import time
from datetime import datetime
from pathlib import Path

import pytz
from dotenv import load_dotenv

from app.cities.germany import hamburg
from app.cities.netherlands import amsterdam
from app.database import test_connection
from app.helpers import test_data

CITY = os.getenv("CITY")
WAIT_TIME = int(os.getenv("WAIT_TIME"))
TESTING = False


class CityProvider:
    """Class to provide the correct city."""

    def provide_city(self, city_name: str) -> object:
        """Provide the correct city.

        Args:
        ----
            city_name (str): The city to provide.

        Returns:
        -------
            city_class (class): The class of the city.
        """
        match city_name:
            case "amsterdam":
                city_class = amsterdam.Municipality()
            case "hamburg":
                city_class = hamburg.Municipality()
            case _:
                msg = f"{city_name} is not a valid city."
                raise ValueError(msg)
        return city_class


if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    env_path = Path() / ".env"
    load_dotenv(dotenv_path=env_path)

    cp = CityProvider()
    print("--- Start program ---")
    print()

    # Get the city from the environment variables
    selected_city: str = os.getenv("CITY").lower()
    provided_city = cp.provide_city(selected_city)

    if TESTING:
        data_set = asyncio.run(provided_city.async_get_locations())
        test_data(data_set)
        test_connection()
    else:
        while True:
            LOCAL_ZONE = pytz.timezone("Europe/Amsterdam")
            CURRENT_TIME = datetime.now(tz=LOCAL_ZONE).strftime("%H:%M:%S")
            print(f"-------- START {selected_city} ---------")

            # Get the data from the selected city
            data_set = asyncio.run(provided_city.async_get_locations())

            # Upload the data to the database
            if selected_city in ["hamburg"]:
                local_time: datetime = datetime.now(tz=LOCAL_ZONE)
                if local_time.hour >= 1:
                    provided_city.upload_data(data_set, CURRENT_TIME)
                else:
                    print(
                        "Hamburg: Not updating database, time between 00:00 and 01:00.",
                    )
            else:
                provided_city.upload_data(data_set, CURRENT_TIME)
            print(f"--------- DONE {selected_city} ---------")
            time.sleep(60 * WAIT_TIME)
