from __future__ import annotations

import threading
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tradebot.config.settings import Settings
from tradebot.infra.db.models import Base

_engine = None
_session_factory: sessionmaker | None = None
_lock = threading.Lock()


def create_db_engine(settings: Settings):
    return create_engine(settings.database_url, pool_pre_ping=True)


def create_session_factory(settings: Settings) -> sessionmaker:
    global _engine, _session_factory
    if _session_factory is None:
        with _lock:
            if _session_factory is None:
                _engine = create_db_engine(settings)
                Base.metadata.create_all(bind=_engine)
                _session_factory = sessionmaker(
                    bind=_engine, autocommit=False, autoflush=False
                )
    return _session_factory
