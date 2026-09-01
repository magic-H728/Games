from typing import Optional, List
import secrets
from datetime import datetime
from sqlalchemy import String, DateTime, Integer, Boolean, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class PlayerRole:
    CAT = "CAT"
    MOUSE = "MOUSE"


class GamePlayerStatus:
    WAITING = "WAITING"
    ALIVE = "ALIVE"
    DEAD = "DEAD"
    PROTECTED = "PROTECTED"
    OFFLINE = "OFFLINE"


class Player(Base):
    """Long-term player identity, persists across games."""
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    student_id: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    wechat_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    game_players: Mapped[list["GamePlayer"]] = relationship(back_populates="player")


class GamePlayer(Base):
    """Player's identity within a specific game."""
    __tablename__ = "game_players"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)

    # QR token for scanning - unique per game player
    qr_token: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, default=lambda: f"HNS-{secrets.token_hex(6).upper()}")

    # Role & status
    role: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # CAT / MOUSE / None
    status: Mapped[str] = mapped_column(String(30), default=GamePlayerStatus.WAITING, nullable=False)
    is_online: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Team
    team_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teams.id"), nullable=True)

    # Survival
    survival_round: Mapped[int] = mapped_column(Integer, default=0)  # increments on each revive
    total_survival_seconds: Mapped[float] = mapped_column(default=0.0)
    revive_count: Mapped[int] = mapped_column(Integer, default=0)

    # Revival protection
    protect_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Pre-assigned as cat before role assignment
    pre_assigned_cat: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    role_assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    died_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    game: Mapped["Game"] = relationship(back_populates="players")
    player: Mapped["Player"] = relationship(back_populates="game_players")
    team: Mapped[Optional["Team"]] = relationship(back_populates="members", foreign_keys=[team_id])
    survival_records: Mapped[list["SurvivalRecord"]] = relationship(back_populates="game_player", cascade="all, delete-orphan")
    capture_records_as_cat: Mapped[list["CaptureRecord"]] = relationship(
        back_populates="cat", foreign_keys="CaptureRecord.cat_id", cascade="all, delete-orphan"
    )
    capture_records_as_mouse: Mapped[list["CaptureRecord"]] = relationship(
        back_populates="mouse", foreign_keys="CaptureRecord.mouse_id", cascade="all, delete-orphan"
    )
    mini_game_attempts: Mapped[list["MiniGameAttempt"]] = relationship(back_populates="game_player", cascade="all, delete-orphan")
    score_transactions: Mapped[list["ScoreTransaction"]] = relationship(
        back_populates="game_player", foreign_keys="ScoreTransaction.game_player_id", cascade="all, delete-orphan"
    )


from app.models.game import Game
from app.models.team import Team
from app.models.survival import SurvivalRecord
from app.models.capture import CaptureRecord
from app.models.mini_game import MiniGameAttempt
from app.models.score import ScoreTransaction
