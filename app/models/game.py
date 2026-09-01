from typing import Optional, List
from datetime import datetime
from sqlalchemy import String, DateTime, Integer, Float, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class GameStatus:
    PENDING = "PENDING"
    READY = "READY"
    ROLE_ASSIGNED = "ROLE_ASSIGNED"
    TEAM_ASSIGNED = "TEAM_ASSIGNED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    FINISHING = "FINISHING"
    FINISHED = "FINISHED"


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default=GameStatus.PENDING, nullable=False)

    # Game config
    cat_ratio: Mapped[float] = mapped_column(Float, default=0.1)  # 10%
    cat_count: Mapped[int] = mapped_column(Integer, default=0)  # 0 = auto calculate
    cat_team_count: Mapped[int] = mapped_column(Integer, default=5)
    mouse_team_count: Mapped[int] = mapped_column(Integer, default=10)

    # Capture config
    capture_score: Mapped[int] = mapped_column(Integer, default=10)
    allow_repeat_capture: Mapped[bool] = mapped_column(Boolean, default=False)

    # Survival config
    survival_interval_seconds: Mapped[int] = mapped_column(Integer, default=300)  # 5 min
    survival_interval_score: Mapped[int] = mapped_column(Integer, default=5)

    # Revival config
    allow_revive: Mapped[bool] = mapped_column(Boolean, default=True)
    max_revive_count: Mapped[int] = mapped_column(Integer, default=3)
    revive_protect_seconds: Mapped[int] = mapped_column(Integer, default=120)  # 2 min

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    players: Mapped[list["GamePlayer"]] = relationship(back_populates="game", cascade="all, delete-orphan")
    teams: Mapped[list["Team"]] = relationship(back_populates="game", cascade="all, delete-orphan")
    mini_games: Mapped[list["MiniGame"]] = relationship(back_populates="game", cascade="all, delete-orphan")
    score_transactions: Mapped[list["ScoreTransaction"]] = relationship(back_populates="game", cascade="all, delete-orphan")


# Import here to avoid circular imports
from app.models.player import GamePlayer
from app.models.team import Team
from app.models.mini_game import MiniGame
from app.models.score import ScoreTransaction
