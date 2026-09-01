from typing import Optional, List
from datetime import datetime
from sqlalchemy import String, DateTime, Integer, Boolean, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class MiniGame(Base):
    """Configurable mini-game for revival challenges."""
    __tablename__ = "mini_games"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    game_type: Mapped[str] = mapped_column(String(50), default="OTHER")  # QUIZ / REACTION / OTHER

    # Scoring config
    is_scored: Mapped[bool] = mapped_column(Boolean, default=False)
    pass_score: Mapped[int] = mapped_column(Integer, default=60)  # minimum score to pass

    # Top 3 rewards
    reward_first: Mapped[int] = mapped_column(Integer, default=30)
    reward_second: Mapped[int] = mapped_column(Integer, default=20)
    reward_third: Mapped[int] = mapped_column(Integer, default=10)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    game: Mapped["Game"] = relationship(back_populates="mini_games")
    attempts: Mapped[list["MiniGameAttempt"]] = relationship(back_populates="mini_game", cascade="all, delete-orphan")


class MiniGameAttempt(Base):
    """A player's attempt at a mini-game."""
    __tablename__ = "mini_game_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    mini_game_id: Mapped[int] = mapped_column(ForeignKey("mini_games.id"), nullable=False)
    game_player_id: Mapped[int] = mapped_column(ForeignKey("game_players.id"), nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    rewarded: Mapped[bool] = mapped_column(Boolean, default=False)  # whether top-3 reward was given
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    mini_game: Mapped["MiniGame"] = relationship(back_populates="attempts")
    game_player: Mapped["GamePlayer"] = relationship(back_populates="mini_game_attempts")


from app.models.game import Game
from app.models.player import GamePlayer
