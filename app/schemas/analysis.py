from typing import Optional

from pydantic import BaseModel


# -------------------------
# Stock Analysis
# -------------------------

class GrowthAnalysis(BaseModel):
    revenue_growth: Optional[float] = None
    profit_growth: Optional[float] = None
    signal: str


class ProfitabilityAnalysis(BaseModel):
    roe: Optional[float] = None
    roce: Optional[float] = None
    operating_margin: Optional[float] = None
    net_margin: Optional[float] = None
    signal: str


class ValuationAnalysis(BaseModel):
    pe_ratio: Optional[float] = None
    signal: str


class DebtAnalysis(BaseModel):
    debt_to_equity: Optional[float] = None
    signal: str


class QualityAnalysis(BaseModel):
    profitability: Optional[str] = None
    growth: Optional[str] = None
    consistency: Optional[str] = None
    signal: str


class MomentumAnalysis(BaseModel):
    return_1y: Optional[float] = None
    signal: str


class RiskAnalysis(BaseModel):
    volatility: Optional[float] = None
    signal: str


class StockAnalysisResponse(BaseModel):
    growth: GrowthAnalysis
    profitability: ProfitabilityAnalysis
    valuation: ValuationAnalysis
    debt: DebtAnalysis
    quality: QualityAnalysis
    momentum: MomentumAnalysis
    risk: RiskAnalysis


# -------------------------
# IPO Analysis
# -------------------------

class IPOIssueStructureAnalysis(BaseModel):
    issue_price_low: Optional[float] = None
    issue_price_high: Optional[float] = None
    lot_size: Optional[int] = None
    issue_size: Optional[float] = None
    fresh_issue_size: Optional[float] = None
    ofs_size: Optional[float] = None
    ofs_percentage: Optional[float] = None


class IPORiskAnalysis(BaseModel):
    debt: str
    profitability: str
    valuation: str
    ofs_percentage: Optional[float] = None
    signal: str


class IPOAnalysisResponse(BaseModel):
    growth: GrowthAnalysis
    profitability: ProfitabilityAnalysis
    valuation: ValuationAnalysis
    issue_structure: IPOIssueStructureAnalysis
    risk: IPORiskAnalysis


# -------------------------
# Mutual Fund Analysis
# -------------------------

class MutualFundReturnsAnalysis(BaseModel):
    return_1y: Optional[float] = None
    return_3y: Optional[float] = None
    return_5y: Optional[float] = None
    signal: str


class BenchmarkAnalysis(BaseModel):
    fund_return_1y: Optional[float] = None
    benchmark_return_1y: Optional[float] = None
    signal: str


class ExpenseRatioAnalysis(BaseModel):
    expense_ratio: Optional[float] = None
    signal: str


class VolatilityAnalysis(BaseModel):
    volatility: Optional[float] = None
    signal: str


class SharpeAnalysis(BaseModel):
    sharpe_ratio: Optional[float] = None
    signal: str


class ConcentrationAnalysis(BaseModel):
    top_10_percentage: Optional[float] = None
    signal: str


class ConsistencyAnalysis(BaseModel):
    positive_periods: Optional[int] = None
    total_periods: Optional[int] = None
    signal: str


class MutualFundRiskAnalysis(BaseModel):
    volatility: Optional[float] = None
    concentration: Optional[float] = None
    signal: str


class MutualFundAnalysisResponse(BaseModel):
    returns: MutualFundReturnsAnalysis
    benchmark: BenchmarkAnalysis
    expense_ratio: ExpenseRatioAnalysis
    volatility: VolatilityAnalysis
    sharpe: SharpeAnalysis
    concentration: ConcentrationAnalysis
    consistency: ConsistencyAnalysis
    risk: MutualFundRiskAnalysis