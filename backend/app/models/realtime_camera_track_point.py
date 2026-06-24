from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database.base import Base


class RealtimeCameraTrackPoint(Base):
    __tablename__ = "realtime_camera_track_points"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    point_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    stream_session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    camera_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    track_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    tracked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    position_x: Mapped[float] = mapped_column(Float, nullable=False)
    position_y: Mapped[float] = mapped_column(Float, nullable=False)
    active_roi_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("point_key", name="uq_realtime_camera_track_points_point_key"),
        Index(
            "ix_realtime_camera_track_points_session_track_time",
            "stream_session_id",
            "track_id",
            "tracked_at",
        ),
    )
