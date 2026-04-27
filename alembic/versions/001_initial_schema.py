"""Initial schema — create frameworks, control_families, and controls tables.

Revision ID: 001
Create Date: 2026-03-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# Revision identifiers used by Alembic
revision: str = "001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Create the frameworks, control_families, and controls tables."""
    # --- frameworks ---
    op.create_table(
        "frameworks",
        sa.Column("id", sa.Uuid(), nullable=False, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("name", "version", name="uq_framework_name_version"),
    )
    op.create_index("ix_frameworks_name", "frameworks", ["name"])

    # --- control_families ---
    op.create_table(
        "control_families",
        sa.Column("id", sa.Uuid(), nullable=False, primary_key=True),
        sa.Column(
            "framework_id",
            sa.Uuid(),
            sa.ForeignKey("frameworks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("function_name", sa.String(100), nullable=False),
        sa.Column("function_id", sa.String(10), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- controls ---
    op.create_table(
        "controls",
        sa.Column("id", sa.Uuid(), nullable=False, primary_key=True),
        sa.Column(
            "family_id",
            sa.Uuid(),
            sa.ForeignKey("control_families.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("control_id", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("priority", sa.String(20), server_default="medium"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("family_id", "control_id", name="uq_family_control_id"),
    )
    op.create_index("ix_controls_control_id", "controls", ["control_id"])


def downgrade() -> None:
    """Drop tables in reverse dependency order."""
    op.drop_table("controls")
    op.drop_table("control_families")
    op.drop_table("frameworks")
