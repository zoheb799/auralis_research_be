from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.db.models.user import User
from app.repositories.refresh_token_repository import (
    RefreshTokenRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest


class AuthService:

    def __init__(self, db: AsyncSession):
        self.user_repository = UserRepository(db)
        self.refresh_token_repository = RefreshTokenRepository(db)

    async def register(
        self,
        data: RegisterRequest,
    ) -> User:

        existing_user = await self.user_repository.get_by_email(
            data.email
        )

        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        user = User(
            name=data.name,
            email=data.email,
            password_hash=hash_password(data.password),
        )

        return await self.user_repository.create(user)

    async def login(
        self,
        data: LoginRequest,
    ) -> tuple[User, str, str]:

        user = await self.user_repository.get_by_email(
            data.email
        )

        if not user or not verify_password(
            data.password,
            user.password_hash,
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        access_token = create_access_token(str(user.id))

        refresh_token, expires_at = create_refresh_token(
            str(user.id)
        )

        await self.refresh_token_repository.create(
            user_id=user.id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=expires_at,
        )

        return user, access_token, refresh_token

    async def refresh(
        self,
        refresh_token: str,
    ) -> str:
        token_hash = hash_refresh_token(refresh_token)

        stored_token = await self.refresh_token_repository.get_valid_token(
            token_hash
        )

        if not stored_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        user = await self.user_repository.get_by_id(
            stored_token.user_id
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        return create_access_token(str(user.id))


    async def logout(
        self,
        refresh_token: str,
    ) -> None:
        token_hash = hash_refresh_token(refresh_token)

        stored_token = await self.refresh_token_repository.get_valid_token(
            token_hash
        )

        if not stored_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        await self.refresh_token_repository.revoke(stored_token)