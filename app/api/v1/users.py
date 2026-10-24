from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.db.models.user import User
from app.schemas.user import (
    UpdateUserProfileRequest,
    UserProfileResponse,
)
from app.services.user_service import UserService


router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.get(
    "/me",
    response_model=UserProfileResponse,
)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    return UserProfileResponse(
        id=str(current_user.id),
        name=current_user.name,
        email=current_user.email,
        created_at=current_user.created_at,
    )


@router.patch(
    "/me",
    response_model=UserProfileResponse,
)
async def update_my_profile(
    data: UpdateUserProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)

    user = await service.update_profile(
        user=current_user,
        name=data.name,
    )

    return UserProfileResponse(
        id=str(user.id),
        name=user.name,
        email=user.email,
        created_at=user.created_at,
    )