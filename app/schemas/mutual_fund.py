from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class MutualFundListItem(BaseModel):
    id: UUID
    name: str
    symbol: Optional[str] = None
    fund_house: Optional[str] = None
    category: Optional[str] = None
    nav: Optional[float] = None
    aum: Optional[float] = None
    expense_ratio: Optional[float] = None
    risk_level: Optional[str] = None


class MutualFundListResponse(BaseModel):
    items: list[MutualFundListItem]
    total: int
    page: int
    page_size: int


class MutualFundDetailResponse(BaseModel):
    id: UUID
    name: str
    symbol: Optional[str] = None
    exchange: Optional[str] = None
    sector: Optional[str] = None
    description: Optional[str] = None
    fund_house: Optional[str] = None
    category: Optional[str] = None
    nav: Optional[float] = None
    aum: Optional[float] = None
    expense_ratio: Optional[float] = None
    risk_level: Optional[str] = None