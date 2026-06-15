from datetime import datetime
from sqlalchemy import (
    BigInteger,
    String,
    Text,
    DateTime,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)

    full_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True, 
    )

    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    email: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String(20),
        unique=True,
        nullable=True,
        index=True,
    )

    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    password_hash: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
        index=True,  
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime, 
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        onupdate=func.now(),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive', 'deleted')",
            name="chk_user_status",
        ),
    )