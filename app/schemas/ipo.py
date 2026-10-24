from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class IPOListItem(BaseModel):
    id: UUID
    name: str
    symbol: Optional[str] = None
    issue_price_low: Optional[float] = None
    issue_price_high: Optional[float] = None
    issue_size: Optional[float] = None
    open_date: Optional[str] = None
    close_date: Optional[str] = None
    listing_date: Optional[str] = None
    ipo_status: str


class IPOListResponse(BaseModel):
    items: list[IPOListItem]
    total: int
    page: int
    page_size: int


class IPODetailResponse(BaseModel):
    id: UUID
    name: str
    symbol: Optional[str] = None
    exchange: Optional[str] = None
    sector: Optional[str] = None
    description: Optional[str] = None
    issue_price_low: Optional[float] = None
    issue_price_high: Optional[float] = None
    lot_size: Optional[int] = None
    issue_size: Optional[float] = None
    fresh_issue_size: Optional[float] = None
    open_date: Optional[str] = None
    close_date: Optional[str] = None
    listing_date: Optional[str] = None
    ipo_status: str
    source_attribution: Optional[str] = None
    source_disclaimer: Optional[str] = None
    source_attribution: Optional[str] = None
    source_disclaimer: Optional[str] = None