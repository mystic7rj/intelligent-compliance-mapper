"""Alembic environment configuration for the Compliance Mapper.

Reads ``DATABASE_URL`` from the ``.env`` file and sets it on the Alembic
config so that migrations can run without hard-coded connection strings.
Imports ``Base.metadata`` from the ORM schema for autogenerate support.
"""

from __future__ import annotations

import os

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from src.data.schema import Base

# Load .env so DATABASE_URL is available
load_dotenv()

# Alembic Config object
config = context.config

# Override sqlalchemy.url from environment
database_url = os.getenv("DATABASE_URL", "sqlite:///./compliance.db")
config.set_main_option("sqlalchemy.url", database_url)

# Target metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with just a URL and not an Engine.
    Calls to ``context.execute()`` emit the given SQL string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Creates an Engine and associates a connection with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
