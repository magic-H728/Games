from typing import Optional, List
from sqlalchemy import select, func as sql_func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.game import Game
from app.models.player import GamePlayer, PlayerRole
from app.models.team import Team
from app.models.score import ScoreTransaction, ScoreType


async def get_player_rankings(
    db: AsyncSession,
    game: Game,
    role_filter: Optional[str] = None
) -> List[dict]:
    """Get player rankings sorted by total score."""
    # Build query for total scores per player
    query = (
        select(
            GamePlayer.id.label("game_player_id"),
            GamePlayer.role,
            sql_func.coalesce(sql_func.sum(ScoreTransaction.score), 0).label("total_score")
        )
        .outerjoin(ScoreTransaction, ScoreTransaction.game_player_id == GamePlayer.id)
        .where(GamePlayer.game_id == game.id)
        .group_by(GamePlayer.id)
    )

    if role_filter:
        query = query.where(GamePlayer.role == role_filter)

    query = query.order_by(sql_func.coalesce(sql_func.sum(ScoreTransaction.score), 0).desc())

    result = await db.execute(query)
    rows = result.all()

    # Get player details
    rankings = []
    for rank, row in enumerate(rows, 1):
        gp_result = await db.execute(
            select(GamePlayer).where(GamePlayer.id == row.game_player_id)
        )
        gp = gp_result.scalar_one_or_none()
        if gp is None:
            continue

        # Get team name
        team_name = None
        if gp.team_id:
            team_result = await db.execute(select(Team).where(Team.id == gp.team_id))
            team = team_result.scalar_one_or_none()
            if team:
                team_name = team.name

        # Get score breakdown
        breakdown = await _get_score_breakdown(db, gp.id)

        # Need to get player name
        from app.models.player import Player
        player_result = await db.execute(select(Player).where(Player.id == gp.player_id))
        player = player_result.scalar_one_or_none()

        rankings.append({
            "rank": rank,
            "game_player_id": gp.id,
            "name": player.name if player else "未知",
            "team_name": team_name,
            "role": gp.role,
            "total_score": row.total_score,
            "capture_score": breakdown.get("CAPTURE", 0),
            "minigame_score": breakdown.get("MINIGAME", 0),
            "survival_score": breakdown.get("SURVIVAL", 0),
        })

    return rankings


async def get_team_rankings(
    db: AsyncSession,
    game: Game,
    role_filter: Optional[str] = None
) -> List[dict]:
    """Get team rankings sorted by total score."""
    query = select(Team).where(Team.game_id == game.id)
    if role_filter:
        query = query.where(Team.role == role_filter)

    result = await db.execute(query)
    teams = result.scalars().all()

    team_scores = []
    for team in teams:
        # Sum scores of all team members
        score_result = await db.execute(
            select(sql_func.coalesce(sql_func.sum(ScoreTransaction.score), 0))
            .join(GamePlayer, GamePlayer.id == ScoreTransaction.game_player_id)
            .where(GamePlayer.team_id == team.id)
        )
        total_score = score_result.scalar() or 0

        # Count members
        member_result = await db.execute(
            select(sql_func.count()).select_from(GamePlayer).where(GamePlayer.team_id == team.id)
        )
        member_count = member_result.scalar() or 0

        team_scores.append({
            "team_id": team.id,
            "team_name": team.name,
            "role": team.role,
            "member_count": member_count,
            "total_score": total_score
        })

    # Sort by score descending
    team_scores.sort(key=lambda x: x["total_score"], reverse=True)

    # Add rank
    for rank, item in enumerate(team_scores, 1):
        item["rank"] = rank

    return team_scores


async def get_player_rank(db: AsyncSession, game: Game, game_player_id: int) -> dict:
    """Get a specific player's rank and score."""
    rankings = await get_player_rankings(db, game)
    for r in rankings:
        if r["game_player_id"] == game_player_id:
            return {"rank": r["rank"], "total_score": r["total_score"]}

    return {"rank": None, "total_score": 0}


async def _get_score_breakdown(db: AsyncSession, game_player_id: int) -> dict:
    result = await db.execute(
        select(
            ScoreTransaction.type,
            sql_func.coalesce(sql_func.sum(ScoreTransaction.score), 0)
        ).where(
            ScoreTransaction.game_player_id == game_player_id
        ).group_by(ScoreTransaction.type)
    )
    rows = result.all()
    return {type_: score for type_, score in rows}
