from enum import Enum

from pydantic import BaseModel, Field


class AssetType(str, Enum):
    STOCK = "stock"
    IPO = "ipo"
    MUTUAL_FUND = "mutual_fund"
    UNKNOWN = "unknown"


class IntentType(str, Enum):
    GENERAL_CHAT = "general_chat"
    EXPLANATION = "explanation"
    SPECIFIC_RESEARCH = "specific_research"
    COMPARISON = "comparison"
    BROAD_DISCOVERY = "broad_discovery"
    PORTFOLIO_PLANNING = "portfolio_planning"


class InvestmentHorizon(str, Enum):
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    UNKNOWN = "unknown"


class InvestmentIntent(BaseModel):
    intent_type: IntentType = IntentType.SPECIFIC_RESEARCH

    asset_type: AssetType = AssetType.UNKNOWN

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

    comparison_targets: list[str] | None = None

    discovery_criteria: str | None = None

    constraints: str | None = None

    clarification_needed: bool = False

    user_query: str