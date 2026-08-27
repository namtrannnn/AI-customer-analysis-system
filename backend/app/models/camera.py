from datetime import datetime
from sqlalchemy import BigInteger, Integer, String, Text, DateTime, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database.base import Base

class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)

    # ── Thông tin hiển thị ────────────────────────────────────────────────────
    camera_name: Mapped[str] = mapped_column(String(100), nullable=False)
    camera_position: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ── Thông tin đầu ghi NVR ────────────────────────────────────────────────
    nvr_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    nvr_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    channel_no: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Kết nối stream ───────────────────────────────────────────────────────
    # rtsp_url: URL AI-stream chính — KHÔNG trả nguyên văn ra FE
    rtsp_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # preview_url: sub-stream chất lượng thấp hơn dùng cho FE preview (nếu có)
    preview_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # transport: giao thức kéo RTSP — tcp ổn định hơn, udp latency thấp hơn
    transport: Mapped[str] = mapped_column(String(10), nullable=False, default="tcp")

    # ── Chế độ & trạng thái cấu hình ─────────────────────────────────────────
    mode: Mapped[str] = mapped_column(String(30), nullable=False, default="anonymous")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")

    # ── Trạng thái kết nối runtime ───────────────────────────────────────────
    last_connection_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    last_connected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Audit ────────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "mode IN ('anonymous', 'identified')",
            name="chk_camera_mode",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive', 'maintenance', 'error')",
            name="chk_camera_status",
        ),
        CheckConstraint(
            "transport IN ('tcp', 'udp')",
            name="chk_camera_transport",
        ),
        CheckConstraint(
            "last_connection_status IN ('online', 'offline', 'reconnecting', 'error') "
            "OR last_connection_status IS NULL",
            name="chk_camera_connection_status",
        ),
    )
