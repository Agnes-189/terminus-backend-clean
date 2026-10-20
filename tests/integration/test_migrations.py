import pytest
from alembic import command
from alembic.config import Config


@pytest.fixture
def alembic_config():
    """Provides isolated Alembic configuration pointing to test database."""
    cfg = Config("alembic.ini")
    return cfg


def test_migration_upgrade_and_downgrade_cycle(alembic_config):
    """Verifies full upgrade and rollback cycle across all schema revisions."""
    # 1. Upgrade to latest schema
    command.upgrade(alembic_config, "head")

    # 2. Rollback to base schema state
    command.downgrade(alembic_config, "base")

    # 3. Re-apply to ensure idempotency
    command.upgrade(alembic_config, "head")