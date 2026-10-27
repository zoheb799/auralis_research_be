"""allow running market-data sync status

Revision ID: 83d9a1f2c6b4
Revises: 2dc859e77a14
Create Date: 2026-10-28

"""
from typing import Sequence, Union

from alembic import op


revision: str = "83d9a1f2c6b4"
down_revision: Union[str, Sequence[str], None] = "2dc859e77a14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "market_data_sync_state",
        "last_finished_at",
        nullable=True,
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE market_data_sync_state
        SET status = 'failed',
            error_category = COALESCE(error_category, 'migration_downgrade'),
            last_finished_at = COALESCE(last_finished_at, last_started_at)
        WHERE status = 'running'
        """
    )
    op.alter_column(
        "market_data_sync_state",
        "last_finished_at",
        nullable=False,
    )
