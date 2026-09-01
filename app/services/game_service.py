from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import select, func as sql_func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.models.game import Game, GameStatus
from app.models.player import GamePlayer, GamePlayerStatus, PlayerRole
from app.models.team import Team
from app.schemas.game import GameCreateRequest, GameResponse, GameOverviewResponse
import random


async def get_current_game(db: AsyncSession) -> Game:
    """Get the most recent active game."""
    result = await db.execute(
        select(Game).where(Game.status != GameStatus.FINISHED).order_by(Game.id.desc())
    )
    game = result.scalar_one_or_none()
    if game is None:
        raise HTTPException(status_code=404, detail="当前没有进行中的游戏")
    return game


async def get_or_create_current_game(db: AsyncSession) -> Game:
    """Get current game or create a new one if none exists."""
    result = await db.execute(
        select(Game).where(Game.status != GameStatus.FINISHED).order_by(Game.id.desc())
    )
    game = result.scalar_one_or_none()
    return game


async def create_game(db: AsyncSession, req: GameCreateRequest) -> Game:
    """Create a new game. Only one active game allowed."""
    # Check for existing active game
    result = await db.execute(
        select(Game).where(Game.status != GameStatus.FINISHED)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail=f"游戏 '{existing.name}' 仍在进行中，请先结束它")

    game = Game(
        name=req.name,
        cat_ratio=req.cat_ratio,
        cat_count=req.cat_count,
        cat_team_count=req.cat_team_count,
        mouse_team_count=req.mouse_team_count,
        capture_score=req.capture_score,
        allow_repeat_capture=req.allow_repeat_capture,
        survival_interval_seconds=req.survival_interval_seconds,
        survival_interval_score=req.survival_interval_score,
        allow_revive=req.allow_revive,
        max_revive_count=req.max_revive_count,
        revive_protect_seconds=req.revive_protect_seconds,
    )
    db.add(game)
    await db.flush()
    return game


async def get_game_overview(db: AsyncSession, game: Game) -> GameOverviewResponse:
    """Get game overview with statistics."""
    from app.models.capture import CaptureRecord

    # Count players
    total = await db.execute(
        select(sql_func.count()).select_from(GamePlayer).where(GamePlayer.game_id == game.id)
    )
    online = await db.execute(
        select(sql_func.count()).select_from(GamePlayer).where(
            GamePlayer.game_id == game.id, GamePlayer.is_online == True
        )
    )
    cats = await db.execute(
        select(sql_func.count()).select_from(GamePlayer).where(
            GamePlayer.game_id == game.id, GamePlayer.role == PlayerRole.CAT
        )
    )
    mice = await db.execute(
        select(sql_func.count()).select_from(GamePlayer).where(
            GamePlayer.game_id == game.id, GamePlayer.role == PlayerRole.MOUSE
        )
    )
    alive_mice = await db.execute(
        select(sql_func.count()).select_from(GamePlayer).where(
            GamePlayer.game_id == game.id,
            GamePlayer.role == PlayerRole.MOUSE,
            GamePlayer.status == GamePlayerStatus.ALIVE
        )
    )
    dead_mice = await db.execute(
        select(sql_func.count()).select_from(GamePlayer).where(
            GamePlayer.game_id == game.id,
            GamePlayer.role == PlayerRole.MOUSE,
            GamePlayer.status == GamePlayerStatus.DEAD
        )
    )
    pre_assigned = await db.execute(
        select(sql_func.count()).select_from(GamePlayer).where(
            GamePlayer.game_id == game.id,
            GamePlayer.pre_assigned_cat == True
        )
    )

    # Count total captures (累计抓捕次数)
    total_captures = await db.execute(
        select(sql_func.count()).select_from(CaptureRecord).where(
            CaptureRecord.game_id == game.id
        )
    )

    # Count total revives (已复活次数)
    total_revives = await db.execute(
        select(sql_func.count()).select_from(GamePlayer).where(
            GamePlayer.game_id == game.id,
            GamePlayer.role == PlayerRole.MOUSE,
            GamePlayer.revive_count > 0
        )
    )

    # Get scalar values once
    total_count = total.scalar() or 0
    online_count = online.scalar() or 0
    cats_count = cats.scalar() or 0
    mice_count = mice.scalar() or 0
    alive_mice_count = alive_mice.scalar() or 0
    dead_mice_count = dead_mice.scalar() or 0
    pre_assigned_count = pre_assigned.scalar() or 0
    total_captures_count = total_captures.scalar() or 0
    total_revives_count = total_revives.scalar() or 0

    return GameOverviewResponse(
        game=GameResponse.model_validate(game),
        statistics={
            "total": total_count,
            "online": online_count,
            "offline": total_count - online_count,
            "cats": cats_count,
            "mice": mice_count,
            "alive_mice": alive_mice_count,
            "dead_mice": dead_mice_count,
            "pre_assigned_cats": pre_assigned_count,
            "total_captures": total_captures_count,
            "total_revives": total_revives_count,
        }
    )


async def start_game(db: AsyncSession, game: Game) -> Game:
    """Start the game - begins survival timing for mice."""
    if game.status not in [GameStatus.TEAM_ASSIGNED, GameStatus.ROLE_ASSIGNED]:
        raise HTTPException(status_code=400, detail="游戏状态不允许开始，请先完成身份分配和分队")

    game.status = GameStatus.RUNNING
    game.started_at = datetime.now(timezone.utc)

    # Start survival records for all alive mice
    from app.models.survival import SurvivalRecord
    result = await db.execute(
        select(GamePlayer).where(
            GamePlayer.game_id == game.id,
            GamePlayer.role == PlayerRole.MOUSE,
            GamePlayer.status == GamePlayerStatus.ALIVE
        )
    )
    mice = result.scalars().all()
    for mouse in mice:
        mouse.survival_round = 1
        record = SurvivalRecord(
            game_player_id=mouse.id,
            survival_round=1,
            started_at=game.started_at
        )
        db.add(record)

    return game


async def finish_game(db: AsyncSession, game: Game) -> Game:
    """Finish the game - settle all scores."""
    if game.status not in [GameStatus.RUNNING, GameStatus.PAUSED]:
        raise HTTPException(status_code=400, detail="只有进行中或暂停的游戏才能结束")

    game.status = GameStatus.FINISHING
    await db.flush()

    now = datetime.now(timezone.utc)
    game.finished_at = now

    # End all active survival records
    from app.models.survival import SurvivalRecord
    result = await db.execute(
        select(SurvivalRecord).where(SurvivalRecord.ended_at.is_(None))
    )
    active_records = result.scalars().all()
    for record in active_records:
        record.ended_at = now
        # Handle timezone-naive datetimes from SQLite
        started = record.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        record.duration_seconds = (now - started).total_seconds()

    # Calculate survival scores for all mice
    from app.services.score_service import settle_survival_scores
    await settle_survival_scores(db, game)

    # Settle mini-game rewards
    from app.services.score_service import settle_minigame_rewards
    await settle_minigame_rewards(db, game)

    game.status = GameStatus.FINISHED
    return game
