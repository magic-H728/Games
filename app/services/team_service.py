from typing import Optional
import random
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.models.game import Game, GameStatus
from app.models.player import GamePlayer, PlayerRole
from app.models.team import Team, TeamRole


async def create_teams(db: AsyncSession, game: Game) -> dict:
    """Create teams and assign players."""
    if game.status != GameStatus.ROLE_ASSIGNED:
        raise HTTPException(status_code=400, detail="请先完成身份分配")

    # Get cats and mice
    result = await db.execute(
        select(GamePlayer).where(
            GamePlayer.game_id == game.id,
            GamePlayer.role == PlayerRole.CAT
        )
    )
    cats = list(result.scalars().all())

    result = await db.execute(
        select(GamePlayer).where(
            GamePlayer.game_id == game.id,
            GamePlayer.role == PlayerRole.MOUSE
        )
    )
    mice = list(result.scalars().all())

    # Delete existing teams for this game
    result = await db.execute(select(Team).where(Team.game_id == game.id))
    existing_teams = result.scalars().all()
    for t in existing_teams:
        await db.delete(t)
    await db.flush()

    # Shuffle for random assignment
    random.shuffle(cats)
    random.shuffle(mice)

    # Create cat teams
    cat_team_count = game.cat_team_count
    if cat_team_count < 1:
        cat_team_count = 1

    cat_teams = []
    for i in range(cat_team_count):
        team = Team(
            game_id=game.id,
            name=f"猫队{i+1:02d}",
            role=TeamRole.CAT,
            team_number=i + 1
        )
        db.add(team)
        cat_teams.append(team)

    await db.flush()

    # Assign cats to teams (round-robin)
    for idx, cat in enumerate(cats):
        team = cat_teams[idx % len(cat_teams)]
        cat.team_id = team.id

    # Create mouse teams
    mouse_team_count = game.mouse_team_count
    if mouse_team_count < 1:
        mouse_team_count = 1

    mouse_teams = []
    for i in range(mouse_team_count):
        team = Team(
            game_id=game.id,
            name=f"鼠队{i+1:02d}",
            role=TeamRole.MOUSE,
            team_number=i + 1
        )
        db.add(team)
        mouse_teams.append(team)

    await db.flush()

    # Assign mice to teams (round-robin)
    for idx, mouse in enumerate(mice):
        team = mouse_teams[idx % len(mouse_teams)]
        mouse.team_id = team.id

    game.status = GameStatus.TEAM_ASSIGNED

    return {
        "cat_teams": len(cat_teams),
        "mouse_teams": len(mouse_teams),
        "cats_per_team": len(cats) // max(1, len(cat_teams)),
        "mice_per_team": len(mice) // max(1, len(mouse_teams)),
    }


async def get_player_team(db: AsyncSession, game_player: GamePlayer) -> Optional[dict]:
    """Get team info for a player."""
    if game_player.team_id is None:
        return None

    result = await db.execute(select(Team).where(Team.id == game_player.team_id))
    team = result.scalar_one_or_none()
    if team is None:
        return None

    # Get all team members
    result = await db.execute(
        select(GamePlayer).where(GamePlayer.team_id == team.id)
    )
    members = result.scalars().all()

    return {
        "team": team,
        "members": members
    }
