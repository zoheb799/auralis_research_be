from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from app.ai.schemas.intent import AssetType
from app.ai.schemas.research import ResearchRequest
from app.ai.schemas.market_data import MarketAssetData
from app.ai.schemas.research_explanation import ResearchExplanation
from app.ai.schemas.research_result import ResearchAssetResult
from app.ai.services.research_explanation_service import (
    ResearchExplanationService,
)


@pytest.mark.asyncio
async def test_explanation_uses_structured_research_evidence():
    market_data = MarketAssetData(
    asset_id=uuid4(),
    name="Reliance Industries",
    symbol="RELIANCE",
    asset_type="stock",
    exchange="NSE",
    sector="Energy",
    current_price=1500,
)

    research_result = ResearchAssetResult(
        market_data=market_data,
    )

    expected = ResearchExplanation(
        summary="Limited research data is available.",
        key_findings=["The supplied current price is ₹1500."],
        risks=["Available data is insufficient for a complete assessment."],
        limitations=["Historical analysis is unavailable."],
    )

    ai_service = AsyncMock()
    ai_service.generate_structured.return_value = expected

    service = ResearchExplanationService(ai_service)

    request = ResearchRequest(
        asset_type=AssetType.STOCK,
    )

    result = await service.explain(
        [research_result],
        request,
    )

    assert result == expected
    assert result.disclaimer

    ai_service.generate_structured.assert_awaited_once()

    kwargs = ai_service.generate_structured.await_args.kwargs

    assert kwargs["response_model"] is ResearchExplanation
    assert "Reliance Industries" in kwargs["user_prompt"]
    assert "Do not fill missing fields with guesses" in kwargs["user_prompt"]
    assert "User question:" in kwargs["user_prompt"]
    assert "Start with a direct, conversational answer" in kwargs["user_prompt"]


@pytest.mark.asyncio
async def test_explanation_service_uses_original_question_when_provided():
    market_data = MarketAssetData(
        asset_id=uuid4(),
        name="Reliance Industries",
        symbol="RELIANCE",
        asset_type="stock",
        exchange="NSE",
        sector="Energy",
        current_price=1500,
    )

    ai_service = AsyncMock()
    ai_service.generate_structured.return_value = ResearchExplanation(
        summary="Based on the available evidence, Reliance looks viable for a long-term investor with a disciplined risk profile.",
        key_findings=["The company has a stable operating profile."],
        risks=["Past performance does not guarantee future results."],
        limitations=["Current data is limited."],
    )

    service = ResearchExplanationService(ai_service)
    request = ResearchRequest(asset_type=AssetType.STOCK)

    await service.explain(
        [ResearchAssetResult(market_data=market_data)],
        request,
        user_question="Is Reliance a good stock for long-term investment?",
    )

    prompt = ai_service.generate_structured.await_args.kwargs["user_prompt"]
    assert "Is Reliance a good stock for long-term investment?" in prompt
    assert "Start with a direct, conversational answer" in prompt