from typing import Optional, List, Tuple
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func as sql_func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import require_player
from app.models.player import Player, GamePlayer, GamePlayerStatus
from app.models.game import Game, GameStatus
from app.models.team import Team
from app.models.score import ScoreTransaction
from app.schemas.player import GamePlayerResponse, PlayerProfileUpdate, PlayerInfoBrief
from app.services import score_service, team_service

router = APIRouter(prefix="/api", tags=["玩家"])


@router.get("/games/current")
async def get_current_game_status(
    db: AsyncSession = Depends(get_db)
):
    """获取当前游戏状态（公开接口，包括已结束的游戏）"""
    result = await db.execute(
        select(Game).order_by(Game.id.desc())
    )
    game = result.scalars().first()

    if game is None:
        raise HTTPException(status_code=404, detail="当前没有进行中的游戏")

    return {
        "id": game.id,
        "name": game.name,
        "status": game.status,
        "started_at": game.started_at.isoformat() if game.started_at else None,
        "finished_at": game.finished_at.isoformat() if game.finished_at else None
    }


async def _get_current_game_player(
    payload: dict = Depends(require_player),
    db: AsyncSession = Depends(get_db)
) -> Tuple[GamePlayer, bool]:
    """Get current player's game_player record. Returns (game_player, is_new)."""
    game_player_id = payload.get("game_player_id")
    player_id = payload.get("player_id")

    # Try to find existing game_player
    result = await db.execute(select(GamePlayer).where(GamePlayer.id == game_player_id))
    gp = result.scalar_one_or_none()

    if gp is not None:
        return gp, False

    # Game player not found (might be after game reset)
    # Try to find latest game (including finished)
    result = await db.execute(
        select(Game).order_by(Game.id.desc())
    )
    game = result.scalars().first()

    if game is None:
        raise HTTPException(status_code=404, detail="当前没有可加入的游戏，请等待工作人员创建")

    # If game is finished, don't create new player - just show error
    if game.status == GameStatus.FINISHED:
        raise HTTPException(status_code=404, detail="游戏已结束，无法加入")

    # Only allow joining if game is in PENDING/READY state
    if game.status not in [GameStatus.PENDING, GameStatus.READY]:
        raise HTTPException(status_code=400, detail="游戏已开始，无法加入")

    # Create new game_player for this player
    new_gp = GamePlayer(
        game_id=game.id,
        player_id=player_id,
        status=GamePlayerStatus.WAITING
    )
    db.add(new_gp)
    await db.flush()

    return new_gp, True


@router.get("/players/me")
async def get_my_info(
    gp_tuple: Tuple[GamePlayer, bool] = Depends(_get_current_game_player),
    payload: dict = Depends(require_player),
    db: AsyncSession = Depends(get_db)
):
    """获取自己的游戏信息"""
    from datetime import datetime, timezone
    from app.core.security import create_token

    gp, is_new = gp_tuple

    # Update last_seen_at
    gp.last_seen_at = datetime.now(timezone.utc)
    gp.is_online = True

    # Generate new token if game_player was re-created
    new_token = None
    if is_new:
        new_token = create_token({
            "sub": str(gp.player_id),
            "role": "PLAYER",
            "player_id": gp.player_id,
            "game_player_id": gp.id,
            "game_id": gp.game_id
        })

    # Get player info
    result = await db.execute(select(Player).where(Player.id == gp.player_id))
    player = result.scalar_one_or_none()

    # Get team name
    team_name = None
    if gp.team_id:
        from app.models.team import Team
        result = await db.execute(select(Team).where(Team.id == gp.team_id))
        team = result.scalar_one_or_none()
        if team:
            team_name = team.name

    # Get total score
    total_score = await score_service.get_player_total_score(db, gp.id)

    # Get capture count (for cats)
    capture_count = 0
    if gp.role == "CAT":
        from app.models.capture import CaptureRecord
        result = await db.execute(
            select(sql_func.count()).select_from(CaptureRecord).where(CaptureRecord.cat_id == gp.id)
        )
        capture_count = result.scalar() or 0

    # Build response with optional new token
    response_data = {
        "id": gp.id,
        "game_id": gp.game_id,
        "player_id": gp.player_id,
        "qr_token": gp.qr_token,
        "role": gp.role,
        "status": gp.status,
        "is_online": gp.is_online,
        "team_id": gp.team_id,
        "team_name": team_name,
        "survival_round": gp.survival_round,
        "total_survival_seconds": gp.total_survival_seconds,
        "revive_count": gp.revive_count,
        "protect_until": gp.protect_until.isoformat() if gp.protect_until else None,
        "joined_at": gp.joined_at.isoformat() if gp.joined_at else None,
        "died_at": gp.died_at.isoformat() if gp.died_at else None,
        "player_name": player.name if player else None,
        "student_id": player.student_id if player else None,
        "wechat_id": player.wechat_id if player else None,
        "total_score": total_score,
        "capture_count": capture_count
    }

    if new_token:
        response_data["new_token"] = new_token

    return response_data


@router.get("/players/me/team")
async def get_my_team(
    gp_tuple: Tuple[GamePlayer, bool] = Depends(_get_current_game_player),
    db: AsyncSession = Depends(get_db)
):
    """获取自己的队伍信息"""
    gp, _ = gp_tuple
    team_info = await team_service.get_player_team(db, gp)
    if team_info is None:
        return {"team": None, "members": []}

    from app.models.team import Team
    team = team_info["team"]
    members = team_info["members"]

    member_list = []
    for m in members:
        result = await db.execute(select(Player).where(Player.id == m.player_id))
        player = result.scalar_one_or_none()
        score = await score_service.get_player_total_score(db, m.id)
        member_list.append({
            "id": m.id,
            "name": player.name if player else "未知",
            "student_id": player.student_id if player else "",
            "wechat_id": player.wechat_id if player else None,
            "role": m.role,
            "status": m.status,
            "total_score": score
        })

    # Get team total score
    team_score = await score_service.get_team_total_score(db, team.id)

    return {
        "team": {
            "id": team.id,
            "name": team.name,
            "role": team.role,
            "team_number": team.team_number,
            "total_score": team_score
        },
        "members": member_list
    }


@router.get("/players/me/score")
async def get_my_score(
    gp_tuple: Tuple[GamePlayer, bool] = Depends(_get_current_game_player),
    db: AsyncSession = Depends(get_db)
):
    """获取自己的积分详情"""
    gp, _ = gp_tuple
    return await score_service.get_player_score_breakdown(db, gp.id)


@router.put("/players/me/profile")
async def update_my_profile(
    req: PlayerProfileUpdate,
    gp_tuple: Tuple[GamePlayer, bool] = Depends(_get_current_game_player),
    db: AsyncSession = Depends(get_db)
):
    """更新自己的个人信息（仅微信号）"""
    gp, _ = gp_tuple
    result = await db.execute(select(Player).where(Player.id == gp.player_id))
    player = result.scalar_one_or_none()
    if player and req.wechat_id is not None:
        player.wechat_id = req.wechat_id
    return {"success": True, "message": "个人信息已更新"}


@router.get("/players/me/score-transactions")
async def get_my_score_transactions(
    gp_tuple: Tuple[GamePlayer, bool] = Depends(_get_current_game_player),
    db: AsyncSession = Depends(get_db)
):
    """获取自己的积分流水"""
    gp, _ = gp_tuple
    from app.models.score import ScoreTransaction
    result = await db.execute(
        select(ScoreTransaction)
        .where(ScoreTransaction.game_player_id == gp.id)
        .order_by(ScoreTransaction.created_at.desc())
    )
    transactions = result.scalars().all()
    return [
        {
            "id": tx.id,
            "score": tx.score,
            "type": tx.type,
            "reason": tx.reason,
            "created_at": tx.created_at.isoformat() if tx.created_at else None
        }
        for tx in transactions
    ]


@router.get("/players/me/captures")
async def get_my_captures(
    gp_tuple: Tuple[GamePlayer, bool] = Depends(_get_current_game_player),
    db: AsyncSession = Depends(get_db)
):
    """获取猫的抓捕记录"""
    gp, _ = gp_tuple
    from app.models.capture import CaptureRecord

    result = await db.execute(
        select(CaptureRecord)
        .where(CaptureRecord.cat_id == gp.id)
        .order_by(CaptureRecord.captured_at.desc())
    )
    captures = result.scalars().all()

    capture_list = []
    for c in captures:
        # 获取鼠的信息
        mouse_result = await db.execute(
            select(GamePlayer)
            .options(selectinload(GamePlayer.player))
            .where(GamePlayer.id == c.mouse_id)
        )
        mouse = mouse_result.scalar_one_or_none()

        capture_list.append({
            "id": c.id,
            "mouse_id": c.mouse_id,
            "mouse_name": mouse.player.name if mouse and mouse.player else "未知",
            "student_id": mouse.player.student_id if mouse and mouse.player else "",
            "score": c.score_awarded,
            "captured_at": c.captured_at.isoformat() if c.captured_at else None
        })

    return capture_list


@router.get("/players/{game_player_id}/brief")
async def get_player_brief(
    game_player_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取玩家简要信息"""
    result = await db.execute(
        select(GamePlayer)
        .options(selectinload(GamePlayer.player))
        .where(GamePlayer.id == game_player_id)
    )
    gp = result.scalar_one_or_none()

    if gp is None:
        raise HTTPException(status_code=404, detail="未找到该玩家")

    team_name = None
    if gp.team_id:
        from app.models.team import Team
        team_result = await db.execute(select(Team).where(Team.id == gp.team_id))
        team = team_result.scalar_one_or_none()
        if team:
            team_name = team.name

    return {
        "id": gp.id,
        "name": gp.player.name if gp.player else "未知",
        "student_id": gp.player.student_id if gp.player else "",
        "wechat_id": gp.player.wechat_id if gp.player else None,
        "role": gp.role,
        "status": gp.status,
        "team_name": team_name
    }


@router.get("/players/{game_player_id}/score-detail")
async def get_player_score_detail(
    game_player_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取玩家积分详情"""
    # Get game player
    result = await db.execute(
        select(GamePlayer)
        .options(selectinload(GamePlayer.player))
        .where(GamePlayer.id == game_player_id)
    )
    gp = result.scalar_one_or_none()
    if gp is None:
        raise HTTPException(status_code=404, detail="未找到该玩家")

    # Get score breakdown
    breakdown = await score_service.get_player_score_breakdown(db, gp.id)

    # Get transactions
    tx_result = await db.execute(
        select(ScoreTransaction)
        .where(ScoreTransaction.game_player_id == gp.id)
        .order_by(ScoreTransaction.created_at.desc())
    )
    transactions = tx_result.scalars().all()

    return {
        "player_name": gp.player.name if gp.player else "未知",
        "total_score": breakdown.get("total", 0),
        "capture_score": breakdown.get("CAPTURE", 0),
        "minigame_score": breakdown.get("MINIGAME", 0),
        "survival_score": breakdown.get("SURVIVAL", 0),
        "transactions": [
            {
                "score": tx.score,
                "type": tx.type,
                "reason": tx.reason,
                "created_at": tx.created_at.isoformat() if tx.created_at else None
            }
            for tx in transactions
        ]
    }


@router.get("/teams/{team_id}/detail")
async def get_team_detail(
    team_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取队伍详情"""
    # Get team
    team_result = await db.execute(select(Team).where(Team.id == team_id))
    team = team_result.scalar_one_or_none()
    if team is None:
        raise HTTPException(status_code=404, detail="未找到该队伍")

    # Get team members
    members_result = await db.execute(
        select(GamePlayer)
        .options(selectinload(GamePlayer.player))
        .where(GamePlayer.team_id == team_id)
    )
    members = members_result.scalars().all()

    member_list = []
    total_score = 0
    for m in members:
        m_score = await score_service.get_player_total_score(db, m.id)
        total_score += m_score
        member_list.append({
            "id": m.id,
            "name": m.player.name if m.player else "未知",
            "student_id": m.player.student_id if m.player else "",
            "role": m.role,
            "status": m.status,
            "score": m_score
        })

    return {
        "team_id": team.id,
        "team_name": team.name,
        "role": team.role,
        "total_score": total_score,
        "members": member_list
    }


@router.get("/players/me/history")
async def get_my_history(
    payload: dict = Depends(require_player),
    db: AsyncSession = Depends(get_db)
):
    """获取玩家的游戏历史记录"""
    player_id = payload.get("player_id")

    # Get all games this player has participated in
    result = await db.execute(
        select(GamePlayer)
        .where(GamePlayer.player_id == player_id)
        .order_by(GamePlayer.id.desc())
    )
    game_players = result.scalars().all()

    # Get current game
    current_game_result = await db.execute(
        select(Game).order_by(Game.id.desc())
    )
    current_game = current_game_result.scalars().first()

    history = []
    for gp in game_players:
        # Get game info
        game_result = await db.execute(select(Game).where(Game.id == gp.game_id))
        game = game_result.scalar_one_or_none()
        if not game:
            continue

        # Get team name
        team_name = None
        if gp.team_id:
            team_result = await db.execute(select(Team).where(Team.id == gp.team_id))
            team = team_result.scalar_one_or_none()
            if team:
                team_name = team.name

        # Get score
        score = await score_service.get_player_total_score(db, gp.id)

        # Get capture count for cats
        capture_count = 0
        if gp.role == "CAT":
            from app.models.capture import CaptureRecord
            cap_result = await db.execute(
                select(sql_func.count()).select_from(CaptureRecord).where(CaptureRecord.cat_id == gp.id)
            )
            capture_count = cap_result.scalar() or 0

        history.append({
            "game_id": game.id,
            "name": game.name,
            "status": game.status,
            "my_role": gp.role,
            "my_team": team_name,
            "my_score": score,
            "capture_count": capture_count,
            "revive_count": gp.revive_count,
            "is_current": current_game and game.id == current_game.id,
            "started_at": game.started_at.isoformat() if game.started_at else None,
            "finished_at": game.finished_at.isoformat() if game.finished_at else None,
            "survival_seconds": gp.total_survival_seconds
        })

    return history


@router.get("/players/me/history/{game_id}")
async def get_game_detail(
    game_id: int,
    payload: dict = Depends(require_player),
    db: AsyncSession = Depends(get_db)
):
    """获取某场游戏的详细数据"""
    player_id = payload.get("player_id")

    # Get game
    game_result = await db.execute(select(Game).where(Game.id == game_id))
    game = game_result.scalar_one_or_none()
    if game is None:
        raise HTTPException(status_code=404, detail="未找到该游戏")

    # Get player's game_player for this game
    gp_result = await db.execute(
        select(GamePlayer)
        .options(selectinload(GamePlayer.player))
        .where(GamePlayer.game_id == game_id, GamePlayer.player_id == player_id)
    )
    gp = gp_result.scalar_one_or_none()
    if gp is None:
        raise HTTPException(status_code=404, detail="你未参与此游戏")

    # Get team info
    team_name = None
    team_members = []
    if gp.team_id:
        team_result = await db.execute(select(Team).where(Team.id == gp.team_id))
        team = team_result.scalar_one_or_none()
        if team:
            team_name = team.name

            # Get team members
            members_result = await db.execute(
                select(GamePlayer)
                .options(selectinload(GamePlayer.player))
                .where(GamePlayer.team_id == gp.team_id)
            )
            members = members_result.scalars().all()

            for m in members:
                m_score = await score_service.get_player_total_score(db, m.id)
                team_members.append({
                    "name": m.player.name if m.player else "未知",
                    "role": m.role,
                    "score": m_score,
                    "is_self": m.id == gp.id
                })

    # Get score
    total_score = await score_service.get_player_total_score(db, gp.id)

    # Get score transactions
    tx_result = await db.execute(
        select(ScoreTransaction)
        .where(ScoreTransaction.game_player_id == gp.id)
        .order_by(ScoreTransaction.created_at.desc())
    )
    transactions = tx_result.scalars().all()

    score_transactions = [
        {
            "score": tx.score,
            "type": tx.type,
            "reason": tx.reason
        }
        for tx in transactions
    ]

    # Get capture count for cats
    capture_count = 0
    if gp.role == "CAT":
        from app.models.capture import CaptureRecord
        cap_result = await db.execute(
            select(sql_func.count()).select_from(CaptureRecord).where(CaptureRecord.cat_id == gp.id)
        )
        capture_count = cap_result.scalar() or 0

    # Get ranking (if game is finished)
    player_rank = None
    team_rank = None
    if game.status == GameStatus.FINISHED:
        # Player ranking
        all_scores_result = await db.execute(
            select(
                GamePlayer.id,
                sql_func.coalesce(sql_func.sum(ScoreTransaction.score), 0).label("total_score")
            )
            .outerjoin(ScoreTransaction, ScoreTransaction.game_player_id == GamePlayer.id)
            .where(GamePlayer.game_id == game_id)
            .group_by(GamePlayer.id)
            .order_by(sql_func.coalesce(sql_func.sum(ScoreTransaction.score), 0).desc())
        )
        all_scores = all_scores_result.all()
        for i, row in enumerate(all_scores, 1):
            if row.id == gp.id:
                player_rank = i
                break

        # Team ranking
        if gp.team_id:
            all_teams_result = await db.execute(select(Team).where(Team.game_id == game_id))
            all_teams = all_teams_result.scalars().all()

            team_scores = []
            for t in all_teams:
                t_score_result = await db.execute(
                    select(sql_func.coalesce(sql_func.sum(ScoreTransaction.score), 0))
                    .join(GamePlayer, GamePlayer.id == ScoreTransaction.game_player_id)
                    .where(GamePlayer.team_id == t.id)
                )
                t_score = t_score_result.scalar() or 0
                team_scores.append({"team_id": t.id, "score": t_score})

            team_scores.sort(key=lambda x: x["score"], reverse=True)
            for i, ts in enumerate(team_scores, 1):
                if ts["team_id"] == gp.team_id:
                    team_rank = i
                    break

    return {
        "game": {
            "id": game.id,
            "name": game.name,
            "status": game.status,
            "started_at": game.started_at.isoformat() if game.started_at else None,
            "finished_at": game.finished_at.isoformat() if game.finished_at else None
        },
        "my_data": {
            "role": gp.role,
            "status": gp.status,
            "team": team_name,
            "total_score": total_score,
            "capture_count": capture_count,
            "revive_count": gp.revive_count,
            "survival_seconds": gp.total_survival_seconds
        },
        "team_data": {
            "name": team_name,
            "members": team_members
        },
        "score_transactions": score_transactions,
        "ranking": {
            "player_rank": player_rank,
            "team_rank": team_rank
        }
    }
