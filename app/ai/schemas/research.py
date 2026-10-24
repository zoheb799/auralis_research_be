from pydantic import BaseModel, Field

from app.ai.schemas.intent import (
    AssetType,
    InvestmentHorizon,
)


class ResearchRequest(BaseModel):
    asset_type: AssetType

    investment_amount: float | None = Field(
        default=None,
        ge=0,
    )

    horizon: InvestmentHorizon = InvestmentHorizon.UNKNOWN

    duration_months: int | None = Field(
        default=None,
        ge=1,
    )

    objective: str | None = None

    risk_preference: str | None = None

    asset_name: str | None = None

    user_question: str | None = None