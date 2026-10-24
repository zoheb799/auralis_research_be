from typing import Optional


def growth_signal(growth: Optional[float]) -> str:
    if growth is None:
        return "unknown"

    if growth >= 15:
        return "strong"
    if growth >= 8:
        return "positive"
    if growth >= 0:
        return "stable"
    return "negative"


def profitability_signal(roe: Optional[float]) -> str:
    if roe is None:
        return "unknown"

    if roe >= 20:
        return "strong"
    if roe >= 12:
        return "healthy"
    if roe >= 5:
        return "moderate"
    return "weak"


def valuation_signal(pe_ratio: Optional[float]) -> str:
    if pe_ratio is None:
        return "unknown"

    if pe_ratio <= 15:
        return "low"
    if pe_ratio <= 25:
        return "moderate"
    if pe_ratio <= 40:
        return "elevated"
    return "high"


def debt_signal(debt_to_equity: Optional[float]) -> str:
    if debt_to_equity is None:
        return "unknown"

    if debt_to_equity <= 0.5:
        return "healthy"
    if debt_to_equity <= 1.0:
        return "moderate"
    if debt_to_equity <= 2.0:
        return "elevated"
    return "high"


def momentum_signal(return_percent: Optional[float]) -> str:
    if return_percent is None:
        return "unknown"

    if return_percent >= 20:
        return "strong"
    if return_percent >= 5:
        return "positive"
    if return_percent >= -5:
        return "neutral"
    if return_percent >= -20:
        return "negative"
    return "weak"


def risk_signal(
    volatility: Optional[float],
    debt_to_equity: Optional[float] = None,
) -> str:
    if volatility is None:
        return "unknown"

    risk_score = 0

    if volatility > 30:
        risk_score += 2
    elif volatility > 15:
        risk_score += 1

    if debt_to_equity is not None:
        if debt_to_equity > 2:
            risk_score += 2
        elif debt_to_equity > 1:
            risk_score += 1

    if risk_score >= 3:
        return "high"

    if risk_score >= 1:
        return "moderate"

    return "low"

def quality_signal(
    roe: Optional[float],
    roce: Optional[float],
    profit_growth: Optional[float],
) -> str:
    """
    Estimate overall business quality from profitability
    and profit growth.
    """

    score = 0
    available_metrics = 0

    if roe is not None:
        available_metrics += 1

        if roe >= 20:
            score += 2
        elif roe >= 12:
            score += 1

    if roce is not None:
        available_metrics += 1

        if roce >= 20:
            score += 2
        elif roce >= 12:
            score += 1

    if profit_growth is not None:
        available_metrics += 1

        if profit_growth >= 15:
            score += 2
        elif profit_growth >= 8:
            score += 1

    if available_metrics == 0:
        return "unknown"

    average_score = score / available_metrics

    if average_score >= 1.5:
        return "strong"

    if average_score >= 0.75:
        return "healthy"

    if average_score > 0:
        return "moderate"

    return "weak"

def profitability_signal(
    roe: Optional[float],
    roce: Optional[float],
    operating_margin: Optional[float] = None,
    net_margin: Optional[float] = None,
) -> str:
    """
    Estimate profitability using ROE, ROCE, and margins.
    """

    signals = []

    if roe is not None:
        if roe >= 20:
            signals.append("strong")
        elif roe >= 12:
            signals.append("healthy")
        elif roe >= 5:
            signals.append("moderate")
        else:
            signals.append("weak")

    if roce is not None:
        if roce >= 20:
            signals.append("strong")
        elif roce >= 12:
            signals.append("healthy")
        elif roce >= 5:
            signals.append("moderate")
        else:
            signals.append("weak")

    if operating_margin is not None:
        if operating_margin >= 20:
            signals.append("strong")
        elif operating_margin >= 10:
            signals.append("healthy")
        elif operating_margin >= 5:
            signals.append("moderate")
        else:
            signals.append("weak")

    if net_margin is not None:
        if net_margin >= 15:
            signals.append("strong")
        elif net_margin >= 8:
            signals.append("healthy")
        elif net_margin >= 3:
            signals.append("moderate")
        else:
            signals.append("weak")

    if not signals:
        return "unknown"

    score = {
        "strong": 3,
        "healthy": 2,
        "moderate": 1,
        "weak": 0,
    }

    average_score = sum(score[value] for value in signals) / len(signals)

    if average_score >= 2.5:
        return "strong"

    if average_score >= 1.5:
        return "healthy"

    if average_score >= 0.5:
        return "moderate"

    return "weak"

def consistency_signal(
    profit_growth_history: list[Optional[float]],
) -> str:
    """
    Estimate earnings consistency from historical profit growth.
    """

    values = [
        value
        for value in profit_growth_history
        if value is not None
    ]

    if not values:
        return "unknown"

    positive_periods = sum(
        1 for value in values
        if value >= 0
    )

    consistency_ratio = positive_periods / len(values)

    if consistency_ratio >= 0.8:
        return "strong"

    if consistency_ratio >= 0.6:
        return "healthy"

    if consistency_ratio >= 0.4:
        return "moderate"

    return "weak"
def ipo_valuation_signal(pe_ratio: Optional[float]) -> str:
    """
    Estimate IPO valuation level from P/E.

    These are MVP heuristics and should not be treated
    as universal valuation rules.
    """

    if pe_ratio is None:
        return "unknown"

    if pe_ratio <= 15:
        return "low"

    if pe_ratio <= 25:
        return "moderate"

    if pe_ratio <= 40:
        return "elevated"

    return "high"
def ipo_risk_signal(
    *,
    debt_signal_value: str = "unknown",
    profitability_signal_value: str = "unknown",
    valuation_signal_value: str = "unknown",
    ofs_percentage: Optional[float] = None,
) -> str:
    """
    Estimate IPO risk from multiple structured risk factors.

    These are MVP heuristics, not investment recommendations.
    """

    risk_score = 0

    # Debt risk
    if debt_signal_value == "high":
        risk_score += 2
    elif debt_signal_value == "elevated":
        risk_score += 1

    # Profitability risk
    if profitability_signal_value == "weak":
        risk_score += 2
    elif profitability_signal_value == "moderate":
        risk_score += 1

    # Valuation risk
    if valuation_signal_value == "high":
        risk_score += 2
    elif valuation_signal_value == "elevated":
        risk_score += 1

    # High OFS can be an additional issue-structure consideration.
    if ofs_percentage is not None:
        if ofs_percentage >= 75:
            risk_score += 2
        elif ofs_percentage >= 50:
            risk_score += 1

    if risk_score >= 5:
        return "high"

    if risk_score >= 1:
        return "moderate"

    return "low"