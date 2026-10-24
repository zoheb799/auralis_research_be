from app.ai.llm.factory import get_llm_provider
from app.ai.llm.gemini import GeminiProvider
import asyncio

def test_get_llm_provider_returns_gemini(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "ai_provider", "gemini", raising=False)
    monkeypatch.setattr(settings, "llm_api_key", "abc123", raising=False)
    monkeypatch.setattr(settings, "llm_base_url", "https://generativelanguage.googleapis.com/v1beta", raising=False)
    monkeypatch.setattr(settings, "llm_model", "gemini-flash-latest", raising=False)
    monkeypatch.setattr(settings, "llm_timeout", 30.0, raising=False)

    provider = get_llm_provider()

    assert isinstance(provider, GeminiProvider)
    assert provider.model == "gemini-flash-latest"


def test_gemini_provider_builds_google_payload():
    provider = GeminiProvider(
        api_key="abc123",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        model="gemini-flash-latest",
    )

    payload = provider.build_payload("System prompt", "User prompt")

    assert payload["contents"][0]["role"] == "user"
    assert payload["contents"][0]["parts"][0]["text"] == "User prompt"
    assert payload["system_instruction"]["parts"][0]["text"] == "System prompt"





def test_gemini_provider_retries_on_503(monkeypatch):
    provider = GeminiProvider(
        api_key="abc123",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        model="gemini-flash-latest",
        timeout=10.0,
    )

    class FakeResponse:
        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self._payload = payload or {}
            self.text = "Service unavailable"

        @property
        def is_error(self):
            return self.status_code >= 400

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

        def json(self):
            return self._payload

    class FakeAsyncClient:
        call_count = 0

        def __init__(self, timeout=None):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            type(self).call_count += 1

            if type(self).call_count == 1:
                return FakeResponse(503)

            return FakeResponse(
                200,
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [{"text": "ok"}]
                            }
                        }
                    ]
                },
            )

    async def fake_sleep(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "app.ai.llm.gemini.httpx.AsyncClient",
        FakeAsyncClient,
    )
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    result = asyncio.run(provider.generate("system", "user"))

    assert result == "ok"
    assert FakeAsyncClient.call_count == 2

