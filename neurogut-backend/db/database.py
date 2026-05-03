"""
NEUROGUT -- Database Engine & Session
=======================================
Single connection string here -- swap SQLite -> PostgreSQL by changing DATABASE_URL.
"""

import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# ---------------------------------------------------------------------------
# Database URL -- change ONLY this line to swap to PostgreSQL:
#   DATABASE_URL = "postgresql+psycopg2://user:pass@host:5432/neurogut"
# ---------------------------------------------------------------------------
_db_dir = Path(__file__).resolve().parent
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{_db_dir / 'neurogut.db'}"
)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency -- yields a DB session, auto-closes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
