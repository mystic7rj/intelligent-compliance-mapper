"""Repository for framework data access.

Provides CRUD operations for ``FrameworkTable`` entities.  All methods
receive their ``Session`` via dependency injection — the repository never
creates or manages its own session.  Contains zero business logic;
only data access and input validation.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.data.schema import FrameworkTable
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FrameworkRepositoryError(Exception):
    """Raised when a framework repository operation fails."""


class FrameworkRepository:
    """Data-access repository for compliance frameworks.

    Args:
        session: An active SQLAlchemy ``Session`` (injected by caller).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_all(self) -> list[FrameworkTable]:
        """Return every framework in the database.

        Returns:
            A list of ``FrameworkTable`` rows (may be empty).
        """
        stmt = select(FrameworkTable).order_by(FrameworkTable.name)
        return list(self._session.execute(stmt).scalars().all())

    def get_by_name(self, name: str) -> FrameworkTable | None:
        """Look up a framework by its name.

        Args:
            name: The framework name to search for (case-sensitive).

        Returns:
            The matching ``FrameworkTable``, or ``None`` if not found.

        Raises:
            FrameworkRepositoryError: If *name* is empty or blank.
        """
        if not name or not name.strip():
            msg = "Framework name cannot be empty"
            raise FrameworkRepositoryError(msg)

        stmt = select(FrameworkTable).where(FrameworkTable.name == name.strip())
        return self._session.execute(stmt).scalars().first()

    def save(self, framework: FrameworkTable) -> FrameworkTable:
        """Persist a framework row (insert or update).

        The caller is responsible for committing the surrounding
        transaction.

        Args:
            framework: The ``FrameworkTable`` instance to persist.

        Returns:
            The persisted (and flushed) ``FrameworkTable``.

        Raises:
            FrameworkRepositoryError: If required fields are missing.
        """
        if not framework.name or not framework.name.strip():
            msg = "Framework name cannot be empty"
            raise FrameworkRepositoryError(msg)
        if not framework.version or not framework.version.strip():
            msg = "Framework version cannot be empty"
            raise FrameworkRepositoryError(msg)

        self._session.add(framework)
        self._session.flush()

        logger.info(
            "Framework saved",
            extra={"framework_name": framework.name, "framework_version": framework.version},
        )
        return framework

    def delete(self, framework_id: uuid.UUID) -> bool:
        """Delete a framework by its UUID primary key.

        Args:
            framework_id: The UUID of the framework to delete.

        Returns:
            ``True`` if the framework was found and deleted, ``False``
            otherwise.
        """
        stmt = select(FrameworkTable).where(FrameworkTable.id == framework_id)
        framework = self._session.execute(stmt).scalars().first()

        if framework is None:
            return False

        self._session.delete(framework)
        self._session.flush()

        logger.info(
            "Framework deleted",
            extra={"framework_id": str(framework_id)},
        )
        return True
