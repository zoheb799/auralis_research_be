"""add IPO source attribution and disclaimer

Revision ID: e57a1c92d306
Revises: c7d92e1a4f30
Create Date: 2026-10-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e57a1c92d306"
down_revision: Union[str, Sequence[str], None] = "c7d92e1a4f30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ipos",
        sa.Column("source_attribution", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "ipos",
        sa.Column("source_disclaimer", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ipos", "source_disclaimer")
    op.drop_column("ipos", "source_attribution")