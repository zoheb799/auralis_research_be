from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.health.router import router as health_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.messages import router as messages_router
from app.api.v1.chat import router as chat_router
from app.api.v1.stocks import router as stocks
from app.api.v1.mutual_funds import router as mutual_funds_router
from app.api.v1.ipos import router as ipos_router
from app.api.v1.market_data_sync import router as market_data_sync_router


router = APIRouter()

router.include_router(health_router)
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(conversations_router)
router.include_router(messages_router)
router.include_router(chat_router)
router.include_router(stocks)
router.include_router(mutual_funds_router)
router.include_router(ipos_router)
router.include_router(market_data_sync_router)