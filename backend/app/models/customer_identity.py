from datetime import datetime
from sqlalchemy import (
    BigInteger,
    String,
    Text,
    DateTime,
    Float,
    ForeignKey,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database.base import Base

class CustomerIdentity(Base):
    __tablename__ = "customer_identities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    
    # Khóa ngoại liên kết với bảng person_profiles
    person_profile_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("person_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Khóa ngoại liên kết với bảng customers
    customer_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    identification_method: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    identified_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
            name="chk_identity_confidence_score",
        ),
    )