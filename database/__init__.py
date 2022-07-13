"""Setup database connection."""
import pymysql, os

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

# Connect to MySQL
connection = pymysql.connect(host=DB_SERVER, port=DB_PORT, user=DB_USERNAME, password=DB_PASSWORD, database=DATABASE)
cursor = connection.cursor()

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

def purge_database(municipality, time):
    """Purge the database tabel."""
    print(f'{time} - START met leeggooien van de database')
    try:
        sql = "DELETE FROM `parking_garages` WHERE `municipality`=%s"
        cursor.execute(sql, municipality)
        connection.commit()
    except Exception as e:
        print(f'MySQL error: {e}')
    finally:
        print(f'{time} - Klaar met leegmaken van de database')