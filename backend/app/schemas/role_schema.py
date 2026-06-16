from datetime import datetime
import re
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

class RoleCreate(BaseModel):
    role_code: str = Field(..., min_length=2, max_length=50, description="Mã nhóm quyền (VD: admin, hr_manager)")
    role_name: str = Field(..., min_length=2, max_length=100, description="Tên nhóm quyền hiển thị")
    description: Optional[str] = None
    
    # Mảng chứa danh sách ID các quyền được chọn từ giao diện
    permission_ids: List[int] = Field(default_factory=list, description="Danh sách ID quyền được cấp")

    @field_validator("role_code")
    @classmethod
    def validate_role_code(cls, v: str) -> str:
        clean_code = v.strip().lower()
        # Ép buộc mã role chỉ chứa chữ cái tiếng Anh, số và dấu gạch dưới
        if not re.match(r"^[a-z0-9_]+$", clean_code):
            raise ValueError("Mã nhóm quyền chỉ được chứa chữ cái không dấu, số và dấu gạch dưới (_).")
        return clean_code
    
class RoleUpdate(BaseModel):
    role_code: str | None = Field(default=None, min_length=2, max_length=50)
    role_name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = None
    permission_ids: list[int] | None = Field(default=None, description="Danh sách ID quyền cập nhật")

    # Validate dữ liệu nhóm quyền
    @field_validator("role_code")
    @classmethod
    def validate_role_code(cls, v: str | None) -> str | None:
        if v is None: return v
        clean_code = v.strip().lower()
        if not re.match(r"^[a-z0-9_]+$", clean_code):
            raise ValueError("Mã nhóm quyền chỉ được chứa chữ cái không dấu, số và dấu gạch dưới (_).")
        return clean_code

# CUS-API-31: Chuẩn hóa Response trả về cho Frontend
class RoleResponse(BaseModel):
    id: int
    role_code: str
    role_name: str
    description: str | None
    permission_ids: list[int] = [] 
    created_at: datetime
    user_count: int = 0

    model_config = {"from_attributes": True}

# Định nghĩa thông tin thu nhỏ của nhân viên thuộc nhóm quyền
class UserMinInfo(BaseModel):
    id: int
    full_name: str
    username: str
    avatar_url: str | None = None

    model_config = {"from_attributes": True}

# Định nghĩa chi tiết thông tin quyền hạn
class PermissionInfo(BaseModel):
    id: int
    permission_code: str
    permission_name: str
    module_name: str

    model_config = {"from_attributes": True}

# Schema tổng hợp trả về toàn bộ thông tin lồng nhau
class RoleFullDetailResponse(BaseModel):
    id: int
    role_code: str
    role_name: str
    description: str | None
    users: list[UserMinInfo] = []          # Trả về mảng danh sách object user
    permissions: list[PermissionInfo] = []  # Trả về mảng danh sách object chi tiết quyền
    created_at: datetime

    model_config = {"from_attributes": True}