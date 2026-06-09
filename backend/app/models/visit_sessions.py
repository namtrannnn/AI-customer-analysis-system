from datetime import datetime
from sqlalchemy import (
    BigInteger,
    DateTime,
    Integer,
    Boolean,
    ForeignKey,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database.base import Base

class VisitSession(Base):
    __tablename__ = "visit_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    
    # Khóa ngoại liên kết với bảng person_profiles
    person_profile_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("person_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    entry_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    exit_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_identified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="chk_visit_duration_seconds",
        ),
    )