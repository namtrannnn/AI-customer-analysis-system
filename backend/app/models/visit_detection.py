from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

# Import referenced models so their tables are registered in Base.metadata
# before SQLAlchemy resolves this model's foreign keys.
from app.models.camera import Camera  # noqa: F401
from app.models.person_profile import PersonProfile  # noqa: F401
from app.models.video import Video  # noqa: F401
from app.models.visit_sessions import VisitSession  # noqa: F401

class VisitDetection(Base):
    __tablename__ = "visit_detections"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    
    visit_session_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("visit_sessions.id", ondelete="CASCADE"), nullable=True)
    person_profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person_profiles.id", ondelete="CASCADE"), nullable=False)
    camera_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True)
    video_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("videos.id", ondelete="SET NULL"), nullable=True)
    
    bbox_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_width: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_height: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    detected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "bbox_width >= 0",
            name="chk_bbox_width",
        ),
        CheckConstraint(
            "bbox_height >= 0",
            name="chk_bbox_height",
        ),
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1", 
            name="chk_detection_confidence_score",
        ),
    )
