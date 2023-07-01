"""Python script for Garages Amsterdam data."""
import datetime

import pymysql
import pytz
from odp_amsterdam import Garage, ODPAmsterdam

from app.database import connection, cursor
from app.helpers import get_unique_number

GEOCODE = "NL-NH"
PHONE_CODE = "020"


async def async_get_garages() -> Garage:
    """Get garage data from API.

    Returns
    -------
        list: List of garages.
    """
    async with ODPAmsterdam() as client:
        garages: Garage = await client.all_garages()
        return garages


def check_value(value: int) -> int:
    """Replace None values with 0.

    Args:
    ----
        value (int): Value to check.
    """
    if value is None:
        return 0
    return value


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
            sql = """INSERT INTO `parking_offstreet` (id, name, country_id, province_id, municipality, state, free_space_short, free_space_long, short_capacity, long_capacity, availability_pct, parking_type, longitude, latitude, visibility, created_at, updated_at)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY
                     UPDATE id=values(id),
                            name=values(name),
                            state=values(state),
                            free_space_short=values(free_space_short),
                            free_space_long=values(free_space_long),
                            short_capacity=values(short_capacity),
                            long_capacity=values(long_capacity),
                            availability_pct=values(availability_pct),
                            longitude=values(longitude),
                            latitude=values(latitude),
                            updated_at=values(updated_at)"""  # noqa: E501
            val = (
                location_id,
                str(item.garage_name),
                int(157),
                int(8),
                str(municipality),
                str(item.state),
                check_value(item.free_space_short),
                check_value(item.free_space_long),
                check_value(item.short_capacity),
                check_value(item.long_capacity),
                item.availability_pct,
                "garage",
                float(item.longitude),
                float(item.latitude),
                bool(True),
                datetime.datetime.now(tz=pytz.timezone("Europe/Amsterdam")),
                datetime.datetime.now(tz=pytz.timezone("Europe/Amsterdam")),
            )
            cursor.execute(sql, val)
        connection.commit()
    except pymysql.Error as error:
        print(f"MySQL error: {error}")
    finally:
        print(f"{time} - KLAAR met updaten van database")
