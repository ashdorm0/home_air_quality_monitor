import os

from collections.abc import Generator

from dotenv import load_dotenv

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


# Load environment variables
load_dotenv()


DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")


if not all([DB_NAME, DB_USER, DB_PASSWORD]):
    raise RuntimeError(
        "Missing required database environment variables."
    )


DATABASE_URL = URL.create(
    drivername="postgresql+psycopg",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
)


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """
    Base class for SQLAlchemy models.
    """
    pass


def get_db() -> Generator[Session, None, None]:
    """
    Provide a database session for each API request.
    """

    with SessionLocal() as session:
        yield session


def check_database_connection() -> bool:
    """
    Verify PostgreSQL connectivity.
    """

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return True