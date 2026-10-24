from typing import Optional

from app.analysis.signals import growth_signal


def return_signal(return_percent: Optional[float]) -> str:
    """
    Classify mutual fund returns.

    MVP heuristic only. Returns should always be considered
    together with risk, benchmark performance, and time period.
    """

    if return_percent is None:
        return "unknown"

    if return_percent >= 15:
        return "strong"

    if return_percent >= 8:
        return "positive"

    if return_percent >= 0:
        return "stable"

    return "negative"


def expense_ratio_signal(
    expense_ratio: Optional[float],
) -> str:
    """
    Classify mutual fund expense ratio.
    """

    if expense_ratio is None:
        return "unknown"

    if expense_ratio <= 0.5:
        return "low"

    if expense_ratio <= 1.0:
        return "moderate"

    if expense_ratio <= 1.5:
        return "elevated"

    return "high"


def volatility_signal(
    volatility: Optional[float],
) -> str:
    """
    Classify annualized volatility.
    """

    if volatility is None:
        return "unknown"

    if volatility <= 10:
        return "low"

    if volatility <= 20:
        return "moderate"

    if volatility <= 30:
        return "elevated"

    return "high"


def sharpe_signal(
    sharpe_ratio: Optional[float],
) -> str:
    """
    Classify Sharpe ratio.

    Higher Sharpe generally means better historical
    risk-adjusted returns.
    """

    if sharpe_ratio is None:
        return "unknown"

    if sharpe_ratio >= 1.5:
        return "strong"

    if sharpe_ratio >= 1.0:
        return "healthy"

    if sharpe_ratio >= 0.5:
        return "moderate"

    if sharpe_ratio >= 0:
        return "weak"

    return "negative"


def concentration_signal(
    top_10_percentage: Optional[float],
) -> str:
    """
    Classify portfolio concentration based on the
    percentage held in the top 10 holdings.
    """

    if top_10_percentage is None:
        return "unknown"

    if top_10_percentage <= 30:
        return "low"

    if top_10_percentage <= 50:
        return "moderate"

    if top_10_percentage <= 70:
        return "elevated"

    return "high"


def benchmark_signal(
    fund_return: Optional[float],
    benchmark_return: Optional[float],
) -> str:
    """
    Compare fund return with benchmark return.
    """

    if fund_return is None or benchmark_return is None:
        return "unknown"

    difference = fund_return - benchmark_return

    if difference >= 5:
        return "strong"

    if difference >= 2:
        return "positive"

    if difference >= -2:
        return "in_line"

    if difference >= -5:
        return "negative"

    return "weak"


def consistency_signal(
    positive_periods: Optional[int],
    total_periods: Optional[int],
) -> str:
    """
    Estimate return consistency across historical periods.
    """

    if positive_periods is None or total_periods is None:
        return "unknown"

    if total_periods <= 0:
        return "unknown"

    ratio = positive_periods / total_periods

    if ratio >= 0.8:
        return "strong"

    if ratio >= 0.6:
        return "healthy"

    if ratio >= 0.4:
        return "moderate"

    return "weak"


def risk_signal(
    volatility: Optional[float],
    concentration: Optional[float],
) -> str:
    """
    Estimate overall mutual fund risk.
    """

    score = 0
    available = False

    if volatility is not None:
        available = True

        if volatility > 30:
            score += 2
        elif volatility > 15:
            score += 1

    if concentration is not None:
        available = True

        if concentration > 60:
            score += 2
        elif concentration > 35:
            score += 1

    if not available:
        return "unknown"

    if score >= 3:
        return "high"

    if score >= 1:
        return "moderate"

    return "low"


def analyze_mutual_fund(
    *,
    return_1y: Optional[float] = None,
    return_3y: Optional[float] = None,
    return_5y: Optional[float] = None,
    benchmark_return_1y: Optional[float] = None,
    expense_ratio: Optional[float] = None,
    volatility: Optional[float] = None,
    sharpe_ratio: Optional[float] = None,
    top_10_percentage: Optional[float] = None,
    positive_periods: Optional[int] = None,
    total_periods: Optional[int] = None,
) -> dict:
    """
    Complete deterministic mutual fund analysis.

    The LLM should consume this structured result rather
    than calculate financial metrics itself.
    """

    returns = {
        "return_1y": return_1y,
        "return_3y": return_3y,
        "return_5y": return_5y,
        "signal": return_signal(return_1y),
    }

    benchmark = {
        "fund_return_1y": return_1y,
        "benchmark_return_1y": benchmark_return_1y,
        "signal": benchmark_signal(
            return_1y,
            benchmark_return_1y,
        ),
    }

    expense = {
        "expense_ratio": expense_ratio,
        "signal": expense_ratio_signal(expense_ratio),
    }

    volatility_result = {
        "volatility": volatility,
        "signal": volatility_signal(volatility),
    }

    sharpe = {
        "sharpe_ratio": sharpe_ratio,
        "signal": sharpe_signal(sharpe_ratio),
    }

    concentration = {
        "top_10_percentage": top_10_percentage,
        "signal": concentration_signal(top_10_percentage),
    }

    consistency = {
        "positive_periods": positive_periods,
        "total_periods": total_periods,
        "signal": consistency_signal(
            positive_periods,
            total_periods,
        ),
    }

    risk = {
        "volatility": volatility,
        "concentration": top_10_percentage,
        "signal": risk_signal(
            volatility=volatility,
            concentration=top_10_percentage,
        ),
    }

    return {
        "returns": returns,
        "benchmark": benchmark,
        "expense_ratio": expense,
        "volatility": volatility_result,
        "sharpe": sharpe,
        "concentration": concentration,
        "consistency": consistency,
        "risk": risk,
    }