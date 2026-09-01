from typing import Optional
import random
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.models.game import Game, GameStatus
from app.models.player import GamePlayer, PlayerRole, GamePlayerStatus


async def pre_assign_cat(db: AsyncSession, game: Game, game_player: GamePlayer) -> GamePlayer:
    """Staff marks a player as cat before role assignment."""
    if game.status not in [GameStatus.PENDING, GameStatus.READY]:
        raise HTTPException(status_code=400, detail="只能在游戏等待阶段指定猫")

    if game_player.role is not None:
        raise HTTPException(status_code=400, detail="该玩家已分配角色")

    game_player.pre_assigned_cat = True
    return game_player


async def cancel_pre_assign_cat(db: AsyncSession, game: Game, game_player: GamePlayer) -> GamePlayer:
    """Cancel pre-assignment."""
    if game.status not in [GameStatus.PENDING, GameStatus.READY]:
        raise HTTPException(status_code=400, detail="只能在游戏等待阶段取消指定")

    game_player.pre_assigned_cat = False
    return game_player


async def assign_roles(db: AsyncSession, game: Game) -> dict:
    """Assign cat/mouse roles to all players."""
    if game.status not in [GameStatus.PENDING, GameStatus.READY]:
        raise HTTPException(status_code=400, detail="游戏状态不允许分配身份")

    # Get all players
    result = await db.execute(
        select(GamePlayer).where(GamePlayer.game_id == game.id)
    )
    all_players = result.scalars().all()

    if not all_players:
        raise HTTPException(status_code=400, detail="没有玩家参与")

    total = len(all_players)

    # Calculate target cat count
    if game.cat_count > 0:
        target_cats = game.cat_count
    else:
        target_cats = max(1, round(total * game.cat_ratio))

    # Get pre-assigned cats
    pre_assigned = [p for p in all_players if p.pre_assigned_cat]
    pre_assigned_count = len(pre_assigned)

    if pre_assigned_count > target_cats:
        raise HTTPException(
            status_code=400,
            detail=f"主动指定猫人数({pre_assigned_count})已超过目标猫数量({target_cats})，请调整设置"
        )

    # Need to randomly select remaining cats
    remaining_needed = target_cats - pre_assigned_count
    unassigned = [p for p in all_players if not p.pre_assigned_cat]

    if remaining_needed > len(unassigned):
        remaining_needed = len(unassigned)

    random_cats = random.sample(unassigned, remaining_needed)

    now = datetime.now(timezone.utc)

    # Assign roles
    for player in all_players:
        if player in pre_assigned or player in random_cats:
            player.role = PlayerRole.CAT
            player.status = GamePlayerStatus.ALIVE
        else:
            player.role = PlayerRole.MOUSE
            player.status = GamePlayerStatus.ALIVE
        player.role_assigned_at = now

    game.status = GameStatus.ROLE_ASSIGNED

    return {
        "total": total,
        "cats": target_cats,
        "mice": total - target_cats,
        "pre_assigned": pre_assigned_count,
        "random_selected": remaining_needed
    }
