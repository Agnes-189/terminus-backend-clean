import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# 1. Add app directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# 2. Import application configuration and Base metadata
from app.core.config import settings
from app.core.database import Base

# Ensure all database model modules are imported so metadata populates
import app.models  # noqa: F401

config = context.config

# 3. Interpret the config file for Python logging
if config.config_file_name:
    fileConfig(config.config_file_name)

# 4. Bind SQLAlchemy Base Metadata for autogenerate detection
target_metadata = Base.metadata


def get_url():
    """Dynamically retrieve database connection string from environment settings."""
    return settings.DATABASE_URL


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode without an active DB engine."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with a direct DB connection."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()

    # Prevent SQLite table lock issues during test runs
    connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True  # Enables column alterations for SQLite databases
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()