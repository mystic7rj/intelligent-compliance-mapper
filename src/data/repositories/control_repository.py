"""Repository for control data access.

Provides read and bulk-write operations for ``ControlTable`` entities.
All methods receive their ``Session`` via dependency injection — the
repository never creates or manages its own session.  Contains zero
business logic; only data access and input validation.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.data.schema import ControlTable
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ControlRepositoryError(Exception):
    """Raised when a control repository operation fails."""


class ControlRepository:
    """Data-access repository for compliance controls.

    Args:
        session: An active SQLAlchemy ``Session`` (injected by caller).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_framework(self, framework_id: uuid.UUID) -> list[ControlTable]:
        """Return all controls belonging to a given framework.

        Joins through the ``control_families`` table to locate controls
        whose parent family belongs to the specified framework.

        Args:
            framework_id: UUID of the parent framework.

        Returns:
            A list of ``ControlTable`` rows (may be empty).
        """
        from src.data.schema import ControlFamilyTable

        stmt = (
            select(ControlTable)
            .join(ControlFamilyTable, ControlTable.family_id == ControlFamilyTable.id)
            .where(ControlFamilyTable.framework_id == framework_id)
            .order_by(ControlTable.control_id)
        )
        return list(self._session.execute(stmt).scalars().all())

    def get_by_id(self, control_id: uuid.UUID) -> ControlTable | None:
        """Look up a control by its UUID primary key.

        Args:
            control_id: The UUID of the control.

        Returns:
            The matching ``ControlTable``, or ``None`` if not found.
        """
        stmt = select(ControlTable).where(ControlTable.id == control_id)
        return self._session.execute(stmt).scalars().first()

    def save_bulk(self, controls: list[ControlTable]) -> list[ControlTable]:
        """Persist multiple controls in a single flush.

        Args:
            controls: A list of ``ControlTable`` instances to persist.

        Returns:
            The persisted (and flushed) controls.

        Raises:
            ControlRepositoryError: If the list is empty or any control
                has missing required fields.
        """
        if not controls:
            msg = "Controls list cannot be empty"
            raise ControlRepositoryError(msg)

        for ctrl in controls:
            if not ctrl.control_id or not ctrl.control_id.strip():
                msg = "Control control_id cannot be empty"
                raise ControlRepositoryError(msg)
            if not ctrl.title or not ctrl.title.strip():
                msg = "Control title cannot be empty"
                raise ControlRepositoryError(msg)

        self._session.add_all(controls)
        self._session.flush()

        logger.info(
            "Controls bulk-saved",
            extra={"count": len(controls)},
        )
        return controls
