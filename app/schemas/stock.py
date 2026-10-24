from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class StockListItem(BaseModel):
    id: UUID
    name: str
    symbol: Optional[str] = None
    exchange: Optional[str] = None
    sector: Optional[str] = None
    price: Optional[float] = None
    change_percent: Optional[float] = None
    price_data_type: Optional[str] = None
    price_interval: Optional[str] = None


class StockListResponse(BaseModel):
    items: list[StockListItem]
    total: int
    page: int
    page_size: int


class StockFundamentals(BaseModel):
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    eps: Optional[float] = None
    dividend_yield: Optional[float] = None
    book_value: Optional[float] = None
    debt_to_equity: Optional[float] = None
    roe: Optional[float] = None


class FinancialHistoryItem(BaseModel):
    period_type: str
    period_end: date
    revenue: Optional[float] = None
    operating_profit: Optional[float] = None
    net_profit: Optional[float] = None
    eps: Optional[float] = None


class PriceHistoryItem(BaseModel):
    price: float
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None
    price_timestamp: datetime
    data_type: Optional[str] = None
    interval: Optional[str] = None


class StockDetailResponse(BaseModel):
    id: UUID
    name: str
    symbol: Optional[str] = None
    exchange: Optional[str] = None
    sector: Optional[str] = None

    price: Optional[float] = None
    change_percent: Optional[float] = None
    price_data_type: Optional[str] = None
    price_interval: Optional[str] = None

    fundamentals: StockFundamentals

    financial_history: list[FinancialHistoryItem]

    price_history: list[PriceHistoryItem]