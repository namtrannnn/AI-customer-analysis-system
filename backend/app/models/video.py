from datetime import datetime
from sqlalchemy import BigInteger, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database.base import Base

class Video(Base):
    __tablename__ = "videos"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    video_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    video_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, default="upload")
    start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    processing_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)