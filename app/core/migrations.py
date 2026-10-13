import logging
from alembic import command
from alembic.config import Config

logger = logging.getLogger("terminus.migrations")


def run_startup_migrations():
    """
    Applies pending Alembic schema migrations on application launch.
    Replaces raw Base.metadata.create_all() calls.
    """
    try:
        logger.info("Checking for pending database migrations...")
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logger.info("Database schema is up to date (Alembic head).")
    except Exception as e:
        logger.error(f"Database migration failed on startup: {e}")
        raise e