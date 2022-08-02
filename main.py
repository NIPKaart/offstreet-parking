"""Scrape tool for parking garage into NIPKaart system."""
import asyncio
import datetime
import os
import time
from pathlib import Path

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
    print("--- Start scraping program ---")
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
            TIME = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"-------- START {CITY} ---------")
            if CITY == "Amsterdam":
                data = asyncio.run(amsterdam.async_get_garages())
                amsterdam.update_database(data, CITY, TIME)
            elif CITY == "Hamburg":
                data = asyncio.run(hamburg.async_get_parking(bulk="true"))
                hamburg.update_database(data, CITY, TIME)
            print(f"--------- DONE {CITY} ---------")
            time.sleep(60 * WAIT_TIME)
