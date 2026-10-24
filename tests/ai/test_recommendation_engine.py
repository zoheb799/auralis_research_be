
from decimal import Decimal
import pytest
from app.ai.analysis.recommendation_engine import RecommendationEngine
from app.ai.schemas.recommendation import RecommendationLabel
from app.ai.schemas.signals import (
    InvestmentSignal,
    InvestmentSignals,
    SignalDirection,
)


def make_signal(name, direction, value=Decimal("10")):
    return InvestmentSignal(
        name=name,
        direction=direction,
        value=value,
        explanation=f"Test signal: {name}",
    )


def make_signals(
    historical_return,
    volatility,
    valuation,
    profitability,
    leverage,
):
    signal_list = [
        historical_return,
        volatility,
        valuation,
        profitability,
        leverage,
    ]

    positive = next(
        (s for s in signal_list if s.direction == SignalDirection.POSITIVE),
        None,
    )

    overall_direction = (
        positive.direction
        if positive is not None
        else SignalDirection.NEUTRAL
    )

    return InvestmentSignals(
        historical_return=historical_return,
        volatility=volatility,
        valuation=valuation,
        profitability=profitability,
        leverage=leverage,
        overall_direction=overall_direction,
    )


def test_missing_signals_are_excluded_from_score():
    signals = make_signals(
        make_signal("historical_return", SignalDirection.POSITIVE),
        make_signal("volatility", SignalDirection.NEGATIVE),
        make_signal("valuation", SignalDirection.NEUTRAL, None),
        make_signal("profitability", SignalDirection.POSITIVE),
        make_signal("leverage", SignalDirection.NEUTRAL, None),
    )

    result = RecommendationEngine.evaluate(signals)

    # Available signals: positive, negative, positive.
    assert result.available_signals == 3
    assert result.positive_signals == 2
    assert result.negative_signals == 1
    assert result.neutral_signals == 0
    assert result.score == pytest.approx(1 / 3, abs=0.0001)
    assert result.label == RecommendationLabel.MIXED


def test_insufficient_data_when_fewer_than_three_signals_are_available():
    signals = make_signals(
        make_signal("historical_return", SignalDirection.POSITIVE),
        make_signal("volatility", SignalDirection.NEUTRAL, None),
        make_signal("valuation", SignalDirection.POSITIVE, None),
        make_signal("profitability", SignalDirection.NEUTRAL, None),
        make_signal("leverage", SignalDirection.NEGATIVE, None),
    )

    result = RecommendationEngine.evaluate(signals)

    assert result.available_signals == 1
    assert result.label == RecommendationLabel.INSUFFICIENT_DATA


def test_all_missing_signals_produce_insufficient_data():
    signals = make_signals(
        make_signal("historical_return", SignalDirection.NEUTRAL, None),
        make_signal("volatility", SignalDirection.NEUTRAL, None),
        make_signal("valuation", SignalDirection.NEUTRAL, None),
        make_signal("profitability", SignalDirection.NEUTRAL, None),
        make_signal("leverage", SignalDirection.NEUTRAL, None),
    )

    result = RecommendationEngine.evaluate(signals)

    assert result.available_signals == 0
    assert result.score == 0.0
    assert result.label == RecommendationLabel.INSUFFICIENT_DATA


def test_all_available_positive_signals_are_favorable_for_research():
    signals = make_signals(
        make_signal("historical_return", SignalDirection.POSITIVE),
        make_signal("volatility", SignalDirection.POSITIVE),
        make_signal("valuation", SignalDirection.POSITIVE),
        make_signal("profitability", SignalDirection.POSITIVE),
        make_signal("leverage", SignalDirection.POSITIVE),
    )

    result = RecommendationEngine.evaluate(signals)

    assert result.score == 1.0
    assert result.label == RecommendationLabel.FAVORABLE_FOR_RESEARCH