"""Python script for Park and Ride Hamburg data."""
import datetime
import json

import pymysql
import pytz
from hamburg import ParkAndRide, UDPHamburg

from app.database import connection, cursor
from app.helpers import get_unique_number

GEOCODE = "DE-HH"
PHONE_CODE = "040"


async def async_get_parking(bulk: str = "false") -> ParkAndRide:
    """Get parking data from API.

    Args:
    ----
        bulk (str): Get all data in one request.
    """
    async with UDPHamburg() as client:
        parking: ParkAndRide = await client.park_and_rides(bulk=bulk)
        return parking


def update_database(data_set: list, municipality: str, time: datetime) -> None:
    """Update the database with new data.

    Args:
    ----
        data_set (list): List of garages.
        municipality (str): Name of the municipality.
        time (datetime): Current time.
    """
    # purge_database(municipality, time)  # noqa: ERA001
    print(f"{time} - START bijwerken van database met nieuwe data")
    try:
        connection.ping(reconnect=True)
        for item in data_set:
            location_id = f"{GEOCODE}-{PHONE_CODE}-{get_unique_number(item.latitude, item.longitude)}"  # noqa: E501
            sql = """INSERT INTO `parking_offstreet` (id, name, country_id, province_id, municipality, free_space_short, short_capacity, availability_pct, parking_type, prices, url, longitude, latitude, visibility, created_at, updated_at)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY
                     UPDATE id=values(id),
                            name=values(name),
                            state=values(state),
                            free_space_short=values(free_space_short),
                            short_capacity=values(short_capacity),
                            availability_pct=values(availability_pct),
                            prices=values(prices),
                            longitude=values(longitude),
                            latitude=values(latitude),
                            updated_at=values(updated_at)"""  # noqa: E501
            val = (
                location_id,
                str(item.name),
                int(83),
                int(14),
                str(municipality),
                item.free_space,
                item.capacity,
                item.availability_pct,
                "parkandride",
                json.dumps(item.tickets),
                item.url,
                float(item.longitude),
                float(item.latitude),
                bool(True),
                datetime.datetime.now(tz=pytz.timezone("Europe/Berlin")),
                item.updated_at,
            )
            cursor.execute(sql, val)
        connection.commit()
    except pymysql.Error as error:
        print(f"MySQL error: {error}")
    finally:
        print(f"{time} - KLAAR met updaten van database")
