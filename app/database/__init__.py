"""Setup database connection."""
import datetime
import os
from pathlib import Path

import pymysql
from dotenv import load_dotenv

load_dotenv()
env_path = Path() / ".env"
load_dotenv(dotenv_path=env_path)

# MYSQL credentials
DB_SERVER = os.getenv("DB_SERVER")
DB_PORT = int(os.getenv("DB_PORT"))
DATABASE = os.getenv("DATABASE")
DB_USERNAME = os.getenv("DB_USERNAME")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Connect to MySQL
connection = pymysql.connect(
    host=DB_SERVER,
    port=DB_PORT,
    user=DB_USERNAME,
    password=DB_PASSWORD,
    database=DATABASE,
)
cursor = connection.cursor()


def test_connection() -> None:
    """Test the connection with MySQL Database."""
    try:
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        print(f"Database version: {version[0]}")
    except pymysql.Error as error:
        print(f"MySQL error: {error}")
    finally:
        cursor.close()
        connection.close()


def purge_database(municipality: str, time: datetime) -> None:
    """Purge the database tabel.

    Args:
    ----
        municipality (str): Name of the municipality.
        time (datetime): Current time.
    """
    print(f"{time} - START met leeggooien van de database")
    try:
        sql = "DELETE FROM `parking_offstreet` WHERE `municipality`=%s"
        cursor.execute(sql, municipality)
        connection.commit()
    except pymysql.Error as error:
        print(f"MySQL error: {error}")
    finally:
        print(f"{time} - Klaar met leegmaken van de database")
