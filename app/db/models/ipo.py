import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, String, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IPO(Base):
    __tablename__ = "ipos"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        primary_key=True,
    )

    issue_price_low: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    issue_price_high: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    lot_size: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    issue_size: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2),
        nullable=True,
    )

    open_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    close_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    listing_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    ipo_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="upcoming",
    )

    source_attribution: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    source_disclaimer: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )