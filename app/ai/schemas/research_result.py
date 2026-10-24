from pydantic import BaseModel

from app.ai.schemas.analysis import HistoricalAnalysis
from app.ai.schemas.market_data import MarketAssetData
from app.ai.schemas.recommendation import RecommendationResult
from app.ai.schemas.risk import RiskAssessment
from app.ai.schemas.signals import InvestmentSignals


class ResearchAssetResult(BaseModel):
    market_data: MarketAssetData
    historical_analysis: HistoricalAnalysis | None = None
    signals: InvestmentSignals | None = None
    recommendation: RecommendationResult | None = None
    risk_assessment: RiskAssessment | None = None