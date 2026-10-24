from enum import Enum
from decimal import Decimal
from pydantic import BaseModel


class SignalDirection(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class InvestmentSignal(BaseModel):
    name: str
    direction: SignalDirection
    value: Decimal | None = None
    explanation: str


class InvestmentSignals(BaseModel):
    historical_return: InvestmentSignal
    volatility: InvestmentSignal
    valuation: InvestmentSignal
    profitability: InvestmentSignal
    leverage: InvestmentSignal

    overall_direction: SignalDirection