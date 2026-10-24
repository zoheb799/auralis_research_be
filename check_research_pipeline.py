import asyncio
from pprint import pprint

from app.db.session import AsyncSessionLocal
from app.ai.schemas.intent import AssetType
from app.ai.schemas.research import ResearchRequest
from app.ai.services.market_data_service import MarketDataService
from app.ai.services.historical_analysis_service import (
    HistoricalAnalysisService,
)
from app.ai.services.research_service import ResearchService


async def main():
    async with AsyncSessionLocal() as db:
        market_data_service = MarketDataService(db)
        historical_analysis_service = HistoricalAnalysisService(db)

        research_service = ResearchService(
            market_data_service=market_data_service,
            historical_analysis_service=historical_analysis_service,
        )

        request = ResearchRequest(
            asset_type=AssetType.STOCK,
            asset_name="Reliance",
        )

        results = await research_service.research(request)

        if not results:
            print("No matching stock found.")
            return

        for result in results:
            print("\n========== MARKET DATA ==========")
            pprint(result.market_data.model_dump())

            print("\n========== HISTORICAL ANALYSIS ==========")
            if result.historical_analysis:
                pprint(result.historical_analysis.model_dump())
            else:
                print("No historical analysis available.")

            print("\n========== SIGNALS ==========")
            if result.signals:
                pprint(result.signals.model_dump())
            else:
                print("No signals available.")

            print("\n========== RECOMMENDATION ==========")
            if result.recommendation:
                pprint(result.recommendation.model_dump())
            else:
                print("No recommendation available.")

            print("\n========== RISK ASSESSMENT ==========")
            if result.risk_assessment:
                pprint(result.risk_assessment.model_dump())
            else:
                print("No risk assessment available.")


if __name__ == "__main__":
    asyncio.run(main())