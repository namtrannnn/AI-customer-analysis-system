from datetime import datetime
import re

from pydantic import BaseModel, EmailStr, Field, field_validator

class LoginRequest(BaseModel):
    username: str = Field(..., description="Tên đăng nhập")
    password: str = Field(..., description="Mật khẩu")

class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., description="Mật khẩu hiện tại")
    # Đặt độ dài tối thiểu là 8 để tăng cường bảo mật
    new_password: str = Field(..., min_length=8, description="Mật khẩu mới")
    confirm_password: str = Field(..., description="Xác nhận mật khẩu mới")

    # 1. Validate độ mạnh của mật khẩu mới
    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        # Kiểm tra phải có ít nhất 1 chữ cái viết hoa
        if not re.search(r"[A-Z]", v):
            raise ValueError("Mật khẩu mới phải chứa ít nhất 1 chữ cái viết hoa.")
        
        # Kiểm tra phải có ít nhất 1 chữ số
        if not re.search(r"\d", v):
            raise ValueError("Mật khẩu mới phải chứa ít nhất 1 chữ số.")
            
        # Kiểm tra phải có ít nhất 1 ký tự đặc biệt
        if not re.search(r"[@$!%*?&#^_-]", v):
            raise ValueError("Mật khẩu mới phải chứa ít nhất 1 ký tự đặc biệt (VD: @, $, !, %, *, ?, &, #, _, -).")
            
        return v

    # 2. Validate xác nhận mật khẩu (phải chạy sau khi new_password đã pass)
    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info):
        # info.data chứa các trường đã được validate thành công trước đó
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("Mật khẩu xác nhận không khớp với mật khẩu mới.")
        return v
   
# CÁC SCHEMA DÀNH CHO OUTPUT ĐĂNG NHẬP
class RoleLoginInfo(BaseModel):
    id: int
    role_code: str
    role_name: str

class UserLoginInfo(BaseModel):
    id: int
    full_name: str
    username: str
    email: EmailStr | str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    status: str
    role: RoleLoginInfo | None = None
    permissions: list[str] = []
    last_login_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

class LoginResponseData(BaseModel):
    access_token: str
    token_type: str
    is_first_login: bool
    user_info: UserLoginInfo 