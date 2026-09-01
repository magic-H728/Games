from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime


class PlayerResponse(BaseModel):
    id: int
    name: str
    student_id: str
    wechat_id: Optional[str]

    class Config:
        from_attributes = True


class GamePlayerResponse(BaseModel):
    id: int
    game_id: int
    player_id: int
    qr_token: str
    role: Optional[str]
    status: str
    is_online: bool
    team_id: Optional[int]
    team_name: Optional[str] = None
    survival_round: int
    total_survival_seconds: float
    revive_count: int
    protect_until: Optional[datetime]
    joined_at: Optional[datetime]
    died_at: Optional[datetime]
    player_name: Optional[str] = None
    student_id: Optional[str] = None
    wechat_id: Optional[str] = None
    total_score: int = 0

    class Config:
        from_attributes = True


class PlayerProfileUpdate(BaseModel):
    wechat_id: Optional[str] = None


class PlayerInfoBrief(BaseModel):
    """Brief info visible to other players."""
    id: int
    name: str
    student_id_masked: str  # e.g. "2026****123"
    wechat_id_masked: Optional[str]  # e.g. "h***23"
    role: Optional[str]
    team_name: Optional[str]
    status: str
