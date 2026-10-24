from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.repositories.mutual_fund_repository import MutualFundRepository
from app.schemas.analysis import MutualFundAnalysisResponse
from app.schemas.mutual_fund import MutualFundDetailResponse, MutualFundListResponse
from app.services.analysis_service import get_mutual_fund_analysis
from app.services.mutual_fund_service import list_mutual_funds


router = APIRouter(
    prefix="/mutual-funds",
    tags=["Mutual Funds"],
)


@router.get(
    "/",
    response_model=MutualFundListResponse,
)
async def get_mutual_funds(
    search: str | None = Query(default=None),
    category: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    db: AsyncSession = Depends(get_db),
):
    return await list_mutual_funds(
        db=db,
        search=search,
        category=category,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{asset_id}",
    response_model=MutualFundDetailResponse,
)
async def get_mutual_fund_detail_endpoint(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> MutualFundDetailResponse:
    repository = MutualFundRepository(db)
    data = await repository.get_mutual_fund_detail(asset_id)

    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mutual fund not found",
        )

    asset = data["asset"]
    fund = data["fund"]

    return MutualFundDetailResponse(
        id=asset.id,
        name=asset.name,
        symbol=asset.symbol,
        exchange=asset.exchange,
        sector=asset.sector,
        description=asset.description,
        fund_house=fund.fund_house,
        category=fund.category,
        nav=(float(fund.nav) if fund.nav is not None else None),
        aum=(float(fund.aum) if fund.aum is not None else None),
        expense_ratio=(float(fund.expense_ratio) if fund.expense_ratio is not None else None),
        risk_level=fund.risk_level,
    )


@router.get(
    "/{asset_id}/analysis",
    response_model=MutualFundAnalysisResponse,
)
async def get_mutual_fund_analysis_endpoint(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> MutualFundAnalysisResponse:
    result = await get_mutual_fund_analysis(db=db, asset_id=asset_id)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mutual fund not found",
        )

    return result