import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL


# Load environment variables from .env
load_dotenv()


# Read database configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")


# Ensure required configuration is present
if not all([DB_NAME, DB_USER, DB_PASSWORD]):
    raise RuntimeError(
        "Missing required database environment variables."
    )


# Construct the PostgreSQL connection URL
DATABASE_URL = URL.create(
    drivername="postgresql+psycopg",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
)


# Create SQLAlchemy database engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


def check_database_connection() -> bool:
    """
    Check whether PostgreSQL is accessible.

    Returns True if the database responds successfully.
    Raises an exception if the connection fails.
    """

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return True