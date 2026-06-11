from datetime import datetime
import re
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# Base: Chỉ chứa những trường Frontend thực sự gửi lên khi tạo mới
class UserCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)
    avatar_url: str | None = None
    # Hứng role_id từ giao diện
    role_ids: list[int] = Field(..., description="Danh sách ID các vai trò")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v == "":
            return None
        if v is not None:
            # Đã sửa lại lỗi dấu | bên trong ngoặc vuông
            pattern = r"^(0|\+84)[35789][0-9]{8}$"
            if not re.match(pattern, v):
                raise ValueError("Số điện thoại không đúng định dạng.")
        return v

# Hứng dữ liệu khi Admin sửa thông tin
class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)
    avatar_url: str | None = None
    status: str | None = Field(default=None, description="Trạng thái người dùng")
    role_ids: list[int] | None = Field(default=None, description="Danh sách ID vai trò mới")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v == "": return None
        if v is not None:
            pattern = r"^(0|\+84)[35789][0-9]{8}$"
            if not re.match(pattern, v):
                raise ValueError("Số điện thoại không đúng định dạng.")
        return v

# Schema trả về cho các API Lấy danh sách, Chi tiết, Cập nhật
class UserResponse(BaseModel):
    id: int
    full_name: str
    username: str
    email: str | None
    phone: str | None
    avatar_url: str | None
    status: str
    role_ids: list[int] = []
    
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

# Schema cho Response dành RIÊNG cho API tạo mới (cho phép lọt mật khẩu)
class UserCreateResponse(BaseModel):
    id: int
    full_name: str
    username: str
    temporary_password: str # Trường để Frontend nhận được mật khẩu