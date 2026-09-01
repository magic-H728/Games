from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import require_staff
from app.models.player import GamePlayer
from app.models.mini_game import MiniGame
from app.schemas.revive import ReviveStartRequest, ReviveCompleteRequest, ReviveResponse
from app.services import revive_service, game_service

router = APIRouter(prefix="/api/revives", tags=["复活"])


@router.post("/start")
async def start_revive(
    req: ReviveStartRequest,
    payload: dict = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    """工作人员发起复活流程"""
    game = await game_service.get_current_game(db)
    result = await revive_service.start_revive(db, game, req.qr_token, req.mini_game_id)

    mouse = result["mouse"]
    mini_game = result["mini_game"]
    attempt = result["attempt"]
    available = result["available_mini_games"]

    return {
        "success": True,
        "message": "请完成复活小游戏",
        "player_name": mouse.player.name if mouse.player else None,
        "attempt_id": attempt.id,
        "mini_game": {
            "id": mini_game.id,
            "name": mini_game.name,
            "pass_score": mini_game.pass_score,
            "is_scored": mini_game.is_scored
        },
        "available_mini_games": [
            {"id": mg.id, "name": mg.name, "pass_score": mg.pass_score}
            for mg in available
        ]
    }


@router.post("/{attempt_id}/complete", response_model=ReviveResponse)
async def complete_revive(
    attempt_id: int,
    req: ReviveCompleteRequest,
    payload: dict = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    """工作人员完成复活（小游戏结束后调用）"""
    game = await game_service.get_current_game(db)
    return await revive_service.complete_revive(db, game, attempt_id, req.score, req.passed)
