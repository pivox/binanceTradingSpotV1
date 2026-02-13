from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tradebot.config.settings import Settings


def create_db_engine(settings: Settings):
    return create_engine(settings.database_url, pool_pre_ping=True)


def create_session_factory(settings: Settings):
    engine = create_db_engine(settings)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)
