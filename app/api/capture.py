from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import require_player
from app.models.player import GamePlayer
from app.models.game import Game
from app.schemas.capture import CaptureRequest, CaptureResponse
from app.services import capture_service, game_service

router = APIRouter(prefix="/api/captures", tags=["抓捕"])


@router.post("/", response_model=CaptureResponse)
async def capture_mouse(
    req: CaptureRequest,
    payload: dict = Depends(require_player),
    db: AsyncSession = Depends(get_db)
):
    """猫扫描鼠的二维码进行抓捕"""
    # Get current game
    game = await game_service.get_current_game(db)

    # Get cat's game_player with player eagerly loaded
    game_player_id = payload.get("game_player_id")
    result = await db.execute(
        select(GamePlayer)
        .options(selectinload(GamePlayer.player))
        .where(GamePlayer.id == game_player_id)
    )
    cat = result.scalar_one_or_none()
    if cat is None:
        raise HTTPException(status_code=404, detail="玩家数据不存在")

    return await capture_service.capture_mouse(db, game, cat, req.qr_token)
