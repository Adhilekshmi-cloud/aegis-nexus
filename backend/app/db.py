from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.app.config import settings

Base = declarative_base()
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_session():
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
