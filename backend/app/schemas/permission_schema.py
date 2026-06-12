from datetime import datetime
from pydantic import BaseModel, Field, field_validator

class PermissionUpdate(BaseModel):
    pass

# Chuẩn hóa response API phân quyền
class PermissionResponse(BaseModel):
    id: int
    permission_code: str
    permission_name: str
    module_name: str
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}