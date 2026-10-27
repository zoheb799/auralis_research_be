from app.analysis.quality_analysis import analyze_quality


def test_analyze_quality():
    result = analyze_quality(
        roe=18.6,
        roce=16.2,
        operating_margin=18.5,
        net_margin=12.0,
        profit_growth=18.7,
        profit_growth_history=[
            12.5,
            15.2,
            8.4,
            21.7,
            18.7,
        ],
    )

    assert result["profitability"] == "healthy"
    assert result["growth"] == "strong"
    assert result["consistency"] == "strong"
    assert result["signal"] == "strong"


def test_quality_with_missing_data():
    result = analyze_quality()

    assert result["profitability"] == "unknown"
    assert result["growth"] == "unknown"
    assert result["consistency"] == "unknown"
    assert result["signal"] == "unknown"


def test_quality_scores_stable_growth_without_crashing():
    result = analyze_quality(profit_growth=4.0)

    assert result["growth"] == "stable"
    assert result["signal"] == "moderate"


def test_quality_scores_negative_growth_without_crashing():
    result = analyze_quality(profit_growth=-4.0)

    assert result["growth"] == "negative"
    assert result["signal"] == "weak"
