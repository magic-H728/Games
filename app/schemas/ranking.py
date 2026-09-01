from typing import Optional, List
from pydantic import BaseModel


class PlayerRankingEntry(BaseModel):
    rank: int
    game_player_id: int
    name: str
    team_name: Optional[str]
    role: Optional[str]
    total_score: int
    capture_score: int = 0
    minigame_score: int = 0
    survival_score: int = 0


class TeamRankingEntry(BaseModel):
    rank: int
    team_id: int
    team_name: str
    role: str
    member_count: int
    total_score: int


class RankingResponse(BaseModel):
    players: List[PlayerRankingEntry]
    teams: List[TeamRankingEntry]
    my_rank: Optional[int] = None
    my_score: int = 0
