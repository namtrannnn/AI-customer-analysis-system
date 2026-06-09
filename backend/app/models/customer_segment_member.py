from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database.base import Base

class CustomerSegmentMember(Base):
    __tablename__ = "customer_segment_members"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    segment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("customer_segments.id", ondelete="CASCADE"), nullable=False)
    person_profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person_profiles.id", ondelete="CASCADE"), nullable=False)
    customer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    score: Mapped[float | None] = mapped_column(Float, nullable=True)