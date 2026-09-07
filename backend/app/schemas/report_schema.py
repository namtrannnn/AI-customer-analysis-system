from pydantic import BaseModel, field_validator, model_validator
from datetime import date
from typing import List, Literal
from enum import Enum


class ReportType(str, Enum):
    summary  = "summary"   # Tổng hợp — gộp tất cả
    activity = "activity"  # Hoạt động — lượt khách, thời gian lưu trú
    customer = "customer"  # Khách hàng — danh sách, phân nhóm
    revenue  = "revenue"   # Doanh thu — đơn hàng, doanh thu


class DailyReportData(BaseModel):
    statistic_date: date
    total_visitors: int
    new_visitors: int
    returning_visitors: int
    avg_duration_seconds: int
    total_orders: int
    total_revenue: float


class CustomerReportData(BaseModel):
    anonymous_code: str
    person_type: str          # anonymous / identified
    customer_name: str | None
    total_visits: int
    avg_duration_seconds: int
    total_spent: float
    segment_name: str | None  # Nhóm AI


class ReportSummary(BaseModel):
    total_visitors: int = 0
    new_visitors: int = 0
    returning_visitors: int = 0
    avg_duration_seconds: int = 0
    total_orders: int = 0
    total_revenue: float = 0.0


class ReportDataDTO(BaseModel):
    report_type: ReportType
    start_date: date
    end_date: date
    summary: ReportSummary
    daily_stats: List[DailyReportData] = []
    customers: List[CustomerReportData] = []  # Chỉ dùng cho loại customer & summary


class ReportFilter(BaseModel):
    start_date: date
    end_date: date
    report_type: ReportType = ReportType.summary

    @model_validator(mode="after")
    def check_dates(self):
        if self.start_date > self.end_date:
            raise ValueError("Ngày bắt đầu không được lớn hơn ngày kết thúc")
        diff = (self.end_date - self.start_date).days
        if diff > 365:
            raise ValueError("Khoảng thời gian không được vượt quá 365 ngày")
        return self
