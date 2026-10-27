from app.analysis.mutual_fund_analysis import (
    analyze_mutual_fund,
    return_signal,
    expense_ratio_signal,
    volatility_signal,
    sharpe_signal,
    concentration_signal,
    benchmark_signal,
    consistency_signal,
    risk_signal,
)
from app.services.analysis_service import analyze_mutual_fund_data


def test_return_signal():
    assert return_signal(18.0) == "strong"
    assert return_signal(10.0) == "positive"
    assert return_signal(4.0) == "stable"
    assert return_signal(-5.0) == "negative"
    assert return_signal(None) == "unknown"


def test_expense_ratio_signal():
    assert expense_ratio_signal(0.3) == "low"
    assert expense_ratio_signal(0.8) == "moderate"
    assert expense_ratio_signal(1.2) == "elevated"
    assert expense_ratio_signal(1.8) == "high"
    assert expense_ratio_signal(None) == "unknown"


def test_volatility_signal():
    assert volatility_signal(8.0) == "low"
    assert volatility_signal(15.0) == "moderate"
    assert volatility_signal(25.0) == "elevated"
    assert volatility_signal(35.0) == "high"
    assert volatility_signal(None) == "unknown"


def test_sharpe_signal():
    assert sharpe_signal(1.8) == "strong"
    assert sharpe_signal(1.2) == "healthy"
    assert sharpe_signal(0.7) == "moderate"
    assert sharpe_signal(0.2) == "weak"
    assert sharpe_signal(-0.5) == "negative"
    assert sharpe_signal(None) == "unknown"


def test_concentration_signal():
    assert concentration_signal(25.0) == "low"
    assert concentration_signal(45.0) == "moderate"
    assert concentration_signal(60.0) == "elevated"
    assert concentration_signal(75.0) == "high"
    assert concentration_signal(None) == "unknown"


def test_benchmark_signal():
    assert benchmark_signal(18.0, 12.0) == "strong"
    assert benchmark_signal(15.0, 12.0) == "positive"
    assert benchmark_signal(11.0, 12.0) == "in_line"
    assert benchmark_signal(8.0, 12.0) == "negative"
    assert benchmark_signal(4.0, 12.0) == "weak"
    assert benchmark_signal(None, 12.0) == "unknown"


def test_consistency_signal():
    assert consistency_signal(9, 10) == "strong"
    assert consistency_signal(7, 10) == "healthy"
    assert consistency_signal(5, 10) == "moderate"
    assert consistency_signal(2, 10) == "weak"
    assert consistency_signal(None, 10) == "unknown"
    assert consistency_signal(5, 0) == "unknown"


def test_risk_signal():
    assert risk_signal(
        volatility=8,
        concentration=30,
    ) == "low"

    assert risk_signal(
        volatility=25,
        concentration=40,
    ) == "moderate"

    assert risk_signal(
        volatility=35,
        concentration=75,
    ) == "high"

    assert risk_signal(
        volatility=None,
        concentration=None,
    ) == "unknown"


def test_analyze_mutual_fund():
    result = analyze_mutual_fund(
        return_1y=18.0,
        return_3y=15.0,
        return_5y=13.0,
        benchmark_return_1y=12.0,
        expense_ratio=0.65,
        volatility=16.0,
        sharpe_ratio=1.2,
        top_10_percentage=45.0,
        positive_periods=8,
        total_periods=10,
    )

    assert result["returns"]["signal"] == "strong"
    assert result["benchmark"]["signal"] == "strong"
    assert result["expense_ratio"]["signal"] == "moderate"
    assert result["volatility"]["signal"] == "moderate"
    assert result["sharpe"]["signal"] == "healthy"
    assert result["concentration"]["signal"] == "moderate"
    assert result["consistency"]["signal"] == "strong"
    assert result["risk"]["signal"] == "moderate"


def test_analyze_mutual_fund_missing_data():
    result = analyze_mutual_fund()

    assert result["returns"]["signal"] == "unknown"
    assert result["benchmark"]["signal"] == "unknown"
    assert result["expense_ratio"]["signal"] == "unknown"
    assert result["volatility"]["signal"] == "unknown"
    assert result["sharpe"]["signal"] == "unknown"
    assert result["concentration"]["signal"] == "unknown"
    assert result["consistency"]["signal"] == "unknown"
    assert result["risk"]["signal"] == "unknown"


def test_analyze_mutual_fund_data_ignores_repository_model_objects():
    result = analyze_mutual_fund_data(
        {
            "asset": object(),
            "fund": object(),
            "expense_ratio": 0.65,
        }
    )

    assert result.expense_ratio.expense_ratio == 0.65
    assert result.expense_ratio.signal == "moderate"