from datetime import datetime
from sqlalchemy import BigInteger, String, Text, DateTime, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database.base import Base

class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    
    camera_name: Mapped[str] = mapped_column(String(100), nullable=False)
    camera_position: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    rtsp_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    mode: Mapped[str] = mapped_column(String(30), nullable=False, default="anonymous")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "mode IN ('anonymous', 'identified')",
            name="chk_camera_mode",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive', 'maintenance', 'error')",
            name="chk_camera_status",
        ),
    )