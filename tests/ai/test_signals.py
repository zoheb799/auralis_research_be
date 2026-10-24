from decimal import Decimal

from app.ai.schemas.signals import (
    InvestmentSignal,
    InvestmentSignals,
    SignalDirection,
)


def test_investment_signal():

    signal = InvestmentSignal(
        name="historical_return",
        direction=SignalDirection.POSITIVE,
        value=Decimal("18.50"),
        explanation="The asset gained 18.5% during the analysis period.",
    )

    assert signal.name == "historical_return"
    assert signal.direction == SignalDirection.POSITIVE
    assert signal.value == Decimal("18.50")


def test_investment_signals():

    signals = InvestmentSignals(
        historical_return=InvestmentSignal(
            name="historical_return",
            direction=SignalDirection.POSITIVE,
            value=Decimal("18.50"),
            explanation="Positive historical return.",
        ),
        volatility=InvestmentSignal(
            name="volatility",
            direction=SignalDirection.NEUTRAL,
            value=Decimal("2.50"),
            explanation="Moderate volatility.",
        ),
        valuation=InvestmentSignal(
            name="valuation",
            direction=SignalDirection.POSITIVE,
            value=Decimal("18.00"),
            explanation="Valuation appears reasonable.",
        ),
        profitability=InvestmentSignal(
            name="profitability",
            direction=SignalDirection.POSITIVE,
            value=Decimal("20.00"),
            explanation="Strong profitability.",
        ),
        leverage=InvestmentSignal(
            name="leverage",
            direction=SignalDirection.NEUTRAL,
            value=Decimal("0.50"),
            explanation="Moderate leverage.",
        ),
        overall_direction=SignalDirection.POSITIVE,
    )

    assert signals.overall_direction == SignalDirection.POSITIVE
    assert signals.historical_return.value == Decimal("18.50")
    assert signals.profitability.direction == SignalDirection.POSITIVE