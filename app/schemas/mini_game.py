from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime


class MiniGameCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    game_type: str = "OTHER"
    is_scored: bool = False
    pass_score: int = 60
    reward_first: int = 30
    reward_second: int = 20
    reward_third: int = 10


class MiniGameUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    game_type: Optional[str] = None
    is_scored: Optional[bool] = None
    pass_score: Optional[int] = None
    reward_first: Optional[int] = None
    reward_second: Optional[int] = None
    reward_third: Optional[int] = None
    is_active: Optional[bool] = None


class MiniGameResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    game_type: str
    is_scored: bool
    pass_score: int
    reward_first: int
    reward_second: int
    reward_third: int
    is_active: bool

    class Config:
        from_attributes = True


class MiniGameAttemptResponse(BaseModel):
    id: int
    mini_game_id: int
    mini_game_name: Optional[str] = None
    game_player_id: int
    player_name: Optional[str] = None
    score: int
    passed: bool
    rewarded: bool
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class MiniGameRankingEntry(BaseModel):
    rank: int
    player_name: str
    team_name: Optional[str]
    score: int
    completed_at: datetime
    rewarded: bool
