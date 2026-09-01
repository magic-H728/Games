from typing import Optional, List
from datetime import datetime
from sqlalchemy import String, DateTime, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class TeamRole:
    CAT = "CAT"
    MOUSE = "MOUSE"


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # CAT or MOUSE team
    team_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1, 2, 3...
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    game: Mapped["Game"] = relationship(back_populates="teams")
    members: Mapped[list["GamePlayer"]] = relationship(back_populates="team", foreign_keys="GamePlayer.team_id")


from app.models.game import Game
from app.models.player import GamePlayer
