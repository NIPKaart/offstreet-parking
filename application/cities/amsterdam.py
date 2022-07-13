"""Python script for Garages Amsterdam data."""
import datetime

from garages_amsterdam import Garage, GaragesAmsterdam

# from ..database import purge_database


async def async_get_garages():
    """Get garage data from API."""
    async with GaragesAmsterdam() as client:
        garages: Garage = await client.all_garages()
        return garages


def check_value(value):
    """Check on null values."""
    if value == "":
        return 0
    return value


def update_database(data_set, municipality, time, connection, cursor):
    """Update the database with new data."""
    # purge_database(municipality, time)
    print(f"{time} - START bijwerken van database met nieuwe data")
    try:
        for item in data_set:
            location_id = f"ams-{item.garage_id[0:9]}-{item.garage_name.split(' ')[0]}"
            sql = """INSERT INTO `parking_garages` (id, name, country_id, province_id, municipality, state, free_space_short, free_space_long, short_capacity, long_capacity, availability_pct, longitude, latitude, visibility, created_at, updated_at)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY
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
                            updated_at=values(updated_at)"""
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
                float(item.longitude),
                float(item.latitude),
                bool(True),
                (datetime.datetime.now()),
                (datetime.datetime.now()),
            )
            cursor.execute(sql, val)
        connection.commit()
    except Exception as error:
        print(f"MySQL error: {error}")
    finally:
        print(f"{time} - KLAAR met updaten van database")
