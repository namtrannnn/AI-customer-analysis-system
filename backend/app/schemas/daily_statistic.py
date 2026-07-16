from pydantic import BaseModel
from datetime import date
from typing import List, Optional

# BE-2: DTO cho Thống kê tổng quan (Cards)
class OverviewStatsResponse(BaseModel):
    total_visits: int
    new_visitors: int
    returning_visitors: int
    avg_duration_seconds: float

# BE-3: DTO cho 1 điểm dữ liệu trên Biểu đồ
class ChartDataPoint(BaseModel):
    label: str  # Ví dụ: "2026-07-14", "Tuần 28", "Tháng 7"
    total_visits: int
    new_visitors: int
    returning_visitors: int

class TrendChartResponse(BaseModel):
    group_by: str
    data: List[ChartDataPoint]