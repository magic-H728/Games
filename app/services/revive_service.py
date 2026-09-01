from typing import Optional, List
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.models.game import Game, GameStatus
from app.models.player import GamePlayer, PlayerRole, GamePlayerStatus
from app.models.survival import SurvivalRecord
from app.models.mini_game import MiniGame, MiniGameAttempt
from app.schemas.revive import ReviveResponse


async def start_revive(
    db: AsyncSession,
    game: Game,
    mouse_qr_token: str,
    mini_game_id: Optional[int] = None
) -> dict:
    """Staff initiates revival for a dead mouse."""
    if not game.allow_revive:
        raise HTTPException(status_code=400, detail="当前游戏不允许复活")

    if game.status != GameStatus.RUNNING:
        raise HTTPException(status_code=400, detail="游戏未在进行中")

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
        raise HTTPException(status_code=400, detail="只有老鼠才能复活")

    if mouse.status != GamePlayerStatus.DEAD:
        raise HTTPException(status_code=400, detail="该老鼠未死亡")

    if mouse.revive_count >= game.max_revive_count:
        raise HTTPException(status_code=400, detail=f"已达到最大复活次数({game.max_revive_count})")

    # Get available mini-games
    result = await db.execute(
        select(MiniGame).where(
            MiniGame.game_id == game.id,
            MiniGame.is_active == True
        )
    )
    mini_games = result.scalars().all()

    if not mini_games:
        raise HTTPException(status_code=400, detail="没有可用的复活小游戏")

    # If mini_game_id specified, use it; otherwise use first available
    if mini_game_id:
        result = await db.execute(
            select(MiniGame).where(MiniGame.id == mini_game_id, MiniGame.game_id == game.id)
        )
        mini_game = result.scalar_one_or_none()
        if mini_game is None:
            raise HTTPException(status_code=404, detail="指定的小游戏不存在")
    else:
        mini_game = mini_games[0]

    # Create a mini-game attempt (pending)
    attempt = MiniGameAttempt(
        mini_game_id=mini_game.id,
        game_player_id=mouse.id,
        score=0,
        passed=False,
        rewarded=False
    )
    db.add(attempt)
    await db.flush()

    return {
        "mouse": mouse,
        "mini_game": mini_game,
        "attempt": attempt,
        "available_mini_games": mini_games
    }


async def complete_revive(
    db: AsyncSession,
    game: Game,
    attempt_id: int,
    score: int,
    passed: bool
) -> ReviveResponse:
    """Staff completes the revival after mini-game."""
    if game.status != GameStatus.RUNNING:
        raise HTTPException(status_code=400, detail="游戏未在进行中")

    # Find the attempt
    result = await db.execute(
        select(MiniGameAttempt).where(MiniGameAttempt.id == attempt_id)
    )
    attempt = result.scalar_one_or_none()

    if attempt is None:
        raise HTTPException(status_code=404, detail="未找到该挑战记录")

    # Get the mouse with player eagerly loaded
    result = await db.execute(
        select(GamePlayer)
        .options(selectinload(GamePlayer.player))
        .where(GamePlayer.id == attempt.game_player_id)
    )
    mouse = result.scalar_one_or_none()

    if mouse is None:
        raise HTTPException(status_code=404, detail="未找到该玩家")

    if mouse.status != GamePlayerStatus.DEAD:
        raise HTTPException(status_code=400, detail="该玩家未死亡")

    # Update attempt
    attempt.score = score
    attempt.passed = passed

    if not passed:
        return ReviveResponse(
            success=False,
            message="小游戏未通过，无法复活",
            player_name=mouse.player.name if mouse.player else None,
            attempt_id=attempt.id
        )

    # Revive the mouse
    now = datetime.now(timezone.utc)
    mouse.status = GamePlayerStatus.ALIVE
    mouse.revive_count += 1
    mouse.survival_round += 1
    mouse.died_at = None
    mouse.protect_until = now + timedelta(seconds=game.revive_protect_seconds)

    # Start new survival record
    survival = SurvivalRecord(
        game_player_id=mouse.id,
        survival_round=mouse.survival_round,
        started_at=now
    )
    db.add(survival)

    # Handle mini-game scoring - automatically settle top 3 rewards
    mini_game_result = await db.execute(
        select(MiniGame).where(MiniGame.id == attempt.mini_game_id)
    )
    mini_game = mini_game_result.scalar_one_or_none()

    reward_message = ""
    if mini_game and mini_game.is_scored and score > 0:
        # Check if this player is in top 3
        from app.models.score import ScoreTransaction, ScoreType

        # Get current top 3 (excluding this attempt)
        top_attempts_result = await db.execute(
            select(MiniGameAttempt)
            .where(
                MiniGameAttempt.mini_game_id == mini_game.id,
                MiniGameAttempt.passed == True,
                MiniGameAttempt.rewarded == True
            )
            .order_by(MiniGameAttempt.score.desc(), MiniGameAttempt.completed_at.asc())
            .limit(3)
        )
        top_attempts = top_attempts_result.scalars().all()

        # Determine if this score qualifies for a reward
        rewards = [mini_game.reward_first, mini_game.reward_second, mini_game.reward_third]
        rank = None
        reward = 0

        if len(top_attempts) < 3:
            # Less than 3 rewarded, this player qualifies
            rank = len(top_attempts) + 1
            reward = rewards[rank - 1] if rank <= len(rewards) else 0
        elif score > top_attempts[-1].score or (score == top_attempts[-1].score):
            # This score beats or ties the 3rd place
            # Find the exact rank
            for i, ta in enumerate(top_attempts):
                if score > ta.score:
                    rank = i + 1
                    reward = rewards[rank - 1] if rank <= len(rewards) else 0
                    break
                elif score == ta.score:
                    # Same score, earlier time wins (but this player just completed)
                    rank = i + 1
                    reward = rewards[rank - 1] if rank <= len(rewards) else 0
                    break

        if rank and reward > 0:
            attempt.rewarded = True
            score_tx = ScoreTransaction(
                game_id=game.id,
                game_player_id=mouse.id,
                score=reward,
                type=ScoreType.MINIGAME,
                reason=f"小游戏 '{mini_game.name}' 第{rank}名奖励",
                related_attempt_id=attempt.id
            )
            db.add(score_tx)
            medal = ["🥇", "🥈", "🥉"][rank - 1] if rank <= 3 else ""
            reward_message = f" {medal}第{rank}名，获得 {reward} 积分奖励！"

    return ReviveResponse(
        success=True,
        message=f"复活成功！保护时间 {game.revive_protect_seconds} 秒{reward_message}",
        player_name=mouse.player.name if mouse.player else None,
        attempt_id=attempt.id
    )
