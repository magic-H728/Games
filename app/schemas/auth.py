from typing import Optional, List
from pydantic import BaseModel


class PlayerLoginRequest(BaseModel):
    name: str
    student_id: str


class StaffLoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str  # "PLAYER" or "STAFF"
    player_id: Optional[int] = None
    game_player_id: Optional[int] = None
