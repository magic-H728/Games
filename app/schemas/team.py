from typing import Optional, List
from pydantic import BaseModel


class TeamResponse(BaseModel):
    id: int
    name: str
    role: str
    team_number: int
    member_count: int = 0
    total_score: int = 0

    class Config:
        from_attributes = True


class TeamMemberResponse(BaseModel):
    id: int
    name: str
    student_id: str
    wechat_id: Optional[str]
    role: Optional[str]
    status: str
    total_score: int = 0


class TeamDetailResponse(BaseModel):
    id: int
    name: str
    role: str
    team_number: int
    members: List[TeamMemberResponse] = []
    total_score: int = 0
