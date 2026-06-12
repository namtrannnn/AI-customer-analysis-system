from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.models.permission import Permission
from app.schemas.permission_schema import PermissionUpdate

# API: Xem danh sách phân quyền
def get_all_permissions(db: Session) -> list[Permission]:
    """
    Lấy danh sách tất cả các quyền (Permissions).
    Sắp xếp theo module_name để Frontend dễ dàng vẽ giao diện gom nhóm.
    """
    return db.query(Permission).order_by(Permission.module_name, Permission.id).all()
