from secrets import compare_digest

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import settings


PUBLIC_PATHS = {
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/health",
}
MARKET_DATA_SYNC_PATH = (
    f"{settings.api_v1_prefix.rstrip('/')}/internal/market-data/sync/"
)


async def api_key_middleware(
    request: Request,
    call_next,
):
    if request.method == "OPTIONS":
        return await call_next(request)

    if request.url.path in PUBLIC_PATHS:
        return await call_next(request)

    if request.url.path.startswith(MARKET_DATA_SYNC_PATH):
        return await call_next(request)

    api_key = request.headers.get("X-API-Key")

    if not api_key:
        return JSONResponse(
            status_code=401,
            content={
                "detail": "Missing X-API-Key header"
            },
        )

    if not compare_digest(api_key, settings.x_api_key):
        return JSONResponse(
            status_code=401,
            content={
                "detail": "Invalid API key"
            },
        )

    return await call_next(request)