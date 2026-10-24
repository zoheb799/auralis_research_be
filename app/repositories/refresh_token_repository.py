from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.refresh_token import RefreshToken


class RefreshTokenRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> RefreshToken:

        refresh_token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        self.db.add(refresh_token)
        await self.db.commit()
        await self.db.refresh(refresh_token)

        return refresh_token

    async def get_valid_token(
        self,
        token_hash: str,
    ) -> RefreshToken | None:

        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > datetime.now(timezone.utc),
            )
        )

        return result.scalar_one_or_none()

    async def revoke(
        self,
        refresh_token: RefreshToken,
    ) -> None:

        refresh_token.revoked_at = datetime.now(timezone.utc)

        await self.db.commit()