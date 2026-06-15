from datetime import datetime
from sqlalchemy import (
    BigInteger, 
    DateTime, 
    ForeignKey
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database.base import Base


class UserRole(Base):
    __tablename__ = "user_roles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(
        BigInteger, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )

    role_id: Mapped[int] = mapped_column(
        BigInteger, 
        ForeignKey("roles.id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )

    assigned_at: Mapped[datetime] = mapped_column(
        DateTime, 
        nullable=False, 
        server_default=func.now()
    )