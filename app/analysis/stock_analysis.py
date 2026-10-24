from typing import Optional
from app.analysis.quality_analysis import analyze_quality
from app.analysis.signals import (
    growth_signal,
    profitability_signal,
    valuation_signal,
    debt_signal,
    momentum_signal,
    risk_signal,
    quality_signal,
)
from app.analysis.financial_metrics import calculate_financial_growth

def calculate_growth(
    revenue_growth: Optional[float],
    profit_growth: Optional[float],
) -> dict:
    signals = []

    if revenue_growth is not None:
        signals.append(growth_signal(revenue_growth))

    if profit_growth is not None:
        signals.append(growth_signal(profit_growth))

    if not signals:
        overall_signal = "unknown"
    elif "negative" in signals:
        overall_signal = "negative"
    elif "strong" in signals:
        overall_signal = "strong"
    elif "positive" in signals:
        overall_signal = "positive"
    else:
        overall_signal = "stable"

    return {
        "revenue_growth": revenue_growth,
        "profit_growth": profit_growth,
        "signal": overall_signal,
    }
def analyze_financial_history(
    current_revenue: Optional[float],
    previous_revenue: Optional[float],
    current_profit: Optional[float],
    previous_profit: Optional[float],
) -> dict:
    """
    Calculate growth metrics from two financial periods.
    """

    growth = calculate_financial_growth(
        current_revenue=current_revenue,
        previous_revenue=previous_revenue,
        current_profit=current_profit,
        previous_profit=previous_profit,
    )

    return {
        "revenue_growth": growth["revenue_growth"],
        "profit_growth": growth["profit_growth"],
        "signal": growth_signal(
            growth["profit_growth"]
            if growth["profit_growth"] is not None
            else growth["revenue_growth"]
        ),
    }

def analyze_stock(
    *,
    revenue_growth: Optional[float] = None,
    profit_growth: Optional[float] = None,
    roe: Optional[float] = None,
    roce: Optional[float] = None,
    operating_margin: Optional[float] = None,
    net_margin: Optional[float] = None,
    pe_ratio: Optional[float] = None,
    debt_to_equity: Optional[float] = None,
    return_1y: Optional[float] = None,
    volatility: Optional[float] = None,
    profit_growth_history: Optional[list[Optional[float]]] = None,
) -> dict:
    """
    Analyze a stock using structured financial and market metrics.

    All calculations are deterministic.
    The LLM should consume this result rather than calculate
    financial metrics itself.
    """

    growth = calculate_growth(
        revenue_growth=revenue_growth,
        profit_growth=profit_growth,
    )

    profitability = {
        "roe": roe,
        "roce": roce,
        "operating_margin": operating_margin,
        "net_margin": net_margin,
        "signal": profitability_signal(
            roe=roe,
            roce=roce,
            operating_margin=operating_margin,
            net_margin=net_margin,
        ),
    }

    valuation = {
        "pe_ratio": pe_ratio,
        "signal": valuation_signal(pe_ratio),
    }

    debt = {
        "debt_to_equity": debt_to_equity,
        "signal": debt_signal(debt_to_equity),
    }

    momentum = {
        "return_1y": return_1y,
        "signal": momentum_signal(return_1y),
    }

    risk = {
        "volatility": volatility,
        "signal": risk_signal(
            volatility=volatility,
            debt_to_equity=debt_to_equity,
        ),
    }

    quality = analyze_quality(
    roe=roe,
    roce=roce,
    operating_margin=operating_margin,
    net_margin=net_margin,
    profit_growth=profit_growth,
    profit_growth_history=profit_growth_history,
)

    return {
        "growth": growth,
        "profitability": profitability,
        "valuation": valuation,
        "debt": debt,
        "quality": quality,
        "momentum": momentum,
        "risk": risk,
    }

