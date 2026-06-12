from datetime import datetime
from pydantic import BaseModel, Field, field_validator

# Validate dữ liệu phân quyền (Chỉ cập nhật name, module, description)
class PermissionUpdate(BaseModel):
    permission_name: str | None = Field(default=None, min_length=2, max_length=100)
    module_name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = None

    @field_validator("permission_name", "module_name")
    @classmethod
    def validate_not_empty(cls, v: str | None) -> str | None:
        if v is not None and len(v.strip()) == 0:
            raise ValueError("Trường dữ liệu không được để trống hoàn toàn chứa khoảng trắng.")
        return v.strip() if v else v

# Chuẩn hóa response API phân quyền
class PermissionResponse(BaseModel):
    id: int
    permission_code: str
    permission_name: str
    module_name: str
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}

class RoleMinInfo(BaseModel):
    id: int
    role_code: str
    role_name: str
    
    model_config = {"from_attributes": True}

class PermissionMinInfo(BaseModel):
    id: int
    permission_code: str
    permission_name: str
    
    model_config = {"from_attributes": True}

class ModulePermissions(BaseModel):
    module_name: str
    permissions: list[PermissionMinInfo]
    
    model_config = {"from_attributes": True}

# (Chuẩn hóa Response): Dành riêng cho API GET /matrix
class PermissionMatrixResponse(BaseModel):
    roles: list[RoleMinInfo]
    modules: list[ModulePermissions]
    # Key là role_id (chuỗi hóa thành string khi lên JSON), Value là mảng các permission_id được kích hoạt
    role_permissions: dict[str, list[int]] 

# (Validate dữ liệu): Dành riêng cho API cập nhật hàng loạt POST /matrix/bulk
class RolePermissionsBulkUpdate(BaseModel):
    role_id: int
    permission_ids: list[int] = Field(default_factory=list, description="Mảng chứa các ID quyền được tích chọn")