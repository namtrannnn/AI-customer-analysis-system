from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas import permission_schema as schemas
from app.schemas.response_schema import StandardResponse
from app.services import permission_service as services
from app.utils.response import success_response
from app.core.dependencies import RequirePermission

router = APIRouter(prefix="/api/permissions", tags=["Permissions"])

# API lấy cấu trúc ma trận phân quyền phục vụ UI 
@router.get("/matrix", response_model=StandardResponse[schemas.PermissionMatrixResponse])
def get_permission_matrix(
    db: Session = Depends(get_db),
    current_user = Depends(RequirePermission("permission.view"))
):
    """API lấy cấu trúc ma trận quyền (Roles x Modules x Permissions) cho bảng cấu hình phân quyền"""
    matrix_data = services.get_permission_matrix(db=db)
    return success_response(
        data=matrix_data,
        message="Lấy ma trận phân quyền thành công."
    )


# API cập nhật hàng loạt ma trận phân quyền (Bulk Update khi bấm nút Lưu trên UI)
@router.post("/matrix/bulk", response_model=StandardResponse[Any])
def bulk_update_permission_matrix(
    payload: list[schemas.RolePermissionsBulkUpdate],
    db: Session = Depends(get_db),
    current_user = Depends(RequirePermission("permission.update"))
):
    """API lưu toàn bộ trạng thái ma trận quyền khi Admin bấm chốt trên giao diện"""
    # Chuyển đổi dữ liệu từ Pydantic Object sang List Dict thuần để Service xử lý gọn
    payload_data = [item.model_dump() for item in payload]
    result = services.bulk_update_permission_matrix(db=db, payload=payload_data)
    
    return success_response(
        data=None,
        message=result["message"]
    )


# API xem danh sách phẳng phân quyền cơ bản
@router.get("/", response_model=StandardResponse[list[schemas.PermissionResponse]])
def get_permissions(
    db: Session = Depends(get_db),
    current_user = Depends(RequirePermission("permission.view"))
):
    """API lấy toàn bộ danh sách Quyền (Permission) dạng phẳng"""
    permissions = services.get_all_permissions(db=db)
    return success_response(
        data=permissions,
        message="Lấy danh sách quyền hệ thống thành công."
    )


# API cập nhật thông tin chi tiết của 1 quyền
@router.patch("/{permission_id}", response_model=StandardResponse[schemas.PermissionResponse])
def update_permission(
    permission_id: int,
    payload: schemas.PermissionUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(RequirePermission("permission.update"))
):
    """API cập nhật Tên, Module hoặc Mô tả của quyền (Không cho phép đổi permission_code)"""
    updated_permission = services.update_permission(db=db, permission_id=permission_id, payload=payload)
    return success_response(
        data=updated_permission,
        message="Cập nhật thông tin phân quyền thành công."
    )