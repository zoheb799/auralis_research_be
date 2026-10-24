
from enum import Enum

from pydantic import BaseModel, Field

from app.ai.schemas.signals import SignalDirection


class RecommendationLabel(str, Enum):
    FAVORABLE_FOR_RESEARCH = "favorable_for_research"
    MIXED = "mixed"
    UNFAVORABLE = "unfavorable"
    INSUFFICIENT_DATA = "insufficient_data"


class RecommendationResult(BaseModel):
    label: RecommendationLabel

    score: float = Field(
        ge=-1.0,
        le=1.0,
    )

    available_signals: int = Field(ge=0)
    positive_signals: int = Field(ge=0)
    neutral_signals: int = Field(ge=0)
    negative_signals: int = Field(ge=0)

    reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    explanation: str

    # Preserve the original signals so the result is traceable.
    overall_signal_direction: SignalDirection