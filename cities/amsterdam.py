"""Python script for Garages Amsterdam data."""
import datetime
from garages_amsterdam import Garage, GaragesAmsterdam

from database import connection, cursor

async def async_get_garages():
    """Get garage data from API."""
    async with GaragesAmsterdam() as client:
        garages: Garage = await client.all_garages()
        return garages

def check_value(value):
    """Check on null values."""
    if value == "":
        return 0
    else:
        return value

def purge_database(city, time):
    """Purge the database tabel."""
    print(f'{time} - START met leeggooien van de database')
    try:
        sql = "DELETE FROM `parking_garages` WHERE `city`=%s"
        cursor.execute(sql, city)
        connection.commit()
    except Exception as e:
        print(f'MySQL error: {e}')
    finally:
        print(f'{time} - Klaar met leegmaken van de database')

def update_database(data_set, city, time):
    """Update the database with new data."""
    # purge_database(city)
    print(f'{time} - START bijwerken van database met nieuwe data')
    count=1
    try:
        for item in data_set:
            sql = """INSERT INTO `parking_garages` (id, name, city, state, free_space_short, free_space_long, short_capacity, long_capacity, longitude, latitude, visibility, created_at, updated_at) 
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY 
                     UPDATE id=values(id),
                            name=values(name),
                            state=values(state),
                            free_space_short=values(free_space_short),
                            free_space_long=values(free_space_long),
                            short_capacity=values(short_capacity),
                            long_capacity=values(long_capacity),
                            longitude=values(longitude),
                            latitude=values(latitude),
                            updated_at=values(updated_at)"""
            val = (count, str(item.garage_name), str(city) ,str(item.state), check_value(item.free_space_short), check_value(item.free_space_long), check_value(item.short_capacity), check_value(item.long_capacity), float(item.longitude), float(item.latitude), bool(True), (datetime.datetime.now()), (datetime.datetime.now()))
            cursor.execute(sql, val)
            count+=1
        connection.commit()

    except Exception as e:
        print(f'MySQL error: {e}')
    finally:
        print(f'{time} - KLAAR met updaten van database')

def test_connection():
    """Test the connection with MySQL Database."""
    try:
        cursor.execute('SELECT VERSION()')
        version = cursor.fetchone()
        print(f'Database version: {version[0]}')
    except Exception as e:
        print(f'MySQL error: {e}')
    finally:
        cursor.close()
        connection.close()