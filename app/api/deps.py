"""Common dependencies for API routes."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.db.session import SessionLocal


def get_db_session() -> Iterator[Session]:
    """Yield a database session for FastAPI dependencies."""

    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


__all__ = ["get_db_session"]
