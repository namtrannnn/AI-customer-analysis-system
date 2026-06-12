from collections import defaultdict

from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.models.permission import Permission
from app.schemas.permission_schema import PermissionUpdate
from app.models.role import Role
from app.models.role_permission import RolePermission

# API: Xem danh sách phân quyền
def get_all_permissions(db: Session) -> list[Permission]:
    """
    Lấy danh sách tất cả các quyền (Permissions).
    Sắp xếp theo module_name để Frontend dễ dàng vẽ giao diện gom nhóm.
    """
    return db.query(Permission).order_by(Permission.module_name, Permission.id).all()

# Cập nhật thông tin 1 quyền (Tên, Mô tả)
def update_permission(db: Session, permission_id: int, payload: PermissionUpdate) -> Permission:
    permission = db.query(Permission).filter(Permission.id == permission_id).first()
    if not permission:
        raise HTTPException(status_code=404, detail="Không tìm thấy dữ liệu Quyền.")

    update_data = payload.model_dump(exclude_unset=True)
    try:
        for key, value in update_data.items():
            setattr(permission, key, value)
        db.commit()
        db.refresh(permission)
        return permission
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Lỗi cập nhật. Vui lòng kiểm tra lại.")

# CÁC HÀM XỬ LÝ MA TRẬN CHO UI FRONTEND
def get_permission_matrix(db: Session) -> dict:
    """
    Trả về cấu trúc dữ liệu 3 chiều để Frontend vẽ Ma trận phân quyền
    """
    # 1. Lấy danh sách Roles làm Cột 
    roles = db.query(Role).order_by(Role.id).all()
    roles_data = [{"id": r.id, "role_code": r.role_code, "role_name": r.role_name} for r in roles]

    # 2. Lấy danh sách Permissions làm Hàng (Gom nhóm theo module_name)
    permissions = db.query(Permission).order_by(Permission.module_name, Permission.id).all()
    modules_dict = defaultdict(list)
    for p in permissions:
        modules_dict[p.module_name].append({
            "id": p.id,
            "permission_code": p.permission_code,
            "permission_name": p.permission_name
        })
    modules_data = [{"module_name": k, "permissions": v} for k, v in modules_dict.items()]

    # 3. Lấy Ma trận (Các ô Checkbox). Trả về dạng dict: { role_id: [permission_id_1, ...] }
    role_permissions = db.query(RolePermission).all()
    role_perm_map = defaultdict(list)
    for rp in role_permissions:
        role_perm_map[str(rp.role_id)].append(rp.permission_id)

    return {
        "roles": roles_data,
        "modules": modules_data,
        "role_permissions": dict(role_perm_map)
    }

def bulk_update_permission_matrix(db: Session, payload: list[dict]) -> dict:
    """
    Hàm lưu toàn bộ trạng thái của Ma trận khi người dùng bấm "Lưu thay đổi" trên giao diện.
    Payload nhận vào là một mảng: [{"role_id": 1, "permission_ids": [1, 2, 3]}, ...]
    """
    try:
        for item in payload:
            role_id = item["role_id"]
            new_perm_ids = item["permission_ids"]

            # Xóa toàn bộ quyền cũ của Role này
            db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()

            # Thêm lại các quyền mới được tick trên UI
            if new_perm_ids:
                new_records = [RolePermission(role_id=role_id, permission_id=p_id) for p_id in new_perm_ids]
                db.add_all(new_records)

        db.commit()
        return {"message": "Cập nhật ma trận phân quyền thành công."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống khi lưu ma trận: {str(e)}")