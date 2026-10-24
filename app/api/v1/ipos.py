from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.repositories.ipo_repository import IPORepository
from app.schemas.analysis import IPOAnalysisResponse
from app.schemas.ipo import IPODetailResponse, IPOListResponse
from app.services.analysis_service import get_ipo_analysis
from app.services.ipo_service import list_ipos


router = APIRouter(
    prefix="/ipos",
    tags=["IPOs"],
)


@router.get(
    "/",
    response_model=IPOListResponse,
)
async def get_ipos(
    search: str | None = Query(default=None),
    status_filter: str | None = Query(
        default=None,
        alias="status",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    db: AsyncSession = Depends(get_db),
):
    return await list_ipos(
        db=db,
        search=search,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{asset_id}",
    response_model=IPODetailResponse,
)
async def get_ipo_detail_endpoint(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> IPODetailResponse:
    repository = IPORepository(db)
    data = await repository.get_ipo_detail(asset_id)

    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="IPO not found",
        )

    asset = data["asset"]
    ipo = data["ipo"]

    return IPODetailResponse(
        id=asset.id,
        name=asset.name,
        symbol=asset.symbol,
        exchange=asset.exchange,
        sector=asset.sector,
        description=asset.description,
        issue_price_low=(float(ipo.issue_price_low) if ipo.issue_price_low is not None else None),
        issue_price_high=(float(ipo.issue_price_high) if ipo.issue_price_high is not None else None),
        lot_size=ipo.lot_size,
        issue_size=(float(ipo.issue_size) if ipo.issue_size is not None else None),
        fresh_issue_size=None,
        open_date=(ipo.open_date.isoformat() if ipo.open_date is not None else None),
        close_date=(ipo.close_date.isoformat() if ipo.close_date is not None else None),
        listing_date=(ipo.listing_date.isoformat() if ipo.listing_date is not None else None),
        ipo_status=ipo.ipo_status,
        source_attribution=ipo.source_attribution,
        source_disclaimer=ipo.source_disclaimer,
    )


@router.get(
    "/{asset_id}/analysis",
    response_model=IPOAnalysisResponse,
)
async def get_ipo_analysis_endpoint(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> IPOAnalysisResponse:
    result = await get_ipo_analysis(db=db, asset_id=asset_id)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="IPO not found",
        )

    return result