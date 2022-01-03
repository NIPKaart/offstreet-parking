"""Scrape tool for parking garage into NIPKaart system."""
import cities.amsterdam as amsterdam

import asyncio, datetime, time, os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()
env_path = Path('.')/'.env'
load_dotenv(dotenv_path=env_path)

CITY        = os.getenv("CITY")
WAIT_TIME   = int(os.getenv("WAIT_TIME"))

testing = False

if __name__ == '__main__':
    print("--- Start scraping program ---")
    if testing:
        if CITY == "Amsterdam":
            data_set = asyncio.run(amsterdam.async_get_garages())
            count: int
            for index, item in enumerate(data_set, 1):
                count = index
                print(item)
            print(f"{count} parkeergarages gevonden")
            amsterdam.test_connection()
    else:
        while True:
            TIME = datetime.datetime.now().strftime('%H:%M:%S')
            print(f'-------- START-{CITY} ---------')
            if CITY == "Amsterdam":
                data_set = asyncio.run(amsterdam.async_get_garages())
                amsterdam.update_database(data_set, CITY, TIME)
            print(f'--------- DONE-{CITY} ---------')
            time.sleep(60 * WAIT_TIME)