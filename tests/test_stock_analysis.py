from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.analysis.stock_analysis import (
    analyze_stock,
    analyze_financial_history,
)
from app.services.analysis_service import get_stock_analysis


def test_analyze_stock():
    result = analyze_stock(
        revenue_growth=12.4,
        profit_growth=18.7,
        roe=18.6,
        roce=16.2,
        pe_ratio=24.2,
        debt_to_equity=0.45,
        return_1y=14.8,
        volatility=21.4,
        profit_growth_history=[
            12.5,
            15.2,
            8.4,
            21.7,
            18.7,
        ],
    )

    assert result["growth"]["signal"] == "strong"
    assert result["quality"]["signal"] == "strong"
    assert result["profitability"]["signal"] == "healthy"
    assert result["valuation"]["signal"] == "moderate"
    assert result["debt"]["signal"] == "healthy"
    assert result["momentum"]["signal"] == "positive"
    assert result["risk"]["signal"] == "moderate"
    assert result["quality"]["profitability"] == "healthy"
    assert result["quality"]["growth"] == "strong"
    assert result["quality"]["consistency"] == "strong"


def test_analyze_financial_history():
    result = analyze_financial_history(
        current_revenue=125000,
        previous_revenue=112000,
        current_profit=15000,
        previous_profit=12500,
    )

    assert round(result["revenue_growth"], 2) == 11.61
    assert result["profit_growth"] == 20.0
    assert result["signal"] == "strong"


@pytest.mark.asyncio
async def test_get_stock_analysis_includes_financial_metric_history(monkeypatch):
    latest_metric = SimpleNamespace(
        period_type="annual",
        period_end=date(2025, 3, 31),
        consolidation_type="consolidated",
        source_provider="test-provider",
        source_as_of_date=date(2025, 4, 15),
        shareholder_equity=Decimal("100"),
        revenue=Decimal("125"),
        operating_profit=Decimal("20"),
        net_profit=Decimal("15"),
        eps=Decimal("1.5"),
        total_debt=Decimal("30"),
        cash=Decimal("10"),
        roe=Decimal("18.6"),
        roce=Decimal("16.2"),
    )
    previous_metric = SimpleNamespace(
        period_type="annual",
        period_end=date(2024, 3, 31),
        consolidation_type="consolidated",
        source_provider="test-provider",
        source_as_of_date=date(2024, 4, 15),
        shareholder_equity=Decimal("90"),
        revenue=Decimal("100"),
        operating_profit=Decimal("15"),
        net_profit=Decimal("10"),
        eps=Decimal("1.0"),
        total_debt=Decimal("35"),
        cash=Decimal("8"),
        roe=Decimal("15"),
        roce=Decimal("14"),
    )
    data = {
        "stock": SimpleNamespace(
            roe=Decimal("18.6"),
            pe_ratio=Decimal("24.2"),
            debt_to_equity=Decimal("0.45"),
        ),
        "metrics": [latest_metric, previous_metric],
        "latest_metric": latest_metric,
        "previous_metric": previous_metric,
        "prices": [],
    }

    class FakeStockRepository:
        def __init__(self, db):
            pass

        async def get_stock_analysis_data(self, asset_id):
            return data

    monkeypatch.setattr(
        "app.services.analysis_service.StockRepository",
        FakeStockRepository,
    )

    result = await get_stock_analysis(db=None, asset_id=None)

    assert result.growth.revenue_growth == 25.0
    assert result.growth.profit_growth == 50.0
    assert result.quality.signal == "strong"
    assert len(result.financial_metrics) == 2
    assert result.financial_metrics[0].period_type == "annual"
    assert result.financial_metrics[0].revenue == 125.0
    assert result.financial_metrics[0].net_profit == 15.0
    assert result.financial_metrics[0].roe == 18.6
    assert result.financial_metrics[0].source_provider == "test-provider"