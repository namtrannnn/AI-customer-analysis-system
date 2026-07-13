# Schema và DTO cho phần Báo cáo Thời gian lưu trú (PB05)
# Thêm comment chi tiết bằng tiếng Việt để dễ đọc và bảo trì.

from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class VisitDurationDetail(BaseModel):
    """
    Thông tin chi tiết một lượt ghé thăm và thời lượng ở lại của khách hàng
    """
    id: int
    anonymous_id: str
    customer_name: Optional[str] = None
    customer_avatar: Optional[str] = None
    entry_time: datetime
    exit_time: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    is_identified: bool

class DurationTrendItem(BaseModel):
    """
    Điểm dữ liệu xu hướng thời gian lưu trú trung bình của một ngày
    """
    date: str                  # Định dạng YYYY-MM-DD
    avg_duration_seconds: float # Thời gian lưu trú trung bình (giây)
    visit_count: int           # Số lượng lượt ghé thăm trong ngày

class DurationStatsResponse(BaseModel):
    """
    Báo cáo tổng hợp số liệu và xu hướng thời gian lưu trú
    """
    avg_duration_seconds: float
    total_visits: int
    max_duration_seconds: int
    trend: List[DurationTrendItem]

class DistributionBucket(BaseModel):
    """
    Khoảng thời lượng lưu trú dùng để vẽ biểu đồ phân bố (Histogram)
    """
    bucket_name: str           # Ví dụ: "Dưới 1 phút", "1 - 5 phút", ...
    visit_count: int           # Số lượt khách rơi vào khoảng thời gian này
