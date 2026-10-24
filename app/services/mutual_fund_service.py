from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.mutual_fund_repository import (
    MutualFundRepository,
)
from app.schemas.mutual_fund import (
    MutualFundListItem,
    MutualFundListResponse,
)


async def list_mutual_funds(
    db: AsyncSession,
    search: str | None = None,
    category: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> MutualFundListResponse:

    repository = MutualFundRepository(db)

    items, total = await repository.list_mutual_funds(
        search=search,
        category=category,
        page=page,
        page_size=page_size,
    )

    return MutualFundListResponse(
        items=[
            MutualFundListItem.model_validate(item)
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )