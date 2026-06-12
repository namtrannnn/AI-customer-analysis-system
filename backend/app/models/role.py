from datetime import datetime
from sqlalchemy import (
    BigInteger, 
    String, 
    Text, 
    DateTime
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database.base import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)

    role_code: Mapped[str] = mapped_column(
        String(50), 
        unique=True, 
        nullable=False,
        index=True,
    )

    role_name: Mapped[str] = mapped_column(
        String(100), 
        nullable=False
    )

    description: Mapped[str | None] = mapped_column(
        Text, 
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        nullable=False, 
        server_default=func.now()
    )
