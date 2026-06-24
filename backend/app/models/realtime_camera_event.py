from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database.base import Base


class RealtimeCameraEvent(Base):
    __tablename__ = "realtime_camera_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    event_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    stream_session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    camera_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    track_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    roi_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("event_key", name="uq_realtime_camera_events_event_key"),
        Index(
            "ix_realtime_camera_events_session_time",
            "stream_session_id",
            "event_timestamp",
        ),
    )
