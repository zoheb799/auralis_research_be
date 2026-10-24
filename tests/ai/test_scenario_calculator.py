from decimal import Decimal
from uuid import uuid4

from app.ai.calculations.scenario_calculator import (
    ScenarioCalculator,
)
from app.ai.schemas.market_data import MarketAssetData


def test_scenario_calculator():

    asset = MarketAssetData(
        asset_id=uuid4(),
        name="Test Stock",
        symbol="TEST",
        asset_type="stock",
        exchange="NSE",
        sector="Technology",
        current_price=Decimal("250"),
    )

    scenarios = ScenarioCalculator.calculate(
        asset=asset,
        investment_amount=Decimal("10000"),
        scenario_returns=[
            Decimal("-5"),
            Decimal("5"),
            Decimal("10"),
        ],
    )

    assert len(scenarios) == 3

    # ₹10,000 / ₹250 = 40 shares
    assert scenarios[0].shares == 40

    # 40 × ₹250
    assert scenarios[0].invested_amount == Decimal("10000")

    # -5% → ₹237.50
    assert scenarios[0].scenario_price == Decimal("237.50")

    # 40 × ₹237.50
    assert scenarios[0].scenario_value == Decimal("9500")

    # ₹9,500 - ₹10,000
    assert scenarios[0].profit_loss == Decimal("-500")

    # +10% → ₹275
    assert scenarios[2].scenario_price == Decimal("275")

    # 40 × ₹275
    assert scenarios[2].scenario_value == Decimal("11000")

    assert scenarios[2].profit_loss == Decimal("1000")