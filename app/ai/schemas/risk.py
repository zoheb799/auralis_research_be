
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    UNKNOWN = "unknown"


class RiskFactor(BaseModel):
    name: str
    level: RiskLevel
    value: Decimal | None = None
    explanation: str


class RiskAssessment(BaseModel):
    overall_level: RiskLevel

    factors: list[RiskFactor] = Field(
        default_factory=list,
    )

    assessed_factors: int = Field(ge=0)
    unavailable_factors: list[str] = Field(
        default_factory=list,
    )

    explanation: str