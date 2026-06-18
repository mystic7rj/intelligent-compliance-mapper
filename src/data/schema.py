# -*- coding: utf-8 -*-
"""SQLAlchemy 2.0 ORM models for the Compliance Mapper database.

PATTERN: ORM (Object-Relational Mapping) — maps Python classes to database tables
Defines three tables — frameworks, control_families, and controls — with
UUID primary keys, created_at/updated_at timestamps, and proper foreign-key
relationships with cascade deletes.

PATTERN: Data Integrity — uses constraints and cascades for referential integrity
- Unique constraints prevent duplicate frameworks and controls
- Cascade deletes ensure orphaned records are automatically cleaned up
- Timestamps track record creation and modification for auditing
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class FrameworkTable(Base):
    """A compliance framework (e.g. NIST CSF, ISO 27001).

    Attributes:
        id: UUID primary key.
        name: Unique framework name.
        version: Framework version string.
        description: Optional long-form description.
        created_at: Row creation timestamp (server-side default).
        updated_at: Last-modification timestamp (auto-updated).
        families: Related control families (cascade delete).
    """

    __tablename__ = "frameworks"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_framework_name_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        default=uuid.uuid4,
        primary_key=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    families: Mapped[list[ControlFamilyTable]] = relationship(
        "ControlFamilyTable",
        back_populates="framework",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # noqa: D105
        return f"<FrameworkTable(name={self.name!r}, version={self.version!r})>"


class ControlFamilyTable(Base):
    """A group of related controls under one framework function.

    Attributes:
        id: UUID primary key.
        framework_id: FK to parent framework (cascade delete).
        function_name: Human-readable function name (e.g. 'Identify').
        function_id: Short identifier (e.g. 'ID').
        description: Optional description.
        created_at: Row creation timestamp.
        updated_at: Last-modification timestamp.
        framework: Parent framework relationship.
        controls: Child controls (cascade delete).
    """

    __tablename__ = "control_families"

    id: Mapped[uuid.UUID] = mapped_column(
        default=uuid.uuid4,
        primary_key=True,
    )
    framework_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("frameworks.id", ondelete="CASCADE"),
        nullable=False,
    )
    function_name: Mapped[str] = mapped_column(String(100), nullable=False)
    function_id: Mapped[str] = mapped_column(String(10), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    framework: Mapped[FrameworkTable] = relationship(
        "FrameworkTable",
        back_populates="families",
    )
    controls: Mapped[list[ControlTable]] = relationship(
        "ControlTable",
        back_populates="family",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # noqa: D105
        return (
            f"<ControlFamilyTable(function_name={self.function_name!r}, "
            f"function_id={self.function_id!r})>"
        )


class ControlTable(Base):
    """A single compliance control within a control family.

    Attributes:
        id: UUID primary key.
        family_id: FK to parent control family (cascade delete).
        control_id: Human-readable control identifier (e.g. 'ID.AM-1').
        title: Control title.
        description: Detailed control description.
        priority: Priority level (low / medium / high / critical).
        created_at: Row creation timestamp.
        updated_at: Last-modification timestamp.
        family: Parent control-family relationship.
    """

    __tablename__ = "controls"
    __table_args__ = (
        UniqueConstraint("family_id", "control_id", name="uq_family_control_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        default=uuid.uuid4,
        primary_key=True,
    )
    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("control_families.id", ondelete="CASCADE"),
        nullable=False,
    )
    control_id: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    family: Mapped[ControlFamilyTable] = relationship(
        "ControlFamilyTable",
        back_populates="controls",
    )

    def __repr__(self) -> str:  # noqa: D105
        return f"<ControlTable(control_id={self.control_id!r}, title={self.title!r})>"
