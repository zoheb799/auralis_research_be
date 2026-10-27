import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.db.session import AsyncSessionLocal, engine
from app.integrations.market_data.registry import MarketDataProviderRegistry
from app.services.market_data_sync import MarketDataSyncService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safely sync real stock fundamentals from the configured provider."
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--symbol")
    parser.add_argument("--exchange", choices=("NSE", "BSE"))
    parser.add_argument(
        "--provider",
        choices=("bharatstock", "alphavantage"),
        help="Overrides MARKET_DATA_FUNDAMENTALS_PROVIDER for this run.",
    )
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--force-refresh", action="store_true")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be greater than zero")
    return args


async def run(args: argparse.Namespace) -> None:
    run_settings = settings
    if args.provider:
        run_settings = settings.model_copy(
            update={"market_data_fundamentals_provider": args.provider}
        )

    try:
        async with httpx.AsyncClient(
            timeout=run_settings.market_data_request_timeout
        ) as client:
            async with AsyncSessionLocal() as db:
                service = MarketDataSyncService(
                    db,
                    run_settings,
                    MarketDataProviderRegistry(run_settings, client),
                )
                summary = await service.sync_stock_fundamentals(
                    dry_run=args.dry_run,
                    limit=args.limit,
                    symbol=args.symbol,
                    exchange=args.exchange,
                    retry_failed=args.retry_failed,
                    force_refresh=args.force_refresh,
                )
        print(
            json.dumps(
                {"dry_run": args.dry_run, **summary.model_dump()},
                default=str,
                indent=2,
            )
        )
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(run(parse_args()))


if __name__ == "__main__":
    main()
