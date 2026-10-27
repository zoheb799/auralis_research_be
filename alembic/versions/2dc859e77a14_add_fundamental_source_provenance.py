"""add fundamental source provenance

Revision ID: 2dc859e77a14
Revises: fd2a1b77c50e
Create Date: 2026-10-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2dc859e77a14"
down_revision: Union[str, Sequence[str], None] = "fd2a1b77c50e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "asset_fundamental_sync_state",
        sa.Column("provider", sa.String(length=50), nullable=False, server_default=""),
    )
    op.add_column(
        "asset_fundamental_sync_state",
        sa.Column("source_as_of_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "asset_fundamental_sync_state",
        sa.Column("missing_fields", sa.Text(), nullable=True),
    )
    op.add_column(
        "financial_metrics",
        sa.Column("consolidation_type", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "financial_metrics",
        sa.Column("source_provider", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "financial_metrics",
        sa.Column("source_as_of_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "financial_metrics",
        sa.Column("shareholder_equity", sa.Numeric(20, 2), nullable=True),
    )
    op.create_index(
        "uq_financial_metric_source_period",
        "financial_metrics",
        [
            "asset_id",
            "period_type",
            "period_end",
            "consolidation_type",
        ],
        unique=True,
        postgresql_where=sa.text("consolidation_type IS NOT NULL"),
    )
    op.alter_column(
        "asset_fundamental_sync_state",
        "provider",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_financial_metric_source_period",
        table_name="financial_metrics",
    )
    op.drop_column("financial_metrics", "shareholder_equity")
    op.drop_column("financial_metrics", "source_as_of_date")
    op.drop_column("financial_metrics", "source_provider")
    op.drop_column("financial_metrics", "consolidation_type")
    op.drop_column("asset_fundamental_sync_state", "missing_fields")
    op.drop_column("asset_fundamental_sync_state", "source_as_of_date")
    op.drop_column("asset_fundamental_sync_state", "provider")
