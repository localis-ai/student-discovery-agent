from typing import Generator

from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, create_engine

from app.core.config import settings

# Create SQLAlchemy engine with SQLModel
engine = create_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),
    pool_pre_ping=True,
    echo=False,  # Disable SQL query logging
)

# Create SessionLocal class for SQLModel
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get database session.
    Use this in FastAPI dependency injection.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session() -> Session:
    """
    Get a database session directly.
    Use this in service classes that manage their own database transactions.
    """
    return SessionLocal()


# Function to check if database exists and has tables
def check_database_exists() -> bool:
    """Check if database exists and has any tables"""
    try:
        # Try to connect and check for any existing tables
        from sqlalchemy import text

        with engine.connect() as conn:
            result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' LIMIT 1"))
            has_tables = result.fetchone() is not None
            return has_tables
    except Exception:
        return False


# Function to check if specific table exists
def table_exists(table_name: str) -> bool:
    """Check if a specific table exists"""
    try:
        from sqlalchemy import text

        with engine.connect() as conn:
            # Try exact match first
            result = conn.execute(
                text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :table_name)"),
                {"table_name": table_name},
            )
            exists = result.fetchone()[0]

            if not exists:
                # Also try lowercase version
                result2 = conn.execute(
                    text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND lower(table_name) = lower(:table_name))"),
                    {"table_name": table_name},
                )
                exists = result2.fetchone()[0]

            if not exists:
                # Debug: list all tables to see what's actually there
                all_tables_result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"))
                [row[0] for row in all_tables_result.fetchall()]

            return exists
    except Exception:
        return False


# Function to create all tables
def create_tables() -> None:
    """Create all database tables from SQLModel models"""
    # Import all models to register them with SQLAlchemy registry
    # Create tables using SQLAlchemy registry (correct way for SQLModel)
    from sqlmodel import SQLModel

    from app.models import (
        User,
        Version,
    )

    try:
        # Use SQLModel.metadata.create_all() - this includes all registered tables
        from app.modules.common.utils.logging import logger

        SQLModel.metadata.create_all(bind=engine)
    except Exception:
        logger.error("[Database] Error creating tables")
        raise


# Function to initialize database on startup
def init_database() -> None:
    """Check database existence and create tables if needed"""
    import time

    # Wait a bit for database to be fully ready
    time.sleep(2)

    max_retries = 3
    for attempt in range(max_retries):
        try:
            create_tables()
            return
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(2)

    # If all retries failed, try one more time
    create_tables()
