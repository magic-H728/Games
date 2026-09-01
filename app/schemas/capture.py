from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime


class CaptureRequest(BaseModel):
    qr_token: str


class CaptureResponse(BaseModel):
    success: bool
    message: str
    cat_name: Optional[str] = None
    mouse_name: Optional[str] = None
    score_awarded: int = 0
    captured_at: Optional[datetime] = None
