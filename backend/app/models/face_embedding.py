from datetime import datetime
from sqlalchemy import (
    BigInteger,
    Text,
    DateTime,
    Float,
    ForeignKey,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database.base import Base
# from pgvector.sqlalchemy import Vector

class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    
    person_profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person_profiles.id", ondelete="CASCADE"), nullable=False)
    camera_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True)
    
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # embedding: Mapped[str | None] = mapped_column(Text, nullable=True) 
    # embedding: Mapped[list[float] | None] = mapped_column(Vector(512), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(
        ARRAY(Float),
        nullable=True,
    )
    
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "quality_score >= 0",
            name="chk_face_quality_score",
        ),
    )