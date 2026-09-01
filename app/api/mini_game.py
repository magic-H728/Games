from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import require_staff, require_player
from app.models.mini_game import MiniGame, MiniGameAttempt
from app.models.player import GamePlayer, Player
from app.models.team import Team
from app.schemas.mini_game import (
    MiniGameCreateRequest, MiniGameUpdateRequest,
    MiniGameResponse, MiniGameAttemptResponse, MiniGameRankingEntry
)
from app.services import game_service

router = APIRouter(prefix="/api/mini-games", tags=["小游戏"])


@router.get("/", response_model=List[MiniGameResponse])
async def list_mini_games(
    payload: dict = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    """获取所有小游戏"""
    game = await game_service.get_current_game(db)
    result = await db.execute(
        select(MiniGame).where(MiniGame.game_id == game.id)
    )
    games = result.scalars().all()
    return [MiniGameResponse.model_validate(mg) for mg in games]


@router.post("/", response_model=MiniGameResponse)
async def create_mini_game(
    req: MiniGameCreateRequest,
    payload: dict = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    """创建小游戏"""
    game = await game_service.get_current_game(db)
    mg = MiniGame(
        game_id=game.id,
        name=req.name,
        description=req.description,
        game_type=req.game_type,
        is_scored=req.is_scored,
        pass_score=req.pass_score,
        reward_first=req.reward_first,
        reward_second=req.reward_second,
        reward_third=req.reward_third
    )
    db.add(mg)
    await db.flush()
    return MiniGameResponse.model_validate(mg)


@router.put("/{mini_game_id}", response_model=MiniGameResponse)
async def update_mini_game(
    mini_game_id: int,
    req: MiniGameUpdateRequest,
    payload: dict = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    """更新小游戏设置"""
    result = await db.execute(select(MiniGame).where(MiniGame.id == mini_game_id))
    mg = result.scalar_one_or_none()
    if mg is None:
        raise HTTPException(status_code=404, detail="未找到该小游戏")

    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(mg, field, value)

    return MiniGameResponse.model_validate(mg)


@router.get("/{mini_game_id}/ranking", response_model=List[MiniGameRankingEntry])
async def get_mini_game_ranking(
    mini_game_id: int,
    payload: dict = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    """获取小游戏排行榜"""
    result = await db.execute(
        select(MiniGameAttempt).where(
            MiniGameAttempt.mini_game_id == mini_game_id,
            MiniGameAttempt.passed == True
        ).order_by(
            MiniGameAttempt.score.desc(),
            MiniGameAttempt.completed_at.asc()
        ).limit(10)
    )
    attempts = result.scalars().all()

    entries = []
    for rank, attempt in enumerate(attempts, 1):
        gp_result = await db.execute(select(GamePlayer).where(GamePlayer.id == attempt.game_player_id))
        gp = gp_result.scalar_one_or_none()

        player_result = await db.execute(select(Player).where(Player.id == gp.player_id)) if gp else None
        player = player_result.scalar_one_or_none() if player_result else None

        team_name = None
        if gp and gp.team_id:
            team_result = await db.execute(select(Team).where(Team.id == gp.team_id))
            team = team_result.scalar_one_or_none()
            if team:
                team_name = team.name

        entries.append(MiniGameRankingEntry(
            rank=rank,
            player_name=player.name if player else "未知",
            team_name=team_name,
            score=attempt.score,
            completed_at=attempt.completed_at,
            rewarded=attempt.rewarded
        ))

    return entries


@router.post("/{mini_game_id}/settle-rewards")
async def settle_mini_game_rewards(
    mini_game_id: int,
    payload: dict = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    """结算小游戏前三名奖励"""
    result = await db.execute(select(MiniGame).where(MiniGame.id == mini_game_id))
    mg = result.scalar_one_or_none()
    if mg is None:
        raise HTTPException(status_code=404, detail="未找到该小游戏")

    if not mg.is_scored:
        raise HTTPException(status_code=400, detail="该小游戏不计分，无需结算奖励")

    game = await game_service.get_current_game(db)

    # Get top 3 unrewarded attempts
    result = await db.execute(
        select(MiniGameAttempt).where(
            MiniGameAttempt.mini_game_id == mini_game_id,
            MiniGameAttempt.passed == True,
            MiniGameAttempt.rewarded == False
        ).order_by(
            MiniGameAttempt.score.desc(),
            MiniGameAttempt.completed_at.asc()
        ).limit(3)
    )
    top_attempts = result.scalars().all()

    rewards = [mg.reward_first, mg.reward_second, mg.reward_third]
    awarded = []

    from app.models.score import ScoreTransaction, ScoreType

    for rank, attempt in enumerate(top_attempts):
        reward = rewards[rank] if rank < len(rewards) else 0
        if reward > 0:
            attempt.rewarded = True
            tx = ScoreTransaction(
                game_id=game.id,
                game_player_id=attempt.game_player_id,
                score=reward,
                type=ScoreType.MINIGAME,
                reason=f"小游戏 '{mg.name}' 第{rank+1}名奖励",
                related_attempt_id=attempt.id
            )
            db.add(tx)

            # Get player name
            gp_result = await db.execute(select(GamePlayer).where(GamePlayer.id == attempt.game_player_id))
            gp = gp_result.scalar_one_or_none()
            player_result = await db.execute(select(Player).where(Player.id == gp.player_id)) if gp else None
            player = player_result.scalar_one_or_none() if player_result else None

            awarded.append({
                "rank": rank + 1,
                "player_name": player.name if player else "未知",
                "score": attempt.score,
                "reward": reward
            })

    return {"success": True, "awarded": awarded}
