from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.schemas.analysis import StockAnalysisResponse
from app.schemas.stock import (
    StockDetailResponse,
    StockListResponse,
)
from app.services.analysis_service import get_stock_analysis
from app.services.stock_service import (
    get_stock_detail,
    list_stocks,
)


router = APIRouter(
    prefix="/stocks",
    tags=["Stocks"],
)


@router.get(
    "/",
    response_model=StockListResponse,
)
async def get_stocks(
    search: str | None = Query(
        default=None,
        description="Search by stock name or symbol",
    ),
    sort: str = Query(
        default="name",
        pattern="^(name|price|symbol)$",
    ),
    order: str = Query(
        default="asc",
        pattern="^(asc|desc)$",
    ),
    page: int = Query(
        default=1,
        ge=1,
    ),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    db: AsyncSession = Depends(get_db),
) -> StockListResponse:
    return await list_stocks(
        db=db,
        search=search,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )

@router.get(
    "/{asset_id}",
    response_model=StockDetailResponse,
)
async def get_stock_detail_endpoint(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> StockDetailResponse:
    result = await get_stock_detail(
        db=db,
        asset_id=asset_id,
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stock not found",
        )

    return result
@router.get(
    "/{asset_id}/analysis",
    response_model=StockAnalysisResponse,
)
async def get_stock_analysis_endpoint(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> StockAnalysisResponse:
    result = await get_stock_analysis(
        db=db,
        asset_id=asset_id,
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stock not found",
        )

    return result