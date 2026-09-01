from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.models.game import Game, GameStatus
from app.models.player import GamePlayer, PlayerRole, GamePlayerStatus, Player
from app.models.capture import CaptureRecord
from app.models.survival import SurvivalRecord
from app.schemas.capture import CaptureResponse


async def capture_mouse(
    db: AsyncSession,
    game: Game,
    cat: GamePlayer,
    mouse_qr_token: str
) -> CaptureResponse:
    """Cat captures a mouse by scanning QR."""
    if game.status != GameStatus.RUNNING:
        raise HTTPException(status_code=400, detail="游戏未在进行中")

    if cat.role != PlayerRole.CAT:
        raise HTTPException(status_code=400, detail="只有猫才能抓捕")

    # Find the mouse with player eagerly loaded
    result = await db.execute(
        select(GamePlayer)
        .options(selectinload(GamePlayer.player))
        .where(
            GamePlayer.qr_token == mouse_qr_token,
            GamePlayer.game_id == game.id
        )
    )
    mouse = result.scalar_one_or_none()

    if mouse is None:
        raise HTTPException(status_code=404, detail="未找到该玩家")

    if mouse.role != PlayerRole.MOUSE:
        raise HTTPException(status_code=400, detail="该玩家不是老鼠")

    if mouse.status == GamePlayerStatus.DEAD:
        raise HTTPException(status_code=400, detail="该老鼠已经死亡")

    # Check protection
    if mouse.protect_until:
        now = datetime.now(timezone.utc)
        protect_until = mouse.protect_until
        # Handle timezone-naive datetimes from SQLite
        if protect_until.tzinfo is None:
            protect_until = protect_until.replace(tzinfo=timezone.utc)
        if now < protect_until:
            remaining = (protect_until - now).total_seconds()
            raise HTTPException(status_code=400, detail=f"该老鼠处于复活保护中，剩余{int(remaining)}秒")

    # Check duplicate capture (same cat, same mouse, same survival round)
    result = await db.execute(
        select(CaptureRecord).where(
            CaptureRecord.cat_id == cat.id,
            CaptureRecord.mouse_id == mouse.id,
            CaptureRecord.survival_round == mouse.survival_round
        )
    )
    existing = result.scalar_one_or_none()
    if existing and not game.allow_repeat_capture:
        raise HTTPException(status_code=400, detail="你已经抓捕过该老鼠（本轮）")

    # Execute capture
    now = datetime.now(timezone.utc)
    mouse.status = GamePlayerStatus.DEAD
    mouse.died_at = now
    mouse.protect_until = None

    # End survival record
    result = await db.execute(
        select(SurvivalRecord).where(
            SurvivalRecord.game_player_id == mouse.id,
            SurvivalRecord.survival_round == mouse.survival_round,
            SurvivalRecord.ended_at.is_(None)
        )
    )
    survival = result.scalar_one_or_none()
    if survival:
        survival.ended_at = now
        # Handle timezone-naive datetimes from SQLite
        started = survival.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        survival.duration_seconds = (now - started).total_seconds()
        mouse.total_survival_seconds += survival.duration_seconds

    # Create capture record
    capture = CaptureRecord(
        game_id=game.id,
        cat_id=cat.id,
        mouse_id=mouse.id,
        survival_round=mouse.survival_round,
        score_awarded=game.capture_score,
        captured_at=now
    )
    db.add(capture)

    # Add score transaction for cat
    from app.models.score import ScoreTransaction, ScoreType
    score_tx = ScoreTransaction(
        game_id=game.id,
        game_player_id=cat.id,
        score=game.capture_score,
        type=ScoreType.CAPTURE,
        reason=f"抓捕 {mouse.player.name if mouse.player else '未知'}",
        related_player_id=mouse.id
    )
    db.add(score_tx)

    return CaptureResponse(
        success=True,
        message=f"成功抓捕！获得 {game.capture_score} 积分",
        cat_name=cat.player.name if cat.player else None,
        mouse_name=mouse.player.name if mouse.player else None,
        score_awarded=game.capture_score,
        captured_at=now
    )
