from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas import permission_schema as schemas
from app.schemas.response_schema import StandardResponse
from app.services import permission_service as services
from app.utils.response import success_response
from app.core.dependencies import get_admin_user

router = APIRouter(prefix="/api/permissions", tags=["Permissions"])

# API xem danh sách phân quyền
@router.get("/", response_model=StandardResponse[list[schemas.PermissionResponse]])
def get_permissions(
    db: Session = Depends(get_db),
    admin_user = Depends(get_admin_user) # BẢO MẬT: Chỉ Admin mới được quản lý quyền
):
    """API lấy toàn bộ danh sách Quyền (Permission)"""
    permissions = services.get_all_permissions(db=db)
    return success_response(
        data=permissions,
        message="Lấy danh sách quyền hệ thống thành công."
    )
