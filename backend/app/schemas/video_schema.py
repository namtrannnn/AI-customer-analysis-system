from pydantic import BaseModel
from typing import List

# Lớp mô tả thông tin chi tiết của từng khách hàng phát hiện được trong video (FE-07)
class DetectedCustomer(BaseModel):
    anonymous_id: str
    customer_type: str  # "new" hoặc "returning"
    confidence: float
    customer_id: int | None = None
    customer_name: str | None = None
    customer_avatar: str | None = None

# Lớp mô tả cấu trúc trả về sau khi phân tích xong video (FE-06)
class VideoAnalysisResponse(BaseModel):
    total_customers: int
    new_customers: int
    returning_customers: int
    detected_customers: List[DetectedCustomer]
    message: str