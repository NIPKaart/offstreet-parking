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