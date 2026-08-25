# Schema & DTO cho phần Thống kê khách theo ngày (PB06)

from pydantic import BaseModel
from datetime import date
from typing import List, Optional


class DailyStatisticResponse(BaseModel):
    """
    Thông tin chi tiết một hàng dữ liệu thống kê ngày
    """
    id: int
    statistic_date: date
    total_visitors: int
    new_visitors: int
    returning_visitors: int
    identified_visitors: int
    avg_duration_seconds: int
    total_orders: int
    total_revenue: float
    conversion_rate: float


class DailyTrendItem(BaseModel):
    """
    Một điểm dữ liệu trên biểu đồ xu hướng
    """
    date: str                    # Định dạng YYYY-MM-DD hoặc "2026-W28" hoặc "2026-07"
    total_visitors: int
    new_visitors: int
    returning_visitors: int
    avg_duration_seconds: int


class DailyStatisticsSummary(BaseModel):
    """
    Tổng hợp KPIs + Dữ liệu biểu đồ xu hướng
    """
    # KPI Cards
    total_visitors: int          # Tổng khách trong khoảng thời gian
    new_visitors: int            # Tổng khách mới
    returning_visitors: int      # Tổng khách quay lại
    avg_duration_seconds: int    # Thời gian ở lại trung bình (giây)
    total_orders: int            # Tổng đơn hàng
    total_revenue: float         # Tổng doanh thu
    avg_conversion_rate: float   # Tỷ lệ chuyển đổi trung bình (%)

    # Dữ liệu biểu đồ
    trend: List[DailyTrendItem]


class SyncStatsRequest(BaseModel):
    """
    Yêu cầu đồng bộ/tính toán lại dữ liệu thống kê cho một khoảng ngày
    """
    start_date: date
    end_date: date
