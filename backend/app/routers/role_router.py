from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from typing import Any

from app.database.session import get_db
from app.schemas import role_schema as schemas
from app.services import role_service as services
from app.utils.response import success_response
from app.core.dependencies import get_admin_user
from app.schemas.response_schema import StandardResponse

router = APIRouter(prefix="/api/roles", tags=["Roles"])

# CUS-API-1: API Thêm nhóm quyền
@router.post("/", status_code=status.HTTP_201_CREATED)
def create_role(
    payload: schemas.RoleCreate, 
    db: Session = Depends(get_db),
    admin_user = Depends(get_admin_user) #  Chỉ Admin được phép tạo Role
):
    new_role = services.create_role_with_permissions(db=db, payload=payload)
    
    # Vì new_role là một Object SQLAlchemy, trích xuất dữ liệu ra dict để chuẩn hóa JSON
    response_data = {
        "id": new_role.id,
        "role_code": new_role.role_code,
        "role_name": new_role.role_name,
        "description": new_role.description,
        "permission_ids": new_role.permission_ids,
        "created_at": new_role.created_at
    }
    
    return success_response(
        data=response_data,
        message="Tạo nhóm quyền mới thành công."
    )

# CUS-API-2 & 6: API Xem danh sách và Tìm kiếm
@router.get("/full-details", response_model=StandardResponse[list[schemas.RoleFullDetailResponse]])
def get_roles_full_details(
    q: str | None = Query(default=None, description="Tìm kiếm theo mã hoặc tên nhóm quyền"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin_user = Depends(get_admin_user)
):    
    roles_detailed = services.get_roles_full_details_list(db=db, search_query=q, skip=skip, limit=limit)
    total = services.count_list_roles(db=db, search_query=q)
    
    return success_response(
        data=roles_detailed,
        message="Lấy danh sách chi tiết nhóm quyền thành công.",
        total=total,
        skip=skip,
        limit=limit
    )

# CUS-API-3: API Xem chi tiết
@router.get("/{role_id}", response_model=StandardResponse[schemas.RoleResponse])
def get_role(
    role_id: int, 
    db: Session = Depends(get_db),
    admin_user = Depends(get_admin_user)
):
    role = services.get_role_by_id(db=db, role_id=role_id)
    return success_response(data=role, message="Lấy chi tiết nhóm quyền thành công")

# CUS-API-4: API Cập nhật
@router.patch("/{role_id}", response_model=StandardResponse[schemas.RoleResponse])
def update_role(
    role_id: int, 
    payload: schemas.RoleUpdate, 
    db: Session = Depends(get_db),
    admin_user = Depends(get_admin_user)
):
    updated_role = services.update_role(db=db, role_id=role_id, payload=payload)
    return success_response(data=updated_role, message="Cập nhật nhóm quyền thành công")

# CUS-API-5: API Xóa
@router.delete("/{role_id}", response_model=StandardResponse[Any])
def delete_role(
    role_id: int, 
    db: Session = Depends(get_db),
    admin_user = Depends(get_admin_user)
):
    """Xóa nhóm quyền (Chỉ xóa được nếu không có nhân viên nào đang giữ quyền này)"""
    result = services.delete_role(db=db, role_id=role_id)
    return success_response(data=None, message=result["message"])