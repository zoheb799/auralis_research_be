from app.analysis.stock_analysis import (
    analyze_stock,
    analyze_financial_history,
)


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