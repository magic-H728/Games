from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime


class ReviveStartRequest(BaseModel):
    qr_token: str
    mini_game_id: Optional[int] = None  # staff selects which mini-game


class ReviveCompleteRequest(BaseModel):
    attempt_id: int
    score: int
    passed: bool


class ReviveResponse(BaseModel):
    success: bool
    message: str
    player_name: Optional[str] = None
    attempt_id: Optional[int] = None
