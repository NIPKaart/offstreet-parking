"""Upload tool for off-street parking into NIPKaart system."""
import asyncio
import os
import time
from datetime import datetime
from pathlib import Path

import pytz
from dotenv import load_dotenv

from app.cities import amsterdam, hamburg
from app.database import test_connection
from app.helpers import test_data

load_dotenv()
env_path = Path(".") / ".env"
load_dotenv(dotenv_path=env_path)

CITY = os.getenv("CITY")
WAIT_TIME = int(os.getenv("WAIT_TIME"))

TESTING = False


if __name__ == "__main__":
    print("--- Start upload program ---")
    if TESTING:
        if CITY == "Amsterdam":
            data = asyncio.run(amsterdam.async_get_garages())
            test_data(data)
        elif CITY == "Hamburg":
            data = asyncio.run(hamburg.async_get_parking())
            test_data(data)
        test_connection()
    else:
        while True:
            CURRENT_TIME = datetime.now().strftime("%H:%M:%S")
            print(f"-------- START {CITY} ---------")
            if CITY == "Amsterdam":
                data = asyncio.run(amsterdam.async_get_garages())
                amsterdam.update_database(data, CITY, CURRENT_TIME)
            elif CITY == "Hamburg":
                local_zone = pytz.timezone("Europe/Amsterdam")
                local_time: datetime = datetime.now(tz=local_zone)

                if local_time.hour >= 1:
                    data = asyncio.run(hamburg.async_get_parking(bulk="true"))
                    hamburg.update_database(data, CITY, CURRENT_TIME)
                else:
                    print(
                        "Hamburg: Not updating database, time is between: 00:00 and 01:00."
                    )
            print(f"--------- DONE {CITY} ---------")
            time.sleep(60 * WAIT_TIME)
