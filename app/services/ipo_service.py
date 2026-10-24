from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.ipo_repository import IPORepository
from app.schemas.ipo import IPOListItem, IPOListResponse


async def list_ipos(
    db: AsyncSession,
    search: str | None = None,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> IPOListResponse:

    repository = IPORepository(db)

    items, total = await repository.list_ipos(
        search=search,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
    )

    return IPOListResponse(
        items=[
            IPOListItem.model_validate(item)
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )