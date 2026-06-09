from datetime import datetime
from sqlalchemy import BigInteger, String, Text, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database.base import Base

class CustomerSegment(Base):
    __tablename__ = "customer_segments"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    segment_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_definition: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())