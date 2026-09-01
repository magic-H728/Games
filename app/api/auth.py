from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.auth import PlayerLoginRequest, StaffLoginRequest, TokenResponse
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/player/login", response_model=TokenResponse)
async def player_login(req: PlayerLoginRequest, db: AsyncSession = Depends(get_db)):
    """玩家使用姓名+学号登录"""
    return await auth_service.player_login(db, req.name, req.student_id)


@router.post("/staff/login", response_model=TokenResponse)
async def staff_login(req: StaffLoginRequest, db: AsyncSession = Depends(get_db)):
    """工作人员使用账号密码登录"""
    return await auth_service.staff_login(db, req.username, req.password)
