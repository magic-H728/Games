from typing import Optional
from sqlalchemy import select, func as sql_func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.game import Game
from app.models.player import GamePlayer, PlayerRole
from app.models.survival import SurvivalRecord
from app.models.mini_game import MiniGame, MiniGameAttempt
from app.models.score import ScoreTransaction, ScoreType


async def get_player_total_score(db: AsyncSession, game_player_id: int) -> int:
    """Get total score for a player."""
    result = await db.execute(
        select(sql_func.coalesce(sql_func.sum(ScoreTransaction.score), 0)).where(
            ScoreTransaction.game_player_id == game_player_id
        )
    )
    return result.scalar() or 0


async def get_player_score_breakdown(db: AsyncSession, game_player_id: int) -> dict:
    """Get score breakdown by type."""
    result = await db.execute(
        select(
            ScoreTransaction.type,
            sql_func.coalesce(sql_func.sum(ScoreTransaction.score), 0)
        ).where(
            ScoreTransaction.game_player_id == game_player_id
        ).group_by(ScoreTransaction.type)
    )
    rows = result.all()

    breakdown = {"CAPTURE": 0, "MINIGAME": 0, "SURVIVAL": 0, "MANUAL": 0}
    for type_, score in rows:
        breakdown[type_] = score

    breakdown["total"] = sum(breakdown.values())
    return breakdown


async def get_team_total_score(db: AsyncSession, team_id: int) -> int:
    """Get total score for a team (sum of all members)."""
    result = await db.execute(
        select(sql_func.coalesce(sql_func.sum(ScoreTransaction.score), 0))
        .join(GamePlayer, GamePlayer.id == ScoreTransaction.game_player_id)
        .where(GamePlayer.team_id == team_id)
    )
    return result.scalar() or 0


async def settle_survival_scores(db: AsyncSession, game: Game):
    """Calculate and award survival scores at game end."""
    # Get all mice with their total survival time
    result = await db.execute(
        select(GamePlayer).where(
            GamePlayer.game_id == game.id,
            GamePlayer.role == PlayerRole.MOUSE
        )
    )
    mice = result.scalars().all()

    interval = game.survival_interval_seconds
    score_per_interval = game.survival_interval_score

    if interval <= 0:
        return

    for mouse in mice:
        # Get all survival records for this mouse
        result = await db.execute(
            select(SurvivalRecord).where(SurvivalRecord.game_player_id == mouse.id)
        )
        records = result.scalars().all()

        total_seconds = sum(r.duration_seconds for r in records)
        mouse.total_survival_seconds = total_seconds

        # Calculate survival score
        intervals = int(total_seconds // interval)
        survival_score = intervals * score_per_interval

        if survival_score > 0:
            total_minutes = int(total_seconds // 60)
            tx = ScoreTransaction(
                game_id=game.id,
                game_player_id=mouse.id,
                score=survival_score,
                type=ScoreType.SURVIVAL,
                reason=f"累计生存 {total_minutes} 分钟"
            )
            db.add(tx)


async def settle_minigame_rewards(db: AsyncSession, game: Game):
    """Settle top-3 rewards for scored mini-games."""
    result = await db.execute(
        select(MiniGame).where(
            MiniGame.game_id == game.id,
            MiniGame.is_scored == True,
            MiniGame.is_active == True
        )
    )
    mini_games = result.scalars().all()

    for mg in mini_games:
        # Get top 3 attempts (highest score, earliest time for ties)
        result = await db.execute(
            select(MiniGameAttempt).where(
                MiniGameAttempt.mini_game_id == mg.id,
                MiniGameAttempt.passed == True,
                MiniGameAttempt.rewarded == False
            ).order_by(
                MiniGameAttempt.score.desc(),
                MiniGameAttempt.completed_at.asc()
            ).limit(3)
        )
        top_attempts = result.scalars().all()

        rewards = [mg.reward_first, mg.reward_second, mg.reward_third]

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
