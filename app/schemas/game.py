from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime


class GameCreateRequest(BaseModel):
    name: str
    cat_ratio: float = 0.1
    cat_count: int = 0  # 0 = auto
    cat_team_count: int = 5
    mouse_team_count: int = 10
    capture_score: int = 10
    allow_repeat_capture: bool = False
    survival_interval_seconds: int = 300
    survival_interval_score: int = 5
    allow_revive: bool = True
    max_revive_count: int = 3
    revive_protect_seconds: int = 120


class GameResponse(BaseModel):
    id: int
    name: str
    status: str
    cat_ratio: float
    cat_count: int
    capture_score: int
    survival_interval_seconds: int
    survival_interval_score: int
    allow_revive: bool
    max_revive_count: int
    revive_protect_seconds: int
    created_at: Optional[datetime]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]

    class Config:
        from_attributes = True


class GameOverviewResponse(BaseModel):
    game: GameResponse
    statistics: dict
