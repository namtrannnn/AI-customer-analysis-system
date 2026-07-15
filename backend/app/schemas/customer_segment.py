from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class CustomerInfo(BaseModel):
    id: int
    full_name: str
    phone: Optional[str] = None
    email: Optional[str] = None

    class Config:
        from_attributes = True

class CustomerSegmentBase(BaseModel):
    segment_name: str = Field(..., max_length=100, description="Tên nhóm khách hàng")
    description: Optional[str] = Field(None, description="Mô tả nhóm")
    rule_definition: Optional[Dict[str, Any]] = Field(None, description="Điều kiện phân nhóm (JSON)")

class CustomerSegmentCreate(CustomerSegmentBase):
    pass

class CustomerSegmentResponse(CustomerSegmentBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class CustomerSegmentMemberBase(BaseModel):
    segment_id: int
    person_profile_id: int
    customer_id: Optional[int] = None
    score: Optional[float] = Field(None, description="Điểm phù hợp của khách hàng với cụm")

class CustomerSegmentMemberCreate(CustomerSegmentMemberBase):
    pass

class CustomerSegmentMemberResponse(CustomerSegmentMemberBase):
    id: int
    assigned_at: datetime
   
    customer: Optional[CustomerInfo] = None

    class Config:
        from_attributes = True