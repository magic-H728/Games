from typing import Optional, List
from datetime import datetime
from sqlalchemy import DateTime, Integer, Float, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class SurvivalRecord(Base):
    """Tracks each survival period for a mouse (one per life)."""
    __tablename__ = "survival_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_player_id: Mapped[int] = mapped_column(ForeignKey("game_players.id"), nullable=False)
    survival_round: Mapped[int] = mapped_column(Integer, nullable=False)  # matches game_player.survival_round
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)

    # Relationships
    game_player: Mapped["GamePlayer"] = relationship(back_populates="survival_records")


from app.models.player import GamePlayer
