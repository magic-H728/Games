from typing import Optional
import csv
import os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.models.player import Player, GamePlayer, GamePlayerStatus
from app.models.game import Game, GameStatus
from app.core.security import create_token, hash_password, verify_password
from app.core.config import get_settings
from app.schemas.auth import TokenResponse

settings = get_settings()

# CSV文件路径
CSV_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "players.csv")


def load_players_from_csv():
    """从CSV文件加载玩家列表"""
    players = {}
    if not os.path.exists(CSV_FILE_PATH):
        return players

    try:
        with open(CSV_FILE_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                student_id = (row.get('student_id') or '').strip()
                name = (row.get('name') or '').strip()
                wechat_id = (row.get('wechat_id') or '').strip()
                if student_id and name:
                    players[student_id] = {
                        'name': name,
                        'wechat_id': wechat_id
                    }
    except Exception as e:
        print(f"Error loading CSV: {e}")

    return players


def validate_player(name: str, student_id: str) -> bool:
    """验证玩家是否在CSV名单中"""
    players = load_players_from_csv()

    if student_id not in players:
        return False

    if players[student_id]['name'] != name:
        return False

    return True


async def player_login(db: AsyncSession, name: str, student_id: str) -> TokenResponse:
    """Player login with name + student_id."""

    # 验证玩家是否在CSV名单中
    if not validate_player(name, student_id):
        raise HTTPException(
            status_code=400,
            detail="姓名或学号不正确，请检查后重试"
        )

    # Find or create player
    result = await db.execute(select(Player).where(Player.student_id == student_id))
    player = result.scalar_one_or_none()

    if player is None:
        # 从CSV获取微信ID
        csv_players = load_players_from_csv()
        wechat_id = csv_players.get(student_id, {}).get('wechat_id', '')

        player = Player(
            name=name,
            student_id=student_id,
            wechat_id=wechat_id if wechat_id else None
        )
        db.add(player)
        await db.flush()
    elif player.name != name:
        raise HTTPException(status_code=400, detail="学号与姓名不匹配")

    # Find current game (any game, including finished)
    result = await db.execute(
        select(Game).order_by(Game.id.desc())
    )
    game = result.scalars().first()

    if game is None:
        raise HTTPException(status_code=404, detail="当前没有可加入的游戏，请等待工作人员创建")

    # Find or create game player (use first() to handle potential duplicates)
    result = await db.execute(
        select(GamePlayer).where(
            GamePlayer.game_id == game.id,
            GamePlayer.player_id == player.id
        )
    )
    game_player = result.scalars().first()

    if game_player is None:
        # 新玩家 - 只能在游戏等待阶段加入
        if game.status not in [GameStatus.PENDING, GameStatus.READY]:
            raise HTTPException(
                status_code=400,
                detail=f"游戏已开始（状态：{game.status}），新玩家无法加入。请联系工作人员。"
            )
        game_player = GamePlayer(
            game_id=game.id,
            player_id=player.id,
            status=GamePlayerStatus.WAITING
        )
        db.add(game_player)
        await db.flush()
    else:
        # 已存在的玩家 - 可以随时登录
        # 更新在线状态
        from datetime import datetime, timezone
        game_player.is_online = True
        game_player.last_seen_at = datetime.now(timezone.utc)

    # Create token
    token = create_token({
        "sub": str(player.id),
        "role": "PLAYER",
        "player_id": player.id,
        "game_player_id": game_player.id,
        "game_id": game.id
    })

    return TokenResponse(
        access_token=token,
        role="PLAYER",
        player_id=player.id,
        game_player_id=game_player.id
    )


async def staff_login(db: AsyncSession, username: str, password: str) -> TokenResponse:
    """Staff login with username + password."""
    if username != settings.STAFF_USERNAME or password != settings.STAFF_PASSWORD:
        raise HTTPException(status_code=401, detail="账号或密码错误")

    token = create_token({
        "sub": username,
        "role": "STAFF"
    })

    return TokenResponse(access_token=token, role="STAFF")
