from typing import Optional

from app.analysis.financial_metrics import calculate_financial_growth
from app.analysis.signals import (
    growth_signal,
    profitability_signal,
    ipo_valuation_signal,
    ipo_risk_signal,
    debt_signal,
)


def analyze_ipo_growth(
    *,
    current_revenue: Optional[float] = None,
    previous_revenue: Optional[float] = None,
    current_profit: Optional[float] = None,
    previous_profit: Optional[float] = None,
) -> dict:
    """
    Analyze revenue and profit growth for an IPO candidate.

    Growth is calculated deterministically from financial data.
    """

    growth = calculate_financial_growth(
        current_revenue=current_revenue,
        previous_revenue=previous_revenue,
        current_profit=current_profit,
        previous_profit=previous_profit,
    )

    revenue_growth = growth["revenue_growth"]
    profit_growth = growth["profit_growth"]

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
def analyze_ipo_profitability(
    *,
    roe: Optional[float] = None,
    roce: Optional[float] = None,
    operating_margin: Optional[float] = None,
    net_margin: Optional[float] = None,
) -> dict:
    """
    Analyze profitability of an IPO candidate.
    """

    return {
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

def analyze_ipo_valuation(
    *,
    pe_ratio: Optional[float] = None,
) -> dict:
    """
    Analyze the valuation of an IPO candidate.
    """

    return {
        "pe_ratio": pe_ratio,
        "signal": ipo_valuation_signal(pe_ratio),
    }

def analyze_ipo_issue_structure(
    *,
    issue_price_low: Optional[float] = None,
    issue_price_high: Optional[float] = None,
    lot_size: Optional[int] = None,
    issue_size: Optional[float] = None,
    fresh_issue_size: Optional[float] = None,
    ofs_size: Optional[float] = None,
) -> dict:
    """
    Analyze the structural details of an IPO issue.
    """

    ofs_percentage = None

    if (
        ofs_size is not None
        and issue_size is not None
        and issue_size > 0
    ):
        ofs_percentage = (ofs_size / issue_size) * 100

    return {
        "issue_price_low": issue_price_low,
        "issue_price_high": issue_price_high,
        "lot_size": lot_size,
        "issue_size": issue_size,
        "fresh_issue_size": fresh_issue_size,
        "ofs_size": ofs_size,
        "ofs_percentage": ofs_percentage,
    }
def analyze_ipo_risk(
    *,
    debt_to_equity: Optional[float] = None,
    profitability: str = "unknown",
    valuation: str = "unknown",
    ofs_percentage: Optional[float] = None,
) -> dict:
    """
    Analyze IPO-specific risk factors.
    """

    debt = debt_signal(debt_to_equity)

    risk = ipo_risk_signal(
        debt_signal_value=debt,
        profitability_signal_value=profitability,
        valuation_signal_value=valuation,
        ofs_percentage=ofs_percentage,
    )

    return {
        "debt": debt,
        "profitability": profitability,
        "valuation": valuation,
        "ofs_percentage": ofs_percentage,
        "signal": risk,
    }
def analyze_ipo(
    *,
    current_revenue: Optional[float] = None,
    previous_revenue: Optional[float] = None,
    current_profit: Optional[float] = None,
    previous_profit: Optional[float] = None,
    roe: Optional[float] = None,
    roce: Optional[float] = None,
    operating_margin: Optional[float] = None,
    net_margin: Optional[float] = None,
    pe_ratio: Optional[float] = None,
    debt_to_equity: Optional[float] = None,
    issue_price_low: Optional[float] = None,
    issue_price_high: Optional[float] = None,
    lot_size: Optional[int] = None,
    issue_size: Optional[float] = None,
    fresh_issue_size: Optional[float] = None,
    ofs_size: Optional[float] = None,
) -> dict:
    """
    Complete deterministic analysis of an IPO candidate.
    """

    growth = analyze_ipo_growth(
        current_revenue=current_revenue,
        previous_revenue=previous_revenue,
        current_profit=current_profit,
        previous_profit=previous_profit,
    )

    profitability = analyze_ipo_profitability(
        roe=roe,
        roce=roce,
        operating_margin=operating_margin,
        net_margin=net_margin,
    )

    valuation = analyze_ipo_valuation(
        pe_ratio=pe_ratio,
    )

    issue_structure = analyze_ipo_issue_structure(
        issue_price_low=issue_price_low,
        issue_price_high=issue_price_high,
        lot_size=lot_size,
        issue_size=issue_size,
        fresh_issue_size=fresh_issue_size,
        ofs_size=ofs_size,
    )

    risk = analyze_ipo_risk(
        debt_to_equity=debt_to_equity,
        profitability=profitability["signal"],
        valuation=valuation["signal"],
        ofs_percentage=issue_structure["ofs_percentage"],
    )

    return {
        "growth": growth,
        "profitability": profitability,
        "valuation": valuation,
        "issue_structure": issue_structure,
        "risk": risk,
    }