from datetime import date

from sqlalchemy import Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MarketDataAPIUsage(Base):
    __tablename__ = "market_data_api_usage"

    provider: Mapped[str] = mapped_column(String(50), primary_key=True)
    usage_date: Mapped[date] = mapped_column(Date, primary_key=True)
    requests_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
