from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NormalizedRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StockInstrument(NormalizedRecord):
    instrument_key: str
    symbol: str
    name: str | None = None
    exchange: str
    isin: str | None = None
    sector: str | None = None


class StockCatalogSyncSummary(NormalizedRecord):
    source: str
    fetched: int
    assets_inserted: int
    assets_updated: int
    stock_records_inserted: int
    identifiers_linked: int


class FinancialPeriod(NormalizedRecord):
    period_end: date
    consolidation_type: Literal["consolidated", "standalone"] | None = None
    revenue: Decimal | None = None
    operating_profit: Decimal | None = None
    net_profit: Decimal | None = None
    eps: Decimal | None = None
    total_debt: Decimal | None = None
    shareholder_equity: Decimal | None = None
    cash: Decimal | None = None
    roe: Decimal | None = None
    roce: Decimal | None = None


class StockFundamentalData(NormalizedRecord):
    provider_symbol: str
    source_provider: str | None = None
    source_as_of_date: date | None = None
    missing_fields: list[str] = Field(default_factory=list)
    market_cap: Decimal | None = None
    pe_ratio: Decimal | None = None
    eps: Decimal | None = None
    dividend_yield: Decimal | None = None
    book_value: Decimal | None = None
    debt_to_equity: Decimal | None = None
    roe: Decimal | None = None
    periods: list[FinancialPeriod] = Field(default_factory=list)


class PriceObservation(NormalizedRecord):
    instrument_key: str
    price: Decimal = Field(gt=0)
    price_timestamp: datetime
    observation_type: Literal["quote", "eod"] = "quote"
    interval: str = "snapshot"
    open: Decimal | None = Field(default=None, gt=0)
    high: Decimal | None = Field(default=None, gt=0)
    low: Decimal | None = Field(default=None, gt=0)
    close: Decimal | None = Field(default=None, gt=0)
    volume: int | None = Field(default=None, ge=0)

    @field_validator("price_timestamp")
    @classmethod
    def timestamp_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("price_timestamp must include a timezone")
        return value


class FundScheme(NormalizedRecord):
    scheme_code: str
    name: str
    fund_house: str | None = None
    category: str | None = None
    isin_growth: str | None = None
    isin_div_reinvestment: str | None = None


class NavObservation(NormalizedRecord):
    scheme_code: str
    nav_date: date
    nav: Decimal = Field(gt=0)


class IPORecord(NormalizedRecord):
    ipo_id: str
    name: str
    symbol: str | None = None
    status: Literal["upcoming", "open", "closed", "listed"]
    isin: str | None = None
    issue_type: str | None = None
    industry: str | None = None
    issue_size: Decimal | None = Field(default=None, gt=0)
    issue_price_low: Decimal | None = Field(default=None, gt=0)
    issue_price_high: Decimal | None = Field(default=None, gt=0)
    lot_size: int | None = Field(default=None, gt=0)
    open_date: date | None = None
    close_date: date | None = None
    listing_date: date | None = None
    listing_price: Decimal | None = Field(default=None, gt=0)
    total_subscription: Decimal | None = Field(default=None, ge=0)
    source_attribution: str | None = None
    source_disclaimer: str | None = None


class SyncSummary(NormalizedRecord):
    job: str
    provider: str
    job_id: str = Field(default_factory=lambda: str(uuid4()))
    duration_seconds: float = 0.0
    discovered: int = 0
    catalog_assets_inserted: int = 0
    catalog_assets_updated: int = 0
    catalog_stock_records_inserted: int = 0
    requests_used: int = 0
    request_budget_remaining: int | None = None
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0