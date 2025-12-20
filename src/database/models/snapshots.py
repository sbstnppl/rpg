"""Session snapshot models for state restoration."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base


class SessionSnapshot(Base):
    """Complete state snapshot for a game session at a specific turn.

    Captures the full state of all session-scoped tables at the start of a turn,
    enabling exact restoration for debugging or rollback.

    Attributes:
        id: Primary key.
        session_id: Foreign key to the game session.
        turn_number: Turn number this snapshot was captured at.
        snapshot_data: JSON containing complete session state.
        created_at: When the snapshot was captured.
    """

    __tablename__ = "session_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    turn_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    snapshot_data: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="Complete session state as JSON",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationship
    session = relationship("GameSession", back_populates="snapshots")

    __table_args__ = (
        Index("ix_session_snapshots_session_turn", "session_id", "turn_number", unique=True),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<SessionSnapshot session={self.session_id} turn={self.turn_number}>"
