from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func as sql_func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import require_staff
from app.models.player import Player, GamePlayer, PlayerRole, GamePlayerStatus
from app.models.game import Game, GameStatus
from app.models.team import Team
from app.models.score import ScoreTransaction, ScoreType
from app.schemas.game import GameCreateRequest, GameResponse, GameOverviewResponse
from app.services import game_service, role_service, team_service, score_service

router = APIRouter(prefix="/api/staff", tags=["工作人员"])


async def _get_game(db: AsyncSession) -> Game:
    return await game_service.get_current_game(db)


# ============ Game Management ============

@router.post("/games", response_model=GameResponse)
async def create_game(
    req: GameCreateRequest,
    payload: dict = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    """创建新游戏"""
    game = await game_service.create_game(db, req)
    return GameResponse.model_validate(game)


@router.get("/games/current/overview", response_model=GameOverviewResponse)
async def game_overview(
    payload: dict = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    """获取当前游戏总览"""
    game = await _get_game(db)
    return await game_service.get_game_overview(db, game)


@router.post("/games/current/start")
async def start_game(
    payload: dict = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    """开始游戏"""
    game = await _get_game(db)
    game = await game_service.start_game(db, game)
    return {"success": True, "message": "游戏已开始", "status": game.status}


@router.post("/games/current/finish")
async def finish_game(
    payload: dict = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    """结束游戏"""
    game = await _get_game(db)
    game = await game_service.finish_game(db, game)
    return {"success": True, "message": "游戏已结束", "status": game.status}


@router.post("/games/current/pause")
async def pause_game(
    payload: dict = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    """暂停游戏"""
    game = await _get_game(db)
    if game.status != GameStatus.RUNNING:
        raise HTTPException(status_code=400, detail="只有进行中的游戏才能暂停")

    game.status = GameStatus.PAUSED
    return {"success": True, "message": "游戏已暂停", "status": game.status}


@router.post("/games/current/resume")
async def resume_game(
    payload: dict = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    """继续游戏"""
    game = await _get_game(db)
    if game.status != GameStatus.PAUSED:
        raise HTTPException(status_code=400, detail="只有暂停的游戏才能继续")

    game.status = GameStatus.RUNNING
    return {"success": True, "message": "游戏已继续", "status": game.status}


@router.post("/games/current/settle")
async def settle_game(
    payload: dict = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    """结算游戏 - 计算生存积分但不结束游戏"""
    from app.models.survival import SurvivalRecord
    from datetime import datetime, timezone

    game = await _get_game(db)
    if game.status not in [GameStatus.RUNNING, GameStatus.PAUSED]:
        raise HTTPException(status_code=400, detail="只有进行中或暂停的游戏才能结算")

    now = datetime.now(timezone.utc)

    # 结算所有鼠的生存时间
    result = await db.execute(
        select(GamePlayer).where(
            GamePlayer.game_id == game.id,
            GamePlayer.role == PlayerRole.MOUSE
        )
    )
    mice = result.scalars().all()

    settled_count = 0
    for mouse in mice:
        # 结算当前正在进行的生存记录
        survival_result = await db.execute(
            select(SurvivalRecord).where(
                SurvivalRecord.game_player_id == mouse.id,
                SurvivalRecord.ended_at.is_(None)
            )
        )
        active_survival = survival_result.scalar_one_or_none()

        if active_survival:
            # 结束当前生存记录
            started = active_survival.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            active_survival.ended_at = now
            active_survival.duration_seconds = (now - started).total_seconds()
            mouse.total_survival_seconds += active_survival.duration_seconds

        # 计算生存积分
        interval = game.survival_interval_seconds
        score_per_interval = game.survival_interval_score

        if interval > 0:
            intervals = int(mouse.total_survival_seconds // interval)
            survival_score = intervals * score_per_interval

            if survival_score > 0:
                # 检查是否已经结算过生存积分
                existing_result = await db.execute(
                    select(ScoreTransaction).where(
                        ScoreTransaction.game_player_id == mouse.id,
                        ScoreTransaction.type == ScoreType.SURVIVAL
                    )
                )
                existing = existing_result.scalar_one_or_none()

                if not existing:
                    total_minutes = int(mouse.total_survival_seconds // 60)
                    tx = ScoreTransaction(
                        game_id=game.id,
                        game_player_id=mouse.id,
                        score=survival_score,
                        type=ScoreType.SURVIVAL,
                        reason=f"累计生存 {total_minutes} 分钟"
                    )
                    db.add(tx)
                    settled_count += 1

    return {
        "success": True,
        "message": f"结算完成，已为 {settled_count} 只鼠计算生存积分",
        "settled_count": settled_count
    }


@router.delete("/games/current")
async def reset_game(
    payload: dict = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    """重置/删除当前游戏（用于重新开始）"""
    from sqlalchemy import delete as sql_delete
    from app.models.capture import CaptureRecord
    from app.models.survival import SurvivalRecord
    from app.models.mini_game import MiniGame, MiniGameAttempt
    from app.models.score import ScoreTransaction
    from app.models.team import Team

    # Get current game
    result = await db.execute(
        select(Game).where(Game.status != GameStatus.FINISHED).order_by(Game.id.desc())
    )
    game = result.scalar_one_or_none()

    if game is None:
        raise HTTPException(status_code=404, detail="没有可重置的游戏")

    # Delete all related data
    await db.execute(sql_delete(ScoreTransaction).where(ScoreTransaction.game_id == game.id))
    await db.execute(sql_delete(CaptureRecord).where(CaptureRecord.game_id == game.id))
    await db.execute(sql_delete(MiniGameAttempt).where(MiniGameAttempt.mini_game_id.in_(
        select(MiniGame.id).where(MiniGame.game_id == game.id)
    )))
    await db.execute(sql_delete(MiniGame).where(MiniGame.game_id == game.id))

    # Delete survival records for players in this game
    player_ids = select(GamePlayer.id).where(GamePlayer.game_id == game.id)
    await db.execute(sql_delete(SurvivalRecord).where(SurvivalRecord.game_player_id.in_(player_ids)))

    # Delete game players and teams
    await db.execute(sql_delete(GamePlayer).where(GamePlayer.game_id == game.id))
    await db.execute(sql_delete(Team).where(Team.game_id == game.id))

    # Delete the game
    await db.execute(sql_delete(Game).where(Game.id == game.id))

    await db.flush()

    return {"success": True, "message": "游戏已重置，可以创建新游戏"}


from app.models.game import GameStatus


# ============ Role Management ============

@router.post("/games/current/assign-cat")
async def assign_cat(
    qr_token: str,
    payload: dict = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    """扫码指定某玩家为猫（立即赋予身份）"""
    game = await _get_game(db)
    result = await db.execute(
        select(GamePlayer)
        .options(selectinload(GamePlayer.player))
        .where(GamePlayer.qr_token == qr_token, GamePlayer.game_id == game.id)
    )
    gp = result.scalar_one_or_none()
    if gp is None:
        raise HTTPException(status_code=404, detail="未找到该玩家")

    # Immediately assign CAT role
    from datetime import datetime, timezone
    gp.role = PlayerRole.CAT
    gp.status = GamePlayerStatus.ALIVE
    gp.role_assigned_at = datetime.now(timezone.utc)
    gp.pre_assigned_cat = True

    return {
        "success": True,
        "message": f"{gp.player.name if gp.player else '未知'} 已成为猫 🐱",
        "player_name": gp.player.name if gp.player else None,
        "student_id": gp.player.student_id if gp.player else None
    }


@router.post("/games/current/assign-roles")
async def assign_roles(
    cat_ratio: float = 0.1,
    payload: dict = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    """执行身份分配"""
    game = await _get_game(db)
    game.cat_ratio = cat_ratio
    result = await role_service.assign_roles(db, game)
    return {"success": True, "message": "身份分配完成", **result}


# ============ Team Management ============

@router.post("/games/current/create-teams")
async def create_teams(
    cat_team_count: int = 5,
    mouse_team_count: int = 10,
    payload: dict = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    """执行自动分队"""
    game = await _get_game(db)
    game.cat_team_count = cat_team_count
    game.mouse_team_count = mouse_team_count
    result = await team_service.create_teams(db, game)
    return {"success": True, "message": "分队完成", **result}


# ============ Player Management ============

@router.get("/players")
async def list_players(
    role: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    payload: dict = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    """获取所有玩家列表"""
    game = await _get_game(db)

    query = select(GamePlayer).where(GamePlayer.game_id == game.id)
    if role:
        query = query.where(GamePlayer.role == role)
    if status:
        query = query.where(GamePlayer.status == status)

    result = await db.execute(query)
    players = result.scalars().all()

    player_list = []
    for gp in players:
        result = await db.execute(select(Player).where(Player.id == gp.player_id))
        player = result.scalar_one_or_none()

        if search and player:
            # 搜索姓名、学号、微信号、身份码
            if (search not in player.name and
                search not in player.student_id and
                search not in (player.wechat_id or "") and
                search not in gp.qr_token):
                continue

        team_name = None
        if gp.team_id:
            result = await db.execute(select(Team).where(Team.id == gp.team_id))
            team = result.scalar_one_or_none()
            if team:
                team_name = team.name

        score = await score_service.get_player_total_score(db, gp.id)

        player_list.append({
            "id": gp.id,
            "player_id": gp.player_id,
            "name": player.name if player else "未知",
            "student_id": player.student_id if player else "",
            "wechat_id": player.wechat_id if player else None,
            "qr_token": gp.qr_token,
            "role": gp.role,
            "status": gp.status,
            "is_online": gp.is_online,
            "team_name": team_name,
            "survival_round": gp.survival_round,
            "revive_count": gp.revive_count,
            "total_score": score
        })

    return player_list


@router.get("/players/{game_player_id}")
async def get_player_detail(
    game_player_id: int,
    payload: dict = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    """获取玩家详细信息"""
    result = await db.execute(select(GamePlayer).where(GamePlayer.id == game_player_id))
    gp = result.scalar_one_or_none()
    if gp is None:
        raise HTTPException(status_code=404, detail="未找到该玩家")

    result = await db.execute(select(Player).where(Player.id == gp.player_id))
    player = result.scalar_one_or_none()

    team_name = None
    if gp.team_id:
        result = await db.execute(select(Team).where(Team.id == gp.team_id))
        team = result.scalar_one_or_none()
        if team:
            team_name = team.name

    score_breakdown = await score_service.get_player_score_breakdown(db, gp.id)

    # Get score transactions
    result = await db.execute(
        select(ScoreTransaction)
        .where(ScoreTransaction.game_player_id == gp.id)
        .order_by(ScoreTransaction.created_at.desc())
    )
    transactions = result.scalars().all()

    return {
        "id": gp.id,
        "name": player.name if player else "未知",
        "student_id": player.student_id if player else "",
        "wechat_id": player.wechat_id if player else None,
        "role": gp.role,
        "status": gp.status,
        "is_online": gp.is_online,
        "team_name": team_name,
        "survival_round": gp.survival_round,
        "total_survival_seconds": gp.total_survival_seconds,
        "revive_count": gp.revive_count,
        "joined_at": gp.joined_at.isoformat() if gp.joined_at else None,
        "died_at": gp.died_at.isoformat() if gp.died_at else None,
        "score_breakdown": score_breakdown,
        "score_transactions": [
            {
                "id": tx.id,
                "score": tx.score,
                "type": tx.type,
                "reason": tx.reason,
                "created_at": tx.created_at.isoformat() if tx.created_at else None
            }
            for tx in transactions
        ]
    }


@router.post("/players/{game_player_id}/adjust-score")
async def adjust_player_score(
    game_player_id: int,
    score: int,
    reason: str,
    payload: dict = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    """手动调整玩家积分"""
    result = await db.execute(select(GamePlayer).where(GamePlayer.id == game_player_id))
    gp = result.scalar_one_or_none()
    if gp is None:
        raise HTTPException(status_code=404, detail="未找到该玩家")

    game = await _get_game(db)
    tx = ScoreTransaction(
        game_id=game.id,
        game_player_id=gp.id,
        score=score,
        type=ScoreType.MANUAL,
        reason=f"工作人员手动调整: {reason}"
    )
    db.add(tx)

    return {"success": True, "message": f"积分已调整 {score:+d}"}


@router.get("/csv-players")
async def get_csv_players(
    payload: dict = Depends(require_staff)
):
    """获取CSV中的玩家名单"""
    from app.services.auth_service import load_players_from_csv
    players = load_players_from_csv()
    return {
        "players": [
            {"name": info["name"], "student_id": sid, "wechat_id": info.get("wechat_id", "")}
            for sid, info in players.items()
        ],
        "total": len(players)
    }


@router.get("/games/history")
async def get_games_history(
    payload: dict = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    """获取历史游戏记录"""
    from app.models.player import PlayerRole, GamePlayerStatus
    from app.models.capture import CaptureRecord

    result = await db.execute(select(Game).order_by(Game.id.desc()))
    games = result.scalars().all()

    history = []
    for game in games:
        # Count players
        total_result = await db.execute(
            select(sql_func.count()).select_from(GamePlayer).where(GamePlayer.game_id == game.id)
        )
        cats_result = await db.execute(
            select(sql_func.count()).select_from(GamePlayer).where(
                GamePlayer.game_id == game.id, GamePlayer.role == PlayerRole.CAT
            )
        )
        mice_result = await db.execute(
            select(sql_func.count()).select_from(GamePlayer).where(
                GamePlayer.game_id == game.id, GamePlayer.role == PlayerRole.MOUSE
            )
        )
        alive_result = await db.execute(
            select(sql_func.count()).select_from(GamePlayer).where(
                GamePlayer.game_id == game.id,
                GamePlayer.role == PlayerRole.MOUSE,
                GamePlayer.status == GamePlayerStatus.ALIVE
            )
        )
        dead_result = await db.execute(
            select(sql_func.count()).select_from(GamePlayer).where(
                GamePlayer.game_id == game.id,
                GamePlayer.role == PlayerRole.MOUSE,
                GamePlayer.status == GamePlayerStatus.DEAD
            )
        )
        captures_result = await db.execute(
            select(sql_func.count()).select_from(CaptureRecord).where(CaptureRecord.game_id == game.id)
        )

        history.append({
            "id": game.id,
            "name": game.name,
            "status": game.status,
            "created_at": game.created_at.isoformat() if game.created_at else None,
            "started_at": game.started_at.isoformat() if game.started_at else None,
            "finished_at": game.finished_at.isoformat() if game.finished_at else None,
            "total": total_result.scalar() or 0,
            "cats": cats_result.scalar() or 0,
            "mice": mice_result.scalar() or 0,
            "alive": alive_result.scalar() or 0,
            "dead": dead_result.scalar() or 0,
            "captures": captures_result.scalar() or 0,
            "revives": 0  # TODO: count revives
        })

    return history


@router.get("/games/{game_id}/detail")
async def get_game_detail(
    game_id: int,
    payload: dict = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    """获取游戏详情"""
    from app.models.player import PlayerRole, GamePlayerStatus
    from app.models.capture import CaptureRecord

    result = await db.execute(select(Game).where(Game.id == game_id))
    game = result.scalar_one_or_none()
    if game is None:
        raise HTTPException(status_code=404, detail="未找到该游戏")

    # Get stats
    total_result = await db.execute(
        select(sql_func.count()).select_from(GamePlayer).where(GamePlayer.game_id == game.id)
    )
    cats_result = await db.execute(
        select(sql_func.count()).select_from(GamePlayer).where(
            GamePlayer.game_id == game.id, GamePlayer.role == PlayerRole.CAT
        )
    )
    mice_result = await db.execute(
        select(sql_func.count()).select_from(GamePlayer).where(
            GamePlayer.game_id == game.id, GamePlayer.role == PlayerRole.MOUSE
        )
    )
    alive_result = await db.execute(
        select(sql_func.count()).select_from(GamePlayer).where(
            GamePlayer.game_id == game.id,
            GamePlayer.role == PlayerRole.MOUSE,
            GamePlayer.status == GamePlayerStatus.ALIVE
        )
    )
    dead_result = await db.execute(
        select(sql_func.count()).select_from(GamePlayer).where(
            GamePlayer.game_id == game.id,
            GamePlayer.role == PlayerRole.MOUSE,
            GamePlayer.status == GamePlayerStatus.DEAD
        )
    )
    captures_result = await db.execute(
        select(sql_func.count()).select_from(CaptureRecord).where(CaptureRecord.game_id == game.id)
    )

    # Get top 10 players by score
    top_players_query = (
        select(
            GamePlayer.id,
            GamePlayer.role,
            sql_func.coalesce(sql_func.sum(ScoreTransaction.score), 0).label("total_score")
        )
        .outerjoin(ScoreTransaction, ScoreTransaction.game_player_id == GamePlayer.id)
        .where(GamePlayer.game_id == game.id)
        .group_by(GamePlayer.id)
        .order_by(sql_func.coalesce(sql_func.sum(ScoreTransaction.score), 0).desc())
        .limit(10)
    )
    top_result = await db.execute(top_players_query)
    top_rows = top_result.all()

    top_players = []
    for row in top_rows:
        gp_result = await db.execute(
            select(GamePlayer).options(selectinload(GamePlayer.player)).where(GamePlayer.id == row.id)
        )
        gp = gp_result.scalar_one_or_none()
        if gp and gp.player:
            top_players.append({
                "name": gp.player.name,
                "role": gp.role,
                "score": row.total_score
            })

    return {
        "game": {
            "id": game.id,
            "name": game.name,
            "status": game.status,
            "created_at": game.created_at.isoformat() if game.created_at else None,
            "started_at": game.started_at.isoformat() if game.started_at else None,
            "finished_at": game.finished_at.isoformat() if game.finished_at else None
        },
        "stats": {
            "total": total_result.scalar() or 0,
            "cats": cats_result.scalar() or 0,
            "mice": mice_result.scalar() or 0,
            "alive": alive_result.scalar() or 0,
            "dead": dead_result.scalar() or 0,
            "captures": captures_result.scalar() or 0
        },
        "top_players": top_players
    }


@router.get("/config")
async def get_game_config(
    payload: dict = Depends(require_staff)
):
    """获取游戏配置"""
    from app.core.config import load_game_config
    return load_game_config()


@router.put("/config")
async def update_game_config(
    config: dict,
    payload: dict = Depends(require_staff)
):
    """更新游戏配置"""
    from app.core.config import save_game_config, load_game_config
    current = load_game_config()
    current.update(config)
    save_game_config(current)
    return {"success": True, "message": "配置已更新", "config": current}


@router.get("/players/{game_player_id}/teammates")
async def get_player_teammates(
    game_player_id: int,
    payload: dict = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    """获取玩家的队友列表"""
    result = await db.execute(
        select(GamePlayer)
        .options(selectinload(GamePlayer.player))
        .where(GamePlayer.id == game_player_id)
    )
    gp = result.scalar_one_or_none()
    if gp is None:
        raise HTTPException(status_code=404, detail="未找到该玩家")

    if gp.team_id is None:
        return {"player": gp.player.name if gp.player else "未知", "team": None, "teammates": []}

    # Get team
    team_result = await db.execute(select(Team).where(Team.id == gp.team_id))
    team = team_result.scalar_one_or_none()

    # Get all teammates
    teammates_result = await db.execute(
        select(GamePlayer)
        .options(selectinload(GamePlayer.player))
        .where(GamePlayer.team_id == gp.team_id)
    )
    teammates = teammates_result.scalars().all()

    teammate_list = []
    for t in teammates:
        score = await score_service.get_player_total_score(db, t.id)
        teammate_list.append({
            "id": t.id,
            "name": t.player.name if t.player else "未知",
            "student_id": t.player.student_id if t.player else "",
            "role": t.role,
            "status": t.status,
            "score": score,
            "is_self": t.id == game_player_id
        })

    return {
        "player": gp.player.name if gp.player else "未知",
        "team": team.name if team else "未知",
        "teammates": teammate_list
    }
