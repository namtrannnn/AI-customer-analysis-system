from sqlalchemy import (
    BigInteger,
    String,
    Text,
    DateTime,
    Integer,
    Numeric,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database.base import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)

    customer_code: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )

    full_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String(20),
        unique=True,
        nullable=True,
        index=True,
    )

    email: Mapped[str | None] = mapped_column(
        String(100), 
        unique=True, 
        nullable=True
    )

    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)

    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
        index=True,
    )

    total_visits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    total_orders: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    total_spent: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )

    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[DateTime | None] = mapped_column(
        DateTime, 
        onupdate=func.now(), 
        nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive', 'deleted')",
            name="chk_customer_status",
        ),
        CheckConstraint(
            "gender IS NULL OR gender IN ('male', 'female', 'other')",
            name="chk_customer_gender",
        ),
        CheckConstraint(
            "total_visits >= 0",
            name="chk_customer_total_visits",
        ),
        CheckConstraint(
            "total_orders >= 0",
            name="chk_customer_total_orders",
        ),
        CheckConstraint(
            "total_spent >= 0",
            name="chk_customer_total_spent",
        ),
    )
