from typing import Optional

from app.analysis.signals import (
    profitability_signal,
    growth_signal,
    consistency_signal,
)


def analyze_quality(
    *,
    roe: Optional[float] = None,
    roce: Optional[float] = None,
    operating_margin: Optional[float] = None,
    net_margin: Optional[float] = None,
    profit_growth: Optional[float] = None,
    profit_growth_history: Optional[list[Optional[float]]] = None,
) -> dict:
    """
    Analyze overall business quality using profitability,
    growth, and earnings consistency.
    """

    profitability = profitability_signal(
        roe=roe,
        roce=roce,
        operating_margin=operating_margin,
        net_margin=net_margin,
    )

    growth = growth_signal(profit_growth)

    consistency = consistency_signal(
        profit_growth_history or []
    )

    scores = {
        "strong": 3,
        "healthy": 2,
        "moderate": 1,
        "weak": 0,
        "unknown": None,
    }

    signals = [
        profitability,
        growth,
        consistency,
    ]

    available_scores = [
        scores[signal]
        for signal in signals
        if scores[signal] is not None
    ]

    if not available_scores:
        overall = "unknown"
    else:
        average_score = sum(available_scores) / len(available_scores)

        if average_score >= 2.5:
            overall = "strong"
        elif average_score >= 1.5:
            overall = "healthy"
        elif average_score >= 0.5:
            overall = "moderate"
        else:
            overall = "weak"

    return {
        "profitability": profitability,
        "growth": growth,
        "consistency": consistency,
        "signal": overall,
    }
