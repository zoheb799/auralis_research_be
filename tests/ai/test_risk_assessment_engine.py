
from decimal import Decimal
from uuid import uuid4

from app.ai.analysis.risk_assessment_engine import RiskAssessmentEngine
from app.ai.schemas.analysis import HistoricalAnalysis
from app.ai.schemas.market_data import MarketAssetData
from app.ai.schemas.risk import RiskLevel


def make_asset(**overrides) -> MarketAssetData:
    data = {
        "asset_id": uuid4(),
        "name": "Example Company",
        "symbol": "EXAMPLE",
        "asset_type": "stock",
        "exchange": "NSE",
        "sector": "Technology",
        "pe_ratio": Decimal("20"),
        "debt_to_equity": Decimal("0.4"),
    }
    data.update(overrides)
    return MarketAssetData(**data)


def make_history(**overrides) -> HistoricalAnalysis:
    data = {
        "asset_id": uuid4(),
        "current_price": Decimal("120"),
        "period_return_percent": Decimal("10"),
        "highest_price": Decimal("125"),
        "lowest_price": Decimal("100"),
        "volatility_percent": Decimal("3"),
        "observation_count": 100,
        "start_timestamp": None,
        "end_timestamp": None,
    }
    data.update(overrides)
    return HistoricalAnalysis(**data)


def test_low_risk_when_all_assessed_factors_are_low():
    result = RiskAssessmentEngine.assess(
        asset=make_asset(
            pe_ratio=Decimal("12"),
            debt_to_equity=Decimal("0.3"),
        ),
        historical_analysis=make_history(
            volatility_percent=Decimal("1.5"),
        ),
    )

    assert result.assessed_factors == 3
    assert result.unavailable_factors == []
    assert result.overall_level == RiskLevel.LOW


def test_high_risk_when_multiple_factors_are_high():
    result = RiskAssessmentEngine.assess(
        asset=make_asset(
            pe_ratio=Decimal("40"),
            debt_to_equity=Decimal("1.5"),
        ),
        historical_analysis=make_history(
            volatility_percent=Decimal("7"),
        ),
    )

    assert result.assessed_factors == 3
    assert result.overall_level == RiskLevel.HIGH


def test_missing_data_is_reported_as_unknown():
    result = RiskAssessmentEngine.assess(
        asset=make_asset(
            pe_ratio=None,
            debt_to_equity=None,
        ),
        historical_analysis=make_history(
            volatility_percent=None,
        ),
    )

    assert result.assessed_factors == 0
    assert result.overall_level == RiskLevel.UNKNOWN
    assert set(result.unavailable_factors) == {
        "volatility",
        "leverage",
        "valuation",
    }


def test_negative_pe_is_not_classified_as_low_valuation_risk():
    result = RiskAssessmentEngine.assess(
        asset=make_asset(pe_ratio=Decimal("-5")),
        historical_analysis=make_history(
            volatility_percent=Decimal("1.5"),
        ),
    )

    valuation = next(
        factor
        for factor in result.factors
        if factor.name == "valuation"
    )

    assert valuation.level == RiskLevel.UNKNOWN
    assert "valuation" in result.unavailable_factors


def test_negative_debt_to_equity_is_not_assumed_low_risk():
    result = RiskAssessmentEngine.assess(
        asset=make_asset(debt_to_equity=Decimal("-0.5")),
        historical_analysis=make_history(
            volatility_percent=Decimal("1.5"),
        ),
    )

    leverage = next(
        factor
        for factor in result.factors
        if factor.name == "leverage"
    )

    assert leverage.level == RiskLevel.UNKNOWN
    assert "leverage" in result.unavailable_factors