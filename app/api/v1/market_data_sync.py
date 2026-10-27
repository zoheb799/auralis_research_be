import logging
from time import perf_counter
from datetime import datetime, timezone
from collections.abc import Awaitable, Callable
from secrets import compare_digest
from uuid import uuid4

import httpx
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import get_db
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.db.models.market_data_sync_state import MarketDataSyncState
from app.integrations.market_data.errors import MarketDataError, ProviderRateLimitError
from app.integrations.market_data.registry import MarketDataProviderRegistry
from app.integrations.market_data.schemas import (
    StockCatalogSyncSummary,
    SyncSummary,
)
from app.services.market_data_lock import market_data_job_lock
from app.services.market_data_sync import MarketDataSyncService, SyncAlreadyRunning


router = APIRouter(
    prefix="/internal/market-data/sync",
    tags=["Internal Market Data Sync"],
)
logger = logging.getLogger(__name__)


async def authenticate_cron(
    x_cron_secret: str | None = Header(default=None, alias="X-Cron-Secret"),
) -> None:
    expected = settings.market_data_cron_secret
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Market-data cron authentication is not configured",
        )
    if not x_cron_secret or not compare_digest(x_cron_secret, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid cron credentials",
        )
    if not settings.market_data_sync_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Market-data synchronization is disabled",
        )


def get_sync_service(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MarketDataSyncService:
    client: httpx.AsyncClient = request.app.state.market_data_http_client
    registry = MarketDataProviderRegistry(settings, client)
    return MarketDataSyncService(db, settings, registry)


async def run_locked(
    job: str,
    operation: Callable[[], Awaitable[SyncSummary]],
    service: MarketDataSyncService,
) -> SyncSummary:
    started_at = datetime.now(timezone.utc)
    started = perf_counter()
    run_summary = SyncSummary(
        job=job,
        provider=_provider_for_job(job),
    )
    try:
        async with market_data_job_lock(job):
            await service.record_sync_state(
                run_summary,
                status="running",
                started_at=started_at,
            )
            summary = await operation()
            summary.job_id = run_summary.job_id
            summary.duration_seconds = perf_counter() - started
            await service.record_sync_state(
                summary,
                status="success",
                started_at=started_at,
            )
            logger.info(
                "market_data_sync_complete job_id=%s job=%s provider=%s discovered=%s inserted=%s updated=%s skipped=%s duration_seconds=%.3f",
                summary.job_id,
                summary.job,
                summary.provider,
                summary.discovered,
                summary.inserted,
                summary.updated,
                summary.skipped,
                summary.duration_seconds,
            )
            return summary
    except SyncAlreadyRunning as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ProviderRateLimitError as exc:
        await service.db.rollback()
        failed_summary = run_summary.model_copy(
            update={"failed": 1, "duration_seconds": perf_counter() - started}
        )
        try:
            await service.record_sync_state(
                failed_summary,
                status="failed",
                started_at=started_at,
                error_category=type(exc).__name__,
            )
        except SQLAlchemyError:
            await service.db.rollback()
            logger.exception(
                "market_data_sync_state_write_failed job=%s provider=%s",
                job,
                failed_summary.provider,
            )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    except MarketDataError as exc:
        await service.db.rollback()
        failed_summary = SyncSummary(
            job=job,
            provider=_provider_for_job(job),
            job_id=run_summary.job_id,
            duration_seconds=perf_counter() - started,
            failed=1,
        )
        try:
            await service.record_sync_state(
                failed_summary,
                status="failed",
                started_at=started_at,
                error_category=type(exc).__name__,
            )
        except SQLAlchemyError:
            await service.db.rollback()
            logger.exception(
                "market_data_sync_state_write_failed job=%s provider=%s",
                job,
                failed_summary.provider,
            )
        logger.warning(
            "market_data_sync_failed job_id=%s job=%s provider=%s category=%s",
            failed_summary.job_id,
            job,
            failed_summary.provider,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except SQLAlchemyError as exc:
        await service.db.rollback()
        logger.exception(
            "market_data_sync_failed job=%s provider=%s category=database",
            job,
            _provider_for_job(job),
        )
        failed_summary = run_summary.model_copy(
            update={"failed": 1, "duration_seconds": perf_counter() - started}
        )
        try:
            await service.record_sync_state(
                failed_summary,
                status="failed",
                started_at=started_at,
                error_category="database",
            )
        except SQLAlchemyError:
            await service.db.rollback()
            logger.exception(
                "market_data_sync_state_write_failed job=%s provider=%s",
                job,
                failed_summary.provider,
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Market-data sync could not persist its result",
        ) from exc
    except Exception as exc:
        await service.db.rollback()
        logger.exception(
            "market_data_sync_failed job=%s provider=%s category=unexpected",
            job,
            _provider_for_job(job),
        )
        failed_summary = run_summary.model_copy(
            update={"failed": 1, "duration_seconds": perf_counter() - started}
        )
        try:
            await service.record_sync_state(
                failed_summary,
                status="failed",
                started_at=started_at,
                error_category="unexpected",
            )
        except SQLAlchemyError:
            await service.db.rollback()
            logger.exception(
                "market_data_sync_state_write_failed job=%s provider=%s",
                job,
                failed_summary.provider,
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Market-data sync failed",
        ) from exc


def _provider_for_job(job: str) -> str:
    return {
        "all": "combined",
        "stocks": settings.market_data_stock_provider,
        "mutual-funds": settings.market_data_mutual_fund_provider,
        "ipos": settings.market_data_ipo_provider,
        "fundamentals": settings.market_data_fundamentals_provider,
    }[job]


async def _run_all_sync_in_background(
    *,
    discover: bool,
    discovery_offset: int,
    run_id: str,
    started_at: datetime,
) -> None:
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(settings.market_data_request_timeout, connect=5.0),
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    ) as client:
        async with AsyncSessionLocal() as db:
            service = MarketDataSyncService(
                db,
                settings,
                MarketDataProviderRegistry(settings, client),
            )
            operations = (
                ("stocks", lambda: service.sync_stocks(discover=discover)),
                (
                    "mutual-funds",
                    lambda: service.sync_mutual_funds(
                        discover=discover,
                        discovery_offset=discovery_offset,
                    ),
                ),
                ("ipos", service.sync_ipos),
                ("fundamentals", service.sync_stock_fundamentals),
            )
            failed = 0
            discovered = inserted = updated = skipped = 0
            try:
                for job, operation in operations:
                    try:
                        result = await run_locked(job, operation, service)
                    except HTTPException as exc:
                        failed += 1
                        logger.warning(
                            "market_data_background_job_failed run_id=%s job=%s status=%s",
                            run_id,
                            job,
                            exc.status_code,
                        )
                        continue
                    discovered += result.discovered
                    inserted += result.inserted
                    updated += result.updated
                    skipped += result.skipped

                summary = SyncSummary(
                    job="all",
                    provider="combined",
                    job_id=run_id,
                    duration_seconds=(
                        datetime.now(timezone.utc) - started_at
                    ).total_seconds(),
                    discovered=discovered,
                    inserted=inserted,
                    updated=updated,
                    skipped=skipped,
                    failed=failed,
                )
                await service.record_sync_state(
                    summary,
                    status="failed" if failed else "success",
                    started_at=started_at,
                    error_category="ChildJobFailed" if failed else None,
                )
                logger.info(
                    "market_data_background_sync_finished run_id=%s failed_jobs=%s",
                    run_id,
                    failed,
                )
            except Exception as exc:
                await db.rollback()
                logger.exception(
                    "market_data_background_sync_crashed run_id=%s",
                    run_id,
                )
                failed_summary = SyncSummary(
                    job="all",
                    provider="combined",
                    job_id=run_id,
                    duration_seconds=(
                        datetime.now(timezone.utc) - started_at
                    ).total_seconds(),
                    failed=max(1, failed),
                )
                try:
                    await service.record_sync_state(
                        failed_summary,
                        status="failed",
                        started_at=started_at,
                        error_category=type(exc).__name__,
                    )
                except SQLAlchemyError:
                    await db.rollback()
                    logger.exception(
                        "market_data_background_state_write_failed run_id=%s",
                        run_id,
                    )


@router.post("/stocks", response_model=SyncSummary)
async def sync_stocks(
    discover: bool = False,
    service: MarketDataSyncService = Depends(get_sync_service),
    _: None = Depends(authenticate_cron),
) -> SyncSummary:
    return await run_locked(
        "stocks",
        lambda: service.sync_stocks(discover=discover),
        service,
    )


@router.post("/stocks/catalog", response_model=StockCatalogSyncSummary)
async def sync_stock_catalog(
    service: MarketDataSyncService = Depends(get_sync_service),
    _: None = Depends(authenticate_cron),
) -> StockCatalogSyncSummary:
    started = perf_counter()
    try:
        async with market_data_job_lock("stocks"):
            result = await service.sync_stock_catalog()
            logger.info(
                "market_data_catalog_sync_complete source=%s fetched=%s assets_inserted=%s assets_updated=%s stock_records_inserted=%s identifiers_linked=%s duration_seconds=%.3f",
                result.source,
                result.fetched,
                result.assets_inserted,
                result.assets_updated,
                result.stock_records_inserted,
                result.identifiers_linked,
                perf_counter() - started,
            )
            return result
    except SyncAlreadyRunning as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except MarketDataError as exc:
        await service.db.rollback()
        logger.warning(
            "market_data_catalog_sync_failed category=%s",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except SQLAlchemyError as exc:
        await service.db.rollback()
        logger.exception("market_data_catalog_sync_failed category=database")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stock catalog sync could not persist its result",
        ) from exc
    except Exception as exc:
        await service.db.rollback()
        logger.exception("market_data_catalog_sync_failed category=unexpected")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Stock catalog sync failed",
        ) from exc


@router.post("/mutual-funds", response_model=SyncSummary)
async def sync_mutual_funds(
    discover: bool = False,
    discovery_offset: int = Query(default=0, ge=0),
    service: MarketDataSyncService = Depends(get_sync_service),
    _: None = Depends(authenticate_cron),
) -> SyncSummary:
    return await run_locked(
        "mutual-funds",
        lambda: service.sync_mutual_funds(
            discover=discover,
            discovery_offset=discovery_offset,
        ),
        service,
    )


@router.post("/ipos", response_model=SyncSummary)
async def sync_ipos(
    service: MarketDataSyncService = Depends(get_sync_service),
    _: None = Depends(authenticate_cron),
) -> SyncSummary:
    return await run_locked("ipos", service.sync_ipos, service)


@router.post("/fundamentals", response_model=SyncSummary)
async def sync_stock_fundamentals(
    limit: int | None = Query(default=None, ge=1),
    symbol: str | None = Query(default=None, min_length=1),
    exchange: str | None = Query(default=None, pattern="(?i)^(NSE|BSE)$"),
    retry_failed: bool = False,
    force_refresh: bool = False,
    service: MarketDataSyncService = Depends(get_sync_service),
    _: None = Depends(authenticate_cron),
) -> SyncSummary:
    return await run_locked(
        "fundamentals",
        lambda: service.sync_stock_fundamentals(
            limit=limit,
            symbol=symbol,
            exchange=exchange,
            retry_failed=retry_failed,
            force_refresh=force_refresh,
        ),
        service,
    )


@router.post("/all", status_code=status.HTTP_202_ACCEPTED)
async def sync_all(
    background_tasks: BackgroundTasks,
    discover: bool = True,
    discovery_offset: int = Query(default=0, ge=0),
    service: MarketDataSyncService = Depends(get_sync_service),
    _: None = Depends(authenticate_cron),
) -> dict[str, str]:
    run_id = str(uuid4())
    started_at = datetime.now(timezone.utc)
    await service.record_sync_state(
        SyncSummary(
            job="all",
            provider="combined",
            job_id=run_id,
        ),
        status="running",
        started_at=started_at,
    )
    background_tasks.add_task(
        _run_all_sync_in_background,
        discover=discover,
        discovery_offset=discovery_offset,
        run_id=run_id,
        started_at=started_at,
    )
    return {
        "job": "all",
        "provider": "combined",
        "job_id": run_id,
        "status": "accepted",
        "status_url": "/api/v1/internal/market-data/sync/status",
    }


@router.get("/status")
async def get_sync_status(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(authenticate_cron),
) -> list[dict]:
    result = await db.execute(
        select(MarketDataSyncState).order_by(
            MarketDataSyncState.job,
            MarketDataSyncState.provider,
        )
    )
    return [
        {
            "job": row.job,
            "provider": row.provider,
            "status": row.status,
            "last_run_id": str(row.last_run_id),
            "last_started_at": row.last_started_at,
            "last_finished_at": row.last_finished_at,
            "last_success_at": row.last_success_at,
            "duration_seconds": (
                (datetime.now(timezone.utc) - row.last_started_at).total_seconds()
                if row.status == "running"
                else float(row.duration_seconds)
            ),
            "discovered": row.discovered,
            "inserted": row.inserted,
            "updated": row.updated,
            "skipped": row.skipped,
            "failed": row.failed,
            "error_category": row.error_category,
        }
        for row in result.scalars()
    ]