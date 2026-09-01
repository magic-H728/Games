from typing import Optional, List
from datetime import datetime
from sqlalchemy import String, DateTime, Integer, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class ScoreType:
    CAPTURE = "CAPTURE"        # Cat captures mouse
    MINIGAME = "MINIGAME"      # Mini-game top 3 reward
    SURVIVAL = "SURVIVAL"      # Mouse survival time
    MANUAL = "MANUAL"          # Staff manual adjustment


class ScoreTransaction(Base):
    __tablename__ = "score_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False)
    game_player_id: Mapped[int] = mapped_column(ForeignKey("game_players.id"), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # ScoreType
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional references
    related_player_id: Mapped[Optional[int]] = mapped_column(ForeignKey("game_players.id"), nullable=True)
    related_attempt_id: Mapped[Optional[int]] = mapped_column(ForeignKey("mini_game_attempts.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    game: Mapped["Game"] = relationship(back_populates="score_transactions")
    game_player: Mapped["GamePlayer"] = relationship(back_populates="score_transactions", foreign_keys=[game_player_id])


from app.models.game import Game
from app.models.player import GamePlayer
