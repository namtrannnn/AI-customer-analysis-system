from datetime import datetime
from sqlalchemy import BigInteger, String, DateTime, Integer, Float, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database.base import Base

class PersonProfile(Base):
    __tablename__ = "person_profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    
    anonymous_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    person_type: Mapped[str] = mapped_column(String(30), nullable=False, default="anonymous")
    
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    total_visits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "person_type IN ('anonymous', 'identified')",
            name="chk_person_type",
        ),
        CheckConstraint(
            "total_visits >= 0",
            name="chk_person_total_visits",
        ),
    )