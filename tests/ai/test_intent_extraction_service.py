from unittest.mock import AsyncMock

import pytest

from app.ai.schemas.intent import (
    AssetType,
    IntentType,
    InvestmentHorizon,
    InvestmentIntent,
)
from app.ai.services.intent_extraction_service import (
    IntentExtractionService,
)


@pytest.mark.asyncio
async def test_extracts_structured_investment_intent():
    query = "Analyze Reliance for long-term investment with 50000."

    expected = InvestmentIntent(
        asset_type=AssetType.STOCK,
        investment_amount=50000,
        horizon=InvestmentHorizon.LONG_TERM,
        asset_name="Reliance",
        user_query=query,
    )

    ai_service = AsyncMock()
    ai_service.generate_structured.return_value = expected

    service = IntentExtractionService(ai_service)

    result = await service.extract(query)

    assert result == expected

    kwargs = ai_service.generate_structured.await_args.kwargs

    assert kwargs["response_model"] is InvestmentIntent
    assert query in kwargs["user_prompt"]


def test_fast_classification_identifies_explanation_requests():
    intent = IntentExtractionService._extract_simple_intent(
        "What does P/E ratio mean?"
    )

    assert intent is not None
    assert intent.intent_type == IntentType.EXPLANATION
    assert intent.asset_type == AssetType.UNKNOWN


@pytest.mark.asyncio
async def test_rejects_empty_query_without_calling_llm():
    ai_service = AsyncMock()
    service = IntentExtractionService(ai_service)

    with pytest.raises(ValueError, match="cannot be empty"):
        await service.extract("   ")

    ai_service.generate_structured.assert_not_awaited()