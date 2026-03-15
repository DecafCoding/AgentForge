"""
Alembic environment configuration.

Wired for async migrations using SQLAlchemy's async engine with the asyncpg
driver. The DATABASE_URL environment variable is read directly, converting
the plain postgresql:// scheme to postgresql+asyncpg:// as required by
SQLAlchemy's async dialect.
"""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

# Alembic Config object — provides access to values in alembic.ini.
config = context.config

# Set up Python logging from the alembic.ini [loggers] section.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# We are not using SQLAlchemy ORM models, so target_metadata is None.
# Alembic will not autogenerate migrations from models — all migrations
# are written by hand in src/db/migrations/versions/.
target_metadata = None


def _get_async_url() -> str:
    """Build the SQLAlchemy async connection URL from the environment.

    Converts ``postgresql://`` to ``postgresql+asyncpg://`` so SQLAlchemy
    can route to the asyncpg dialect. The env var takes precedence over
    whatever placeholder is set in alembic.ini.
    """
    url = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/agentforge",
    )
    return url.replace("postgresql://", "postgresql+asyncpg://", 1)


def run_migrations_offline() -> None:
    """Run migrations without a live database connection.

    Useful for generating SQL scripts to review before applying.
    """
    context.configure(
        url=_get_async_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: object) -> None:
    """Execute pending migrations on the provided sync connection."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations against a live database using an async engine."""
    connectable = create_async_engine(
        _get_async_url(),
        # NullPool avoids connection reuse — correct for migration scripts
        # that run once and exit.
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
