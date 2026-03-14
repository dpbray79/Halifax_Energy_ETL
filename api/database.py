"""
database.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Halifax Energy Forecasting API — Database Connection Module
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SQLAlchemy engine, session factory, and dependency injection for FastAPI

UPDATED FOR SUPABASE POSTGRESQL:
  - Removed SQL Server/pyodbc fast_executemany event listener
  - Now uses PostgreSQL with psycopg2
  - Connection pooling optimized for Supabase
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import logging

from .config import settings

logger = logging.getLogger(__name__)

# ── SQLAlchemy Setup ──────────────────────────────────────────────────────────

# Create database engine (PostgreSQL via Supabase)
engine = create_engine(
    settings.database_url,
    echo=False,  # Set to True for SQL query logging
    pool_pre_ping=True,  # Verify connections before using
    pool_size=5,  # Reduced for Supabase free tier
    max_overflow=10,
    pool_recycle=3600,  # Recycle connections after 1 hour
)


# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for ORM models
Base = declarative_base()


# ── Dependency Injection ──────────────────────────────────────────────────────

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session.

    Usage:
        @app.get("/example")
        def read_example(db: Session = Depends(get_db)):
            result = db.query(SomeModel).all()
            return result
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Health Check ──────────────────────────────────────────────────────────────

def check_db_connection() -> bool:
    """
    Check if database is accessible.

    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
