from decimal import Decimal
from uuid import uuid4

import pytest

from app.ai.schemas.analysis import HistoricalAnalysis
from app.ai.schemas.intent import AssetType, InvestmentHorizon
from app.ai.schemas.market_data import MarketAssetData
from app.ai.schemas.research import ResearchRequest
from app.ai.services.research_service import ResearchService
from app.ai.schemas.recommendation import RecommendationLabel
from app.ai.schemas.risk import RiskLevel

class FakeMarketDataService:

    def __init__(
        self,
        assets: list[MarketAssetData],
    ) -> None:
        self.assets = assets

    async def search_assets(
        self,
        *,
        query: str | None = None,
        asset_type: str | None = None,
        limit: int = 20,
    ) -> list[MarketAssetData]:

        return self.assets


class FakeHistoricalAnalysisService:

    def __init__(
        self,
        analysis: HistoricalAnalysis,
    ) -> None:
        self.analysis = analysis
        self.requested_asset_ids = []

    async def analyze(
        self,
        *,
        asset_id,
        lookback_days: int,
        exchange=None,
    ) -> HistoricalAnalysis:

        self.requested_asset_ids.append(
            (asset_id, lookback_days, exchange)
        )

        return self.analysis


@pytest.mark.asyncio
async def test_research_service_combines_market_and_historical_data():

    asset_id = uuid4()

    market_data = MarketAssetData(
    asset_id=asset_id,
    name="Reliance Industries",
    symbol="RELIANCE",
    asset_type="stock",
    exchange="NSE",
    sector="Energy",
    current_price=Decimal("1500"),
    pe_ratio=Decimal("18"),
    roe=Decimal("20"),
    debt_to_equity=Decimal("0.4"),
)

    historical_analysis = HistoricalAnalysis(
        asset_id=asset_id,
        current_price=Decimal("1500"),
        period_return_percent=Decimal("12.50"),
        highest_price=Decimal("1650"),
        lowest_price=Decimal("1300"),
        volatility_percent=Decimal("2.50"),
        observation_count=250,
        start_timestamp=None,
        end_timestamp=None,
    )

    market_service = FakeMarketDataService(
        assets=[market_data]
    )

    historical_service = FakeHistoricalAnalysisService(
        analysis=historical_analysis
    )

    research_service = ResearchService(
        market_data_service=market_service,
        historical_analysis_service=historical_service,
    )

    request = ResearchRequest(
        asset_type=AssetType.STOCK,
        asset_name="Reliance",
        horizon=InvestmentHorizon.LONG_TERM,
    )

    results = await research_service.research(request)

    assert len(results) == 1

    result = results[0]

    assert result.market_data.asset_id == asset_id
    assert result.market_data.symbol == "RELIANCE"

    assert result.historical_analysis is not None
    assert result.signals is not None

    assert (
        result.signals.overall_direction.value
        == "positive"
    )

    assert (
        result.historical_analysis.period_return_percent
        == Decimal("12.50")
    )

    assert (
        result.historical_analysis.volatility_percent
        == Decimal("2.50")
    )

    assert historical_service.requested_asset_ids == [
       (asset_id, 365, "NSE")
    ]
    assert result.recommendation is not None
    assert (
        result.recommendation.label
        == RecommendationLabel.FAVORABLE_FOR_RESEARCH
    )

    assert result.risk_assessment is not None
    assert (
    result.risk_assessment.overall_level
    == RiskLevel.MODERATE
)


@pytest.mark.asyncio
async def test_research_service_skips_historical_analysis_for_non_stock():

    asset_id = uuid4()

    market_data = MarketAssetData(
        asset_id=asset_id,
        name="Example Mutual Fund",
        symbol="EXAMPLEMF",
        asset_type="mutual_fund",
        exchange=None,
        sector=None,
        current_price=Decimal("100"),
        nav=Decimal("100"),
    )

    historical_analysis = HistoricalAnalysis(
        asset_id=asset_id,
        current_price=Decimal("100"),
        period_return_percent=Decimal("10"),
        highest_price=Decimal("110"),
        lowest_price=Decimal("90"),
        volatility_percent=Decimal("2"),
        observation_count=100,
        start_timestamp=None,
        end_timestamp=None,
    )

    market_service = FakeMarketDataService(
        assets=[market_data]
    )

    historical_service = FakeHistoricalAnalysisService(
        analysis=historical_analysis
    )

    research_service = ResearchService(
        market_data_service=market_service,
        historical_analysis_service=historical_service,
    )

    request = ResearchRequest(
        asset_type=AssetType.MUTUAL_FUND,
        asset_name="Example Mutual Fund",
    )

    results = await research_service.research(request)

    assert len(results) == 1

    result = results[0]

    assert result.market_data.asset_type == "mutual_fund"

    assert result.historical_analysis is None

    assert historical_service.requested_asset_ids == []