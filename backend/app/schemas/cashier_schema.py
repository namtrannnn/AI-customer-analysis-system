import re

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime

class CustomerInfo(BaseModel):
    id: int
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None

class CustomerSummary(BaseModel):
    id: int
    customer_code: Optional[str] = None 
    full_name: Optional[str] = None
    phone: Optional[str] = None

class ProfileInfo(BaseModel):
    id: int
    anonymous_code: str
    person_type: str
    face_image_url: Optional[str] = None

class ActiveSessionResponse(BaseModel):
    session_id: int
    entry_time: datetime
    profile: ProfileInfo
    customer: Optional[CustomerInfo] = None

class ActiveSessionListResponse(BaseModel):
    total: int
    items: List[ActiveSessionResponse]

class InStoreVisitorResponse(BaseModel):
    session_id: int
    entry_time: datetime
    profile_id: int
    anonymous_code: str
    person_type: str
    face_image_url: Optional[str] = None
    customer: Optional[CustomerSummary] = None

class LinkProfileCustomerRequest(BaseModel):
    person_profile_id: int
    customer_id: int
    ai_session_code: Optional[str] = None

class CreateOrderRequest(BaseModel):
    customer_id: Optional[int] = None
    person_profile_id: Optional[int] = None
    total_amount: float = Field(..., ge=0, description="Tổng tiền đơn hàng")
    item_summary: Optional[str] = None
    payment_method: str = Field(..., description="cash, card, transfer, e_wallet")
    order_time: Optional[datetime] = None
    ai_session_code: Optional[str] = None

class OrderResponse(BaseModel):
    id: int
    order_code: str
    total_amount: float
    created_at: datetime

class CustomerCreate(BaseModel):
    full_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    person_profile_id: Optional[int] = None
    ai_session_code: Optional[str] = None  # Bổ sung mã Live
    gender: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v == "": # Xử lý chuỗi rỗng thành None
            return None
        if v is not None:
            pattern = r"^(0|\+84)[35789][0-9]{8}$"
            if not re.match(pattern, v):
                raise ValueError("Số điện thoại không đúng định dạng Việt Nam.")
        return v
        
    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: str | None) -> str | None:
        if v and v not in ["male", "female", "other"]:
            raise ValueError("Giới tính chỉ được phép là 'male', 'female', hoặc 'other'.")
        return v