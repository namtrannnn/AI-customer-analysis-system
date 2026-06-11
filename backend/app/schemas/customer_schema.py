from datetime import datetime
from decimal import Decimal
import re
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# Schema nhận dữ liệu khi camera tạo khách ẩn danh
class AnonymousCreate(BaseModel):
    confidence_avg: float | None = Field(default=None, ge=0.0, le=1.0, description="Độ tin cậy trung bình của khuôn mặt")

# Schema trả về thông tin hồ sơ camera
class PersonProfileResponse(BaseModel):
    id: int
    anonymous_code: str
    person_type: str
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    total_visits: int
    confidence_avg: float | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CustomerBase(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    gender: str | None = None
    avatar_url: str | None = None
    note: str | None = None

    # CUS-API-11: Validate
    # Validate Giới tính
    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: str | None) -> str | None:
        # Nếu có giá trị truyền vào thì phải nằm trong 3 loại
        if v and v not in ["male", "female", "other"]:
            raise ValueError("Giới tính chỉ được phép là 'male', 'female', hoặc 'other'.")
        return v

    # Validate Số điện thoại
    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v == "": # Xử lý trường hợp frontend gửi chuỗi rỗng
            return None
        if v is not None:
            # Đã sửa lại lỗi dấu | bên trong ngoặc vuông
            pattern = r"^(0|\+84)[35789][0-9]{8}$"
            if not re.match(pattern, v):
                raise ValueError("Số điện thoại không đúng định dạng Việt Nam.")
        return v

# Schema cho CUS-API-10 (Lịch sử đơn hàng)
class OrderHistoryResponse(BaseModel):
    id: int
    order_code: str
    total_amount: Decimal
    order_time: datetime
    
    model_config = ConfigDict(from_attributes=True)

# Schema cho CUS-API-09 (Lịch sử ghé thăm)
class VisitHistoryResponse(BaseModel):
    id: int
    entry_time: datetime
    exit_time: datetime | None
    duration_seconds: int | None
    is_identified: bool
    
    model_config = ConfigDict(from_attributes=True)

class CustomerCreate(CustomerBase):
    # Validate bằng tham số gt=0 (greater than 0) của Pydantic
    person_profile_id: int | None = Field(default=None, gt=0, description="ID khuôn mặt từ camera")
    
    # URL ảnh khuôn mặt cắt từ camera để dùng làm avatar nếu có
    captured_avatar_url: str | None = None

class CustomerUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    gender: str | None = None
    avatar_url: str | None = None
    note: str | None = None
    status: str | None = None

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

class CustomerResponse(CustomerBase):
    id: int
    customer_code: str
    status: str
    total_visits: int
    total_orders: int
    total_spent: Decimal
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
