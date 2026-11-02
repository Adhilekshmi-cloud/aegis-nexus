from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

database_url = make_url(settings.database_url)
if database_url.get_backend_name() == "sqlite" and database_url.database not in {None, ":memory:"}:
    Path(database_url.database).parent.mkdir(parents=True, exist_ok=True)

Base = declarative_base()
engine = create_engine(database_url, connect_args={"check_same_thread": False})
session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_session():
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
