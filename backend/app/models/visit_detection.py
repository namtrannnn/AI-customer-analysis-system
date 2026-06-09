from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class VisitDetection(Base):
    __tablename__ = "visit_detections"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    visit_session_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("visit_sessions.id", ondelete="CASCADE"), nullable=True)
    person_profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person_profiles.id", ondelete="CASCADE"), nullable=False)
    camera_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True)
    video_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("videos.id", ondelete="SET NULL"), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    bbox_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_width: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_height: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)