from pydantic import BaseModel, Field, model_validator
from typing import Optional
from datetime import datetime, timezone

class VisitSessionCreate(BaseModel):
    # Field(..., gt=0) bắt buộc ID phải là số nguyên dương
    person_profile_id: int = Field(..., gt=0, description="ID của Profile Khách hàng")
    
    # Do hệ thống không lưu video vào DB, ta dùng chuỗi để đánh dấu nguồn (tên video hoặc ID luồng camera)
    source_identifier: str = Field(..., min_length=1, description="Tên file video tạm hoặc ID camera")
    
    # Tự động lấy giờ UTC hiện tại nếu không truyền vào
    enter_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class VisitSessionUpdate(BaseModel):
    exit_time: datetime

class VisitSessionResponse(VisitSessionCreate):
    id: int
    exit_time: Optional[datetime] = None
    duration_seconds: Optional[int] = None # Tính toán thời gian khách ở lại (PB05)

    model_config = {"from_attributes": True}