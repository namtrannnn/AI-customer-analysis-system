from datetime import datetime, date
from sqlalchemy import BigInteger, DateTime, Date, Float, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database.base import Base

class DailyStatistic(Base):
    __tablename__ = "daily_statistics"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    statistic_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    total_visitors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_visitors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    returning_visitors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    identified_visitors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_orders: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_revenue: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    conversion_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())