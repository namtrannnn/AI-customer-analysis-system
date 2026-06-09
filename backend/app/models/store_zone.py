from sqlalchemy import BigInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class StoreZone(Base):
    __tablename__ = "store_zones"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    zone_name: Mapped[str] = mapped_column(String(100), nullable=False)
    zone_type: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)