from fastapi import APIRouter

from app.api.v1 import economy, regions, chat

router = APIRouter()

# 경제 분석 라우터
router.include_router(
    economy.router,
    prefix="/economy",
    tags=["economy"],
)

# 지역 정보 라우터
router.include_router(
    regions.router,
    prefix="/regions",
    tags=["regions"],
)

# AI 채팅 라우터
router.include_router(
    chat.router,
    prefix="/chat",
    tags=["chat"],
)
