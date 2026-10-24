from app.analysis.ipo_analysis import (
    analyze_ipo_growth,
    analyze_ipo_profitability,
    analyze_ipo_valuation,
    analyze_ipo_issue_structure,
    analyze_ipo_risk,
    analyze_ipo,
)

def test_analyze_ipo_growth():
    result = analyze_ipo_growth(
        current_revenue=150000,
        previous_revenue=120000,
        current_profit=18000,
        previous_profit=15000,
    )

    assert round(result["revenue_growth"], 2) == 25.00
    assert round(result["profit_growth"], 2) == 20.00
    assert result["signal"] == "strong"


def test_analyze_ipo_growth_negative():
    result = analyze_ipo_growth(
        current_revenue=90000,
        previous_revenue=100000,
        current_profit=8000,
        previous_profit=10000,
    )

    assert result["revenue_growth"] == -10.0
    assert result["profit_growth"] == -20.0
    assert result["signal"] == "negative"


def test_analyze_ipo_growth_missing_data():
    result = analyze_ipo_growth()

    assert result["revenue_growth"] is None
    assert result["profit_growth"] is None
    assert result["signal"] == "unknown"

def test_analyze_ipo_profitability():
    result = analyze_ipo_profitability(
        roe=21.0,
        roce=19.0,
        operating_margin=16.0,
        net_margin=10.0,
    )

    assert result["roe"] == 21.0
    assert result["roce"] == 19.0
    assert result["operating_margin"] == 16.0
    assert result["net_margin"] == 10.0
    assert result["signal"] == "healthy"


def test_analyze_ipo_profitability_missing_data():
    result = analyze_ipo_profitability()

    assert result["signal"] == "unknown"


def test_analyze_ipo_valuation():
    result = analyze_ipo_valuation(
        pe_ratio=24.5,
    )

    assert result["pe_ratio"] == 24.5
    assert result["signal"] == "moderate"


def test_analyze_ipo_valuation_missing_data():
    result = analyze_ipo_valuation()

    assert result["signal"] == "unknown"

def test_analyze_ipo_issue_structure():
    result = analyze_ipo_issue_structure(
        issue_price_low=950,
        issue_price_high=1000,
        lot_size=15,
        issue_size=1000,
        fresh_issue_size=300,
        ofs_size=700,
    )

    assert result["issue_price_low"] == 950
    assert result["issue_price_high"] == 1000
    assert result["lot_size"] == 15
    assert result["issue_size"] == 1000
    assert result["fresh_issue_size"] == 300
    assert result["ofs_size"] == 700
    assert result["ofs_percentage"] == 70.0


def test_analyze_ipo_issue_structure_missing_data():
    result = analyze_ipo_issue_structure()

    assert result["ofs_percentage"] is None

def test_analyze_ipo_risk():
    result = analyze_ipo_risk(
        debt_to_equity=2.2,
        profitability="moderate",
        valuation="elevated",
        ofs_percentage=70,
    )

    assert result["debt"] == "high"
    assert result["profitability"] == "moderate"
    assert result["valuation"] == "elevated"
    assert result["ofs_percentage"] == 70
    assert result["signal"] == "high"


def test_analyze_ipo_risk_low():
    result = analyze_ipo_risk(
        debt_to_equity=0.3,
        profitability="strong",
        valuation="moderate",
        ofs_percentage=10,
    )

    assert result["debt"] == "healthy"
    assert result["signal"] == "low"

def test_analyze_ipo():
    result = analyze_ipo(
        current_revenue=150000,
        previous_revenue=120000,
        current_profit=18000,
        previous_profit=15000,
        roe=21.0,
        roce=19.0,
        operating_margin=16.0,
        net_margin=10.0,
        pe_ratio=24.5,
        debt_to_equity=0.8,
        issue_price_low=950,
        issue_price_high=1000,
        lot_size=15,
        issue_size=1000,
        fresh_issue_size=300,
        ofs_size=700,
    )

    assert result["growth"]["signal"] == "strong"
    assert result["profitability"]["signal"] == "healthy"
    assert result["valuation"]["signal"] == "moderate"

    assert result["issue_structure"]["ofs_percentage"] == 70.0

    assert result["risk"]["debt"] == "moderate"
    assert result["risk"]["signal"] == "moderate"