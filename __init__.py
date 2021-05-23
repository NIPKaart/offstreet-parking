import datetime, aiohttp, asyncio, garages_amsterdam, os, pymysql, time

from dotenv import load_dotenv
from pathlib import Path

load_dotenv()
env_path = Path('.')/'.env'
load_dotenv(dotenv_path=env_path)

# MYSQL credentials
DB_SERVER   = os.getenv("DB_SERVER")
DB_PORT     = int(os.getenv("DB_PORT"))
DATABASE    = os.getenv("DATABASE")
DB_USERNAME = os.getenv("DB_USERNAME")
DB_PASSWORD = os.getenv("DB_PASSWORD")

SLEEP_TIME = 60 * 10    # gelijk aan 10 minuten

# Connect to MySQL
connection = pymysql.connect(host=DB_SERVER, port=DB_PORT, user=DB_USERNAME, password=DB_PASSWORD, database=DATABASE)
cursor = connection.cursor()

async def async_get_garages():
    """Get garage data from API."""
    async with aiohttp.ClientSession() as client:
        return await garages_amsterdam.get_garages(client)

def check_value(value):
    """Check on null values."""
    if value == "":
        return 0
    else:
        return value

def update_database(data_set):
    """Update the database with new data."""
    print(f'{TIME} - START bijwerken van database met nieuwe data')
    count=1
    try:
        for item in data_set:
            sql = """INSERT INTO `garages_amsterdam` (id, name, state, free_space_short, free_space_long, short_capacity, long_capacity, longitude, latitude, created_at, updated_at) 
                     VALUES (%s, %s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY 
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
            val = (count, str(item.garage_name), str(item.state), check_value(item.free_space_short), check_value(item.free_space_long), check_value(item.short_capacity), check_value(item.long_capacity), float(item.longitude), float(item.latitude), (datetime.datetime.now()), (datetime.datetime.now()))
            cursor.execute(sql, val)
            count+=1
        connection.commit()

    except Exception as e:
        print(f'MySQL error: {e}')
    finally:
        print(f'{TIME} - KLAAR met updaten van database')

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

if __name__ == '__main__':
    print("start scrape program")
    # data_set = asyncio.run(async_get_garages())
    # test_connection()
    while True:
        TIME = datetime.datetime.now().strftime('%H:%M:%S')
        print(f'----------START----------')
        update_database(asyncio.run(async_get_garages()))
        print(f'----------DONE----------')
        time.sleep(SLEEP_TIME)