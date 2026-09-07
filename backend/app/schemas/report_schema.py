from pydantic import BaseModel, root_validator
from datetime import date
from typing import List

class DailyReportData(BaseModel):
    statistic_date: date
    total_visitors: int
    new_visitors: int
    returning_visitors: int
    avg_duration_seconds: int
    total_orders: int
    total_revenue: float

class ReportSummary(BaseModel):
    total_visitors: int = 0
    new_visitors: int = 0
    returning_visitors: int = 0
    avg_duration_seconds: int = 0
    total_orders: int = 0
    total_revenue: float = 0.0

class ReportDataDTO(BaseModel):
    start_date: date
    end_date: date
    summary: ReportSummary
    daily_stats: List[DailyReportData]

class ReportFilter(BaseModel):
    start_date: date
    end_date: date

    @root_validator(pre=True)
    def check_dates(cls, values):
        start = values.get('start_date')
        end = values.get('end_date')
        if start and end and start > end:
            raise ValueError("Ngày bắt đầu không được lớn hơn ngày kết thúc")
        return values