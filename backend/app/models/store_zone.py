from datetime import datetime
from sqlalchemy import BigInteger, String, Text, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database.base import Base


class StoreZone(Base):
    __tablename__ = "store_zones"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    zone_name: Mapped[str] = mapped_column(String(100), nullable=False)
    zone_type: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Polygon points dạng JSON: [{"x": 0.1, "y": 0.2}, ...]
    # Lưu tọa độ tương đối (0..1) so với kích thước ảnh nền
    polygon: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)

    # Màu hiển thị trên FE (hex string, e.g. "#3b82f6")
    color: Mapped[str] = mapped_column(String(20), nullable=False, default="#3b82f6")

    # Thống kê tổng hợp (cập nhật khi có ZoneVisit mới)
    total_visits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(nullable=True, onupdate=func.now())
