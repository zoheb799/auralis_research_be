import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AssetPrice(Base):
    __tablename__ = "asset_prices"
    __table_args__ = (
        Index(
            "uq_asset_price_observation",
            "asset_id",
            "provider",
            "observation_type",
            "interval",
            "price_timestamp",
            unique=True,
            postgresql_where=text("provider <> 'legacy'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="legacy",
    )

    observation_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="quote",
    )

    interval: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="snapshot",
    )

    price: Mapped[Decimal] = mapped_column(
        Numeric(14, 4),
        nullable=False,
    )

    open: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4),
        nullable=True,
    )

    high: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4),
        nullable=True,
    )

    low: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4),
        nullable=True,
    )

    close: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4),
        nullable=True,
    )

    volume: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    price_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )