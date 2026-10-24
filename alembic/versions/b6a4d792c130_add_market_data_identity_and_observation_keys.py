"""add market data identity and observation keys

Revision ID: b6a4d792c130
Revises: a099999fc672
Create Date: 2026-10-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b6a4d792c130"
down_revision: Union[str, Sequence[str], None] = "a099999fc672"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "asset_identifiers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("asset_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("identifier_type", sa.String(length=50), nullable=False),
        sa.Column("scope", sa.String(length=50), server_default="", nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "identifier_type",
            "scope",
            "external_id",
            name="uq_asset_identifier_provider_type_external",
        ),
    )
    op.create_index(
        op.f("ix_asset_identifiers_asset_id"),
        "asset_identifiers",
        ["asset_id"],
        unique=False,
    )

    op.add_column(
        "asset_prices",
        sa.Column(
            "provider",
            sa.String(length=50),
            server_default="legacy",
            nullable=False,
        ),
    )
    op.add_column(
        "asset_prices",
        sa.Column(
            "observation_type",
            sa.String(length=20),
            server_default="quote",
            nullable=False,
        ),
    )
    op.add_column(
        "asset_prices",
        sa.Column(
            "interval",
            sa.String(length=20),
            server_default="snapshot",
            nullable=False,
        ),
    )
    op.add_column(
        "asset_prices",
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "uq_asset_price_observation",
        "asset_prices",
        ["asset_id", "provider", "observation_type", "interval", "price_timestamp"],
        unique=True,
        postgresql_where=sa.text("provider <> 'legacy'"),
    )


def downgrade() -> None:
    op.drop_index("uq_asset_price_observation", table_name="asset_prices")
    op.drop_column("asset_prices", "fetched_at")
    op.drop_column("asset_prices", "interval")
    op.drop_column("asset_prices", "observation_type")
    op.drop_column("asset_prices", "provider")
    op.drop_index(
        op.f("ix_asset_identifiers_asset_id"),
        table_name="asset_identifiers",
    )
    op.drop_table("asset_identifiers")