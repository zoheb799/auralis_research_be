from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class MarketAssetData(BaseModel):
    asset_id: UUID

    name: str
    symbol: str | None
    asset_type: str
    exchange: str | None
    sector: str | None

    # Latest market price
    current_price: Decimal | None = None
    price_timestamp: datetime | None = None
    price_observation_type: str | None = None
    price_interval: str | None = None

    # Stock fundamentals
    market_cap: Decimal | None = None
    pe_ratio: Decimal | None = None
    eps: Decimal | None = None
    dividend_yield: Decimal | None = None
    book_value: Decimal | None = None
    debt_to_equity: Decimal | None = None
    roe: Decimal | None = None

    # Mutual fund data
    nav: Decimal | None = None
    aum: Decimal | None = None
    expense_ratio: Decimal | None = None
    risk_level: str | None = None

    # IPO data
    issue_price_low: Decimal | None = None
    issue_price_high: Decimal | None = None
    lot_size: int | None = None
    issue_size: Decimal | None = None
    ipo_status: str | None = None