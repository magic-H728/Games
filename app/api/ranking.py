from typing import Optional, List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import require_player, require_staff
from app.models.player import GamePlayer
from app.services import game_service, ranking_service

router = APIRouter(prefix="/api/rankings", tags=["排行榜"])


@router.get("/players")
async def get_player_rankings(
    role: Optional[str] = None,
    payload: dict = Depends(require_player),
    db: AsyncSession = Depends(get_db)
):
    """获取个人排行榜"""
    game = await game_service.get_current_game(db)
    rankings = await ranking_service.get_player_rankings(db, game, role)

    # Get caller's rank
    game_player_id = payload.get("game_player_id")
    my_info = await ranking_service.get_player_rank(db, game, game_player_id)

    return {
        "players": rankings[:50],  # Top 50
        "my_rank": my_info["rank"],
        "my_score": my_info["total_score"]
    }


@router.get("/teams")
async def get_team_rankings(
    role: Optional[str] = None,
    payload: dict = Depends(require_player),
    db: AsyncSession = Depends(get_db)
):
    """获取团队排行榜"""
    game = await game_service.get_current_game(db)
    rankings = await ranking_service.get_team_rankings(db, game, role)

    # Get caller's team rank
    game_player_id = payload.get("game_player_id")
    from sqlalchemy import select
    result = await db.select(GamePlayer).where(GamePlayer.id == game_player_id) if False else await db.execute(select(GamePlayer).where(GamePlayer.id == game_player_id))
    gp = result.scalar_one_or_none()

    my_team_rank = None
    my_team_score = 0
    if gp and gp.team_id:
        for r in rankings:
            if r["team_id"] == gp.team_id:
                my_team_rank = r["rank"]
                my_team_score = r["total_score"]
                break

    return {
        "teams": rankings[:50],
        "my_team_rank": my_team_rank,
        "my_team_score": my_team_score
    }


@router.get("/staff/players")
async def staff_get_player_rankings(
    role: Optional[str] = None,
    payload: dict = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    """工作人员获取个人排行榜（完整数据）"""
    game = await game_service.get_current_game(db)
    rankings = await ranking_service.get_player_rankings(db, game, role)
    return {"players": rankings}


@router.get("/staff/teams")
async def staff_get_team_rankings(
    role: Optional[str] = None,
    payload: dict = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    """工作人员获取团队排行榜（完整数据）"""
    game = await game_service.get_current_game(db)
    rankings = await ranking_service.get_team_rankings(db, game, role)
    return {"teams": rankings}
