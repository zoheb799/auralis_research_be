
from app.ai.analysis.recommendation_engine import RecommendationEngine
from app.ai.analysis.risk_assessment_engine import RiskAssessmentEngine
from app.ai.analysis.signal_engine import SignalEngine
from app.ai.schemas.research import ResearchRequest
from app.ai.schemas.research_result import ResearchAssetResult
from app.ai.services.historical_analysis_service import (
    HistoricalAnalysisService,
)
from app.ai.services.market_data_service import MarketDataService


class ResearchService:
    def __init__(
        self,
        market_data_service: MarketDataService,
        historical_analysis_service: HistoricalAnalysisService,
    ) -> None:
        self.market_data_service = market_data_service
        self.historical_analysis_service = historical_analysis_service

    async def research(
        self,
        request: ResearchRequest,
    ) -> list[ResearchAssetResult]:
        assets = await self.market_data_service.search_assets(
            query=request.asset_name,
            asset_type=(
                request.asset_type.value
                if request.asset_type.value != "unknown"
                else None
            ),
        )

        results: list[ResearchAssetResult] = []

        for asset in assets:
            historical_analysis = None
            signals = None
            recommendation = None
            risk_assessment = None

            if asset.asset_type == "stock":
                historical_analysis = await self.historical_analysis_service.analyze(
                    asset_id=asset.asset_id,
                    lookback_days=365,
                    exchange=asset.exchange,
                )

                signals = SignalEngine.analyze(
                    asset=asset,
                    historical_analysis=historical_analysis,
                )

                recommendation = RecommendationEngine.evaluate(signals)

                risk_assessment = RiskAssessmentEngine.assess(
                    asset=asset,
                    historical_analysis=historical_analysis,
                )

            results.append(
                ResearchAssetResult(
                    market_data=asset,
                    historical_analysis=historical_analysis,
                    signals=signals,
                    recommendation=recommendation,
                    risk_assessment=risk_assessment,
                )
            )

        return results

