from datetime import datetime
from sqlalchemy import (
    BigInteger,
    String,
    Text,
    DateTime,
    Numeric,
    ForeignKey,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database.base import Base

class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    
    # Khóa ngoại liên kết với bảng customers, cho phép NULL nếu khách chưa định danh
    customer_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    # Khóa ngoại liên kết với bảng person_profiles
    person_profile_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("person_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    order_code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    
    total_amount: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )
    
    item_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    order_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "total_amount >= 0",
            name="chk_order_total_amount",
        ),
    )