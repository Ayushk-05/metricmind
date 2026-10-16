from collections.abc import Generator
from sqlalchemy.orm import Session

from app.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency providing a SQLAlchemy database session.

    Ensures that the session is reliably closed after the request is processed,
    preventing connection leaks.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
