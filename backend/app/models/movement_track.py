from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class MovementTrack(Base):
    __tablename__ = "movement_tracks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)

    visit_session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("visit_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    person_profile_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("person_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    zone_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("store_zones.id", ondelete="SET NULL"),
        nullable=True,
    )
    position_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    position_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    tracked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
