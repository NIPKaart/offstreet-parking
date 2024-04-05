"""Python script for Park and Ride Hamburg data."""

import datetime
import json

import pymysql
import pytz
from hamburg import ParkAndRide, UDPHamburg

from app.cities import City
from app.database import connection, cursor
from app.helpers import get_unique_number


class Municipality(City):
    """Manage the location data of Hamburg."""

    def __init__(self) -> None:
        """Initialize the class."""
        super().__init__(
            name="Hamburg",
            country="Germany",
            country_id=83,
            province_id=14,
            geo_code="DE-HH",
            phone_code="040",
        )
        self.limit = 40

    async def async_get_locations(self) -> ParkAndRide:
        """Get parking data from API.

        Args:
        ----
            limit (int): Number of garages to retrieve.

        """
        async with UDPHamburg() as client:
            parking: ParkAndRide = await client.park_and_rides(limit=self.limit)
            print(f"{self.name} - data has been retrieved")
            return parking

    def upload_data(self, data_set: list, time: datetime) -> None:
        """Update the database with new data.

        Args:
        ----
            data_set (list): List of garages.
            time (datetime): Current time.

        """
        # purge_database(self.name, time)  # noqa: ERA001
        print(f"{time} - {self.name}: START updating database with new data")
        try:
            connection.ping(reconnect=True)
            for item in data_set:
                location_id = f"{self.geo_code}-{self.phone_code}-{get_unique_number(item.latitude, item.longitude)}"  # noqa: E501
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
                    int(self.country_id),
                    int(self.province_id),
                    str(self.name),
                    item.free_space,
                    item.capacity,
                    item.availability_pct,
                    "parkandride",
                    json.dumps(item.tickets),
                    item.url,
                    float(item.longitude),
                    float(item.latitude),
                    True,
                    datetime.datetime.now(tz=pytz.timezone("Europe/Berlin")),
                    item.updated_at,
                )
                cursor.execute(sql, val)
            connection.commit()
        except pymysql.Error as error:
            print(f"MySQL error: {error}")
        finally:
            print(f"{time} - {self.name}: DONE with database update")
