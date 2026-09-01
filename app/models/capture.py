from typing import Optional, List
from datetime import datetime
from sqlalchemy import DateTime, Integer, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class CaptureRecord(Base):
    __tablename__ = "capture_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False)
    cat_id: Mapped[int] = mapped_column(ForeignKey("game_players.id"), nullable=False)
    mouse_id: Mapped[int] = mapped_column(ForeignKey("game_players.id"), nullable=False)
    survival_round: Mapped[int] = mapped_column(Integer, nullable=False)  # which life of the mouse
    score_awarded: Mapped[int] = mapped_column(Integer, default=0)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    cat: Mapped["GamePlayer"] = relationship(back_populates="capture_records_as_cat", foreign_keys=[cat_id])
    mouse: Mapped["GamePlayer"] = relationship(back_populates="capture_records_as_mouse", foreign_keys=[mouse_id])


from app.models.player import GamePlayer
