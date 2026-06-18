# -*- coding: utf-8 -*-
"""Database engine and session management for the Compliance Mapper.

PATTERN: Configuration from Environment — uses .env for flexible deployment
Reads ``DATABASE_URL`` from the ``.env`` file via python-dotenv.
Supports SQLite for local development and PostgreSQL for production.

PATTERN: Context Manager — get_session() provides automatic resource cleanup
Provides a ``get_session()`` context manager with proper commit / rollback
/ close semantics.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from src.utils.logger import get_logger

load_dotenv()

logger = get_logger(__name__)


class DatabaseConfigError(Exception):
    """Raised when the database configuration is missing or invalid."""


def get_engine(url: str | None = None) -> Engine:
    """Create and return a SQLAlchemy ``Engine``.

    If *url* is not provided, the ``DATABASE_URL`` environment variable is
    used.  SQLite URLs automatically receive ``check_same_thread=False``;
    PostgreSQL URLs enable ``pool_pre_ping``.

    Args:
        url: Optional database URL override.

    Returns:
        A configured ``Engine`` instance.

    Raises:
        DatabaseConfigError: If no URL is provided and ``DATABASE_URL`` is
            not set.
    """
    database_url = url or os.getenv("DATABASE_URL")

    if not database_url:
        msg = (
            "DATABASE_URL is not configured. "
            "Set it in the .env file or pass it explicitly."
        )
        raise DatabaseConfigError(msg)

    connect_args: dict[str, bool] = {}

    if database_url.startswith("sqlite"):
        # Apply resilient pool checks and recycle policy for SQLite too.
        connect_args["check_same_thread"] = False
        engine = create_engine(
            database_url,
            connect_args=connect_args,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False,
        )
    else:
        # Apply resilient pool checks and recycle policy for production DBs.
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False,
        )

    logger.info(
        "Database engine created",
        extra={"driver": engine.dialect.name},
    )
    return engine


@contextmanager
def get_session(engine: Engine) -> Generator[Session, None, None]:
    """Yield a database ``Session`` with automatic lifecycle management.

    Commits on clean exit, rolls back on any exception, and always
    closes the session afterwards.

    Args:
        engine: The SQLAlchemy ``Engine`` to bind.

    Yields:
        An active ``Session`` instance.
    """
    session = Session(bind=engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        # Always close the session explicitly to avoid leaked connections.
        session.close()


# Dispose an engine connection pool to release all DB resources explicitly.
def dispose_engine(engine: Engine) -> None:
    # Dispose pooled connections and detach pool state.
    engine.dispose()
