from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class InvestmentScenario(BaseModel):
    asset_id: UUID
    asset_name: str
    symbol: str | None

    investment_amount: Decimal
    current_price: Decimal

    shares: int
    invested_amount: Decimal
    remaining_amount: Decimal

    scenario_return_percent: Decimal
    scenario_price: Decimal
    scenario_value: Decimal

    profit_loss: Decimal


class AssetAnalysis(BaseModel):
    asset_id: UUID
    asset_name: str
    symbol: str | None

    current_price: Decimal | None

    historical_return_percent: Decimal | None
    volatility_percent: Decimal | None

    scenarios: list[InvestmentScenario]

class HistoricalAnalysis(BaseModel):
    asset_id: UUID

    current_price: Decimal | None

    period_return_percent: Decimal | None

    highest_price: Decimal | None
    lowest_price: Decimal | None

    volatility_percent: Decimal | None

    observation_count: int

    start_timestamp: datetime | None
    end_timestamp: datetime | None
    data_age_hours: float | None = None
    is_stale: bool | None = None