"""Python script for Park and Ride Hamburg data."""
import datetime
import json

from hamburg import ParkAndRide, UDPHamburg


async def async_get_parking(bulk="false"):
    """Get parking data from API."""
    async with UDPHamburg() as client:
        parking: ParkAndRide = await client.park_and_ride(bulk=bulk)
        return parking


def update_database(data_set, municipality, time, connection, cursor):
    """Update the database with new data."""
    # purge_database(municipality, time)
    print(f"{time} - START bijwerken van database met nieuwe data")
    try:
        for item in data_set:
            sql = """INSERT INTO `parking_garages` (id, name, country_id, province_id, municipality, free_space_short, short_capacity, availability_pct, prices, url, longitude, latitude, visibility, created_at, updated_at)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY
                     UPDATE id=values(id),
                            name=values(name),
                            state=values(state),
                            free_space_short=values(free_space_short),
                            short_capacity=values(short_capacity),
                            availability_pct=values(availability_pct),
                            prices=values(prices),
                            longitude=values(longitude),
                            latitude=values(latitude),
                            updated_at=values(updated_at)"""
            val = (
                str(item.spot_id),
                str(item.name),
                int(83),
                int(14),
                str(municipality),
                item.free_space,
                item.capacity,
                item.availability_pct,
                json.dumps(item.tickets),
                item.url,
                float(item.longitude),
                float(item.latitude),
                bool(True),
                (datetime.datetime.now()),
                item.updated_at,
            )
            # print(val)
            cursor.execute(sql, val)
        connection.commit()
    except Exception as error:
        print(f"MySQL error: {error}")
    finally:
        print(f"{time} - KLAAR met updaten van database")
