
from decimal import Decimal
from uuid import uuid4

from app.ai.analysis.signal_engine import SignalEngine
from app.ai.schemas.analysis import HistoricalAnalysis
from app.ai.schemas.market_data import MarketAssetData
from app.ai.schemas.signals import SignalDirection


def make_asset(**overrides) -> MarketAssetData:
    data = {
        "asset_id": uuid4(),
        "name": "Example Company",
        "symbol": "EXAMPLE",
        "asset_type": "stock",
        "exchange": "NSE",
        "sector": "Technology",
        "pe_ratio": Decimal("20"),
        "roe": Decimal("18"),
        "debt_to_equity": Decimal("0.4"),
    }
    data.update(overrides)
    return MarketAssetData(**data)


def make_history(**overrides) -> HistoricalAnalysis:
    data = {
        "asset_id": uuid4(),
        "current_price": Decimal("120"),
        "period_return_percent": Decimal("20"),
        "highest_price": Decimal("125"),
        "lowest_price": Decimal("90"),
        "volatility_percent": Decimal("3"),
        "observation_count": 100,
        "start_timestamp": None,
        "end_timestamp": None,
    }
    data.update(overrides)
    return HistoricalAnalysis(**data)


def test_positive_historical_return():
    signal = SignalEngine._historical_return_signal(
        make_history(period_return_percent=Decimal("20"))
    )

    assert signal.direction == SignalDirection.POSITIVE
    assert signal.value == Decimal("20")


def test_negative_historical_return():
    signal = SignalEngine._historical_return_signal(
        make_history(period_return_percent=Decimal("-8"))
    )

    assert signal.direction == SignalDirection.NEGATIVE


def test_missing_historical_return_has_no_value():
    signal = SignalEngine._historical_return_signal(
        make_history(period_return_percent=None)
    )

    assert signal.direction == SignalDirection.NEUTRAL
    assert signal.value is None


def test_missing_metrics_are_not_counted_as_available_evidence():
    signals = SignalEngine.analyze(
        asset=make_asset(
            pe_ratio=None,
            roe=None,
            debt_to_equity=None,
        ),
        historical_analysis=make_history(
            volatility_percent=None,
        ),
    )

    assert signals.valuation.value is None
    assert signals.profitability.value is None
    assert signals.leverage.value is None
    assert signals.volatility.value is None

    # The current engine may fail this assertion because its
    # overall-direction calculation counts missing metrics.
    # This test records the intended behavior.
    assert signals.overall_direction == SignalDirection.POSITIVE


def test_all_missing_evidence_does_not_produce_positive_direction():
    signals = SignalEngine.analyze(
        asset=make_asset(
            pe_ratio=None,
            roe=None,
            debt_to_equity=None,
        ),
        historical_analysis=make_history(
            period_return_percent=None,
            volatility_percent=None,
        ),
    )

    assert signals.overall_direction == SignalDirection.NEUTRAL