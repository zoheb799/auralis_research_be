from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from sqlalchemy import text

from app.db.session import engine
from app.services.market_data_sync import SyncAlreadyRunning


@asynccontextmanager
async def market_data_job_lock(job_name: str) -> AsyncIterator[None]:
    async with engine.connect() as connection:
        result = await connection.execute(
            text("SELECT pg_try_advisory_lock(hashtextextended(:job_name, 0))"),
            {"job_name": f"auralis:market-data:{job_name}"},
        )
        acquired = bool(result.scalar_one())
        await connection.commit()
        if not acquired:
            raise SyncAlreadyRunning(f"{job_name} sync is already running")
        try:
            yield
        finally:
            await connection.execute(
                text("SELECT pg_advisory_unlock(hashtextextended(:job_name, 0))"),
                {"job_name": f"auralis:market-data:{job_name}"},
            )
            await connection.commit()