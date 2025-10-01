"""SQLAlchemy session management."""
from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.obs import instrument_sqlalchemy_engine

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
if settings.enable_tracing:
    instrument_sqlalchemy_engine(engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_session() -> Session:
    """Provide a transactional scope around a series of operations."""
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
