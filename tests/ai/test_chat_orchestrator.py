
from app.ai.schemas.intent import (
    AssetType,
    IntentType,
    InvestmentHorizon,
    InvestmentIntent,
)
from app.ai.schemas.research_explanation import ResearchExplanation

from unittest.mock import AsyncMock

import pytest

from app.ai.orchestrator.chat_orchestrator import ChatOrchestrator

@pytest.mark.asyncio
async def test_research_request_uses_research_pipeline():
    query = "Analyze Reliance for long-term investment with 50000."

    ai_service = AsyncMock()
    ai_service.generate.return_value = "Normal chat response"

    intent_service = AsyncMock()
    intent_service.extract.return_value = InvestmentIntent(
        asset_type=AssetType.STOCK,
        investment_amount=50000,
        horizon=InvestmentHorizon.LONG_TERM,
        asset_name="Reliance",
        user_query=query,
    )

    research_service = AsyncMock()
    research_service.research.return_value = [object()]

    explanation_service = AsyncMock()
    explanation_service.explain.return_value = ResearchExplanation(
        summary="Reliance research summary.",
        key_findings=["Historical data was assessed."],
        risks=["Market prices can decline."],
        limitations=["Past returns do not predict future returns."],
    )

    orchestrator = ChatOrchestrator(
        ai_service=ai_service,
        research_service=research_service,
        intent_extraction_service=intent_service,
        research_explanation_service=explanation_service,
    )

    result = await orchestrator.chat(query)

    assert "Reliance research summary." in result
    intent_service.extract.assert_awaited_once_with(query)
    research_service.research.assert_awaited_once()
    explanation_service.explain.assert_awaited_once()
    ai_service.generate.assert_not_awaited()
    assert explanation_service.explain.await_args.kwargs["user_question"] == query


@pytest.mark.asyncio
async def test_research_request_with_no_matching_assets_does_not_call_explainer():
    query = "Research Reliance stock."

    ai_service = AsyncMock()
    intent_service = AsyncMock()
    intent_service.extract.return_value = InvestmentIntent(
        asset_type=AssetType.STOCK,
        asset_name="Reliance",
        user_query=query,
    )

    research_service = AsyncMock()
    research_service.research.return_value = []

    explanation_service = AsyncMock()

    orchestrator = ChatOrchestrator(
        ai_service=ai_service,
        research_service=research_service,
        intent_extraction_service=intent_service,
        research_explanation_service=explanation_service,
    )

    result = await orchestrator.chat(query)

    assert "no matching" in result.lower()
    explanation_service.explain.assert_not_awaited()
    ai_service.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_general_chat_does_not_trigger_research_pipeline():
    query = "Hi, how are you?"

    ai_service = AsyncMock()
    ai_service.generate.return_value = "Hello there!"

    intent_service = AsyncMock()
    intent_service.extract.return_value = InvestmentIntent(
        intent_type=IntentType.GENERAL_CHAT,
        user_query=query,
    )

    research_service = AsyncMock()
    explanation_service = AsyncMock()

    orchestrator = ChatOrchestrator(
        ai_service=ai_service,
        research_service=research_service,
        intent_extraction_service=intent_service,
        research_explanation_service=explanation_service,
    )

    result = await orchestrator.chat(query)

    assert result == "Hello there!"
    intent_service.extract.assert_awaited_once_with(query)
    research_service.research.assert_not_awaited()
    explanation_service.explain.assert_not_awaited()
    ai_service.generate.assert_awaited_once()