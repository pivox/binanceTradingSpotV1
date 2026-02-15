from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tradebot.config.settings import Settings
from tradebot.infra.db.models import Base


def create_db_engine(settings: Settings):
    return create_engine(settings.database_url, pool_pre_ping=True)


def create_session_factory(settings: Settings):
    engine = create_db_engine(settings)
    # Ensure all mapped tables exist so API endpoints don't fail on fresh DBs.
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)
