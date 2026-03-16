"""
Database session dependency.

Provides `get_db` — a reusable FastAPI dependency that yields a SQLAlchemy
session and ensures it is closed after the request completes.

Usage:
    from api.dependencies.db import get_db

    @router.get("/example")
    def example(db: Session = Depends(get_db)):
        ...

Requirements: 7.4
"""

from typing import Generator

from sqlalchemy.orm import Session


def get_db() -> Generator[Session, None, None]:
    """
    Yield a database session and close it when the request is done.

    Imports SessionLocal lazily from api.main to avoid circular imports
    while keeping a single engine/session-factory definition.

    Requirements: 7.4
    """
    from api.main import SessionLocal  # lazy import to avoid circular dependency

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
