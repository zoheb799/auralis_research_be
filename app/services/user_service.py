from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.repositories.user_repository import UserRepository


class UserService:

    def __init__(self, db: AsyncSession):
        self.user_repository = UserRepository(db)

    async def get_profile(
        self,
        user: User,
    ) -> User:
        return user

    async def update_profile(
        self,
        user: User,
        name: str,
    ) -> User:
        return await self.user_repository.update_name(
            user=user,
            name=name,
        )