"""add fundamentals sync tracking

Revision ID: fd2a1b77c50e
Revises: e57a1c92d306
Create Date: 2026-10-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "fd2a1b77c50e"
down_revision: Union[str, Sequence[str], None] = "e57a1c92d306"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "asset_fundamental_sync_state",
        sa.Column("asset_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("last_attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_category", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("asset_id"),
    )
    op.create_table(
        "market_data_api_usage",
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("requests_used", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("provider", "usage_date"),
    )


def downgrade() -> None:
    op.drop_table("market_data_api_usage")
    op.drop_table("asset_fundamental_sync_state")
