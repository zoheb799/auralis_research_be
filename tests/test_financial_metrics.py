from app.analysis.financial_metrics import (
    calculate_growth,
    calculate_margin,
    calculate_debt_to_equity,
    calculate_financial_growth,
)


def test_calculate_growth():
    result = calculate_growth(120, 100)

    assert result == 20.0


def test_calculate_growth_negative():
    result = calculate_growth(80, 100)

    assert result == -20.0


def test_calculate_growth_zero_previous():
    result = calculate_growth(100, 0)

    assert result is None


def test_calculate_margin():
    result = calculate_margin(20, 100)

    assert result == 20.0


def test_calculate_debt_to_equity():
    result = calculate_debt_to_equity(50, 100)

    assert result == 0.5

def test_calculate_financial_growth():
    result = calculate_financial_growth(
        current_revenue=125000,
        previous_revenue=112000,
        current_profit=15000,
        previous_profit=12500,
    )

    assert round(result["revenue_growth"], 2) == 11.61
    assert result["profit_growth"] == 20.0