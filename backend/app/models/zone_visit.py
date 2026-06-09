from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class ZoneVisit(Base):
    __tablename__ = "zone_visits"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    visit_session_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("visit_sessions.id", ondelete="CASCADE"), nullable=False)
    person_profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person_profiles.id", ondelete="CASCADE"), nullable=False)
    zone_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("store_zones.id", ondelete="CASCADE"), nullable=False)
    enter_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    leave_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)