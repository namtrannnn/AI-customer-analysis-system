from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models.role import Role
from app.models.permission import Permission
from app.models.role_permission import RolePermission
from app.schemas.role_schema import RoleCreate, RoleUpdate
from app.models.user_role import UserRole
from app.models.user import User

# CUS-API-1: Thêm nhóm quyền
def create_role_with_permissions(db: Session, payload: RoleCreate) -> dict:
    # 1. Kiểm tra trùng lặp mã nhóm quyền
    existing_role = db.query(Role).filter(Role.role_code == payload.role_code).first()
    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mã nhóm quyền '{payload.role_code}' đã tồn tại trong hệ thống."
        )

    # 2. Kiểm tra tính hợp lệ của mảng quyền (nếu có)
    permission_ids_from_ui = payload.permission_ids
    if permission_ids_from_ui:
        # Đếm số lượng ID hợp lệ thực sự tồn tại trong DB
        valid_permissions_count = db.query(Permission).filter(
            Permission.id.in_(permission_ids_from_ui)
        ).count()
        
        # Nếu số lượng đếm được không khớp với số lượng gửi lên -> Frontend gửi ID rác
        if valid_permissions_count != len(permission_ids_from_ui):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Một hoặc nhiều Quyền (Permission) được chọn không tồn tại."
            )

    try:
        # 3. Tạo Nhóm quyền mới
        role_data = payload.model_dump(exclude={"permission_ids"})
        new_role = Role(**role_data)
        
        db.add(new_role)
        db.flush() # Đẩy tạm xuống DB để lấy new_role.id mà chưa chốt giao dịch

        # 4. Lưu danh sách quyền vào bảng trung gian
        if permission_ids_from_ui:
            for p_id in permission_ids_from_ui:
                new_role_permission = RolePermission(
                    role_id=new_role.id, 
                    permission_id=p_id
                )
                db.add(new_role_permission)

        # 5. Chốt toàn bộ transaction
        db.commit()
        db.refresh(new_role)
        
        # Gắn mảng permissions vào object trả về để Frontend vẽ giao diện
        new_role.permission_ids = permission_ids_from_ui
        
        return new_role

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lỗi ràng buộc dữ liệu khi lưu nhóm quyền."
        )
    
# CUS-API-2 & 6: Xem danh sách và Tìm kiếm nhóm quyền
def get_roles_full_details_list(
    db: Session, 
    search_query: str | None = None, 
    skip: int = 0, 
    limit: int = 100
) -> list[dict]:
    
    query = db.query(Role)
    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter(
            or_(Role.role_code.ilike(search_pattern), Role.role_name.ilike(search_pattern))
        )
        
    roles = query.order_by(Role.id.desc()).offset(skip).limit(limit).all()
    
    full_details_list = []
    
    for role in roles:
        # Lấy danh sách Object User thuộc nhóm quyền này (Bỏ qua các user đã bị xóa mềm)
        users = db.query(User).join(
            UserRole, UserRole.user_id == User.id
        ).filter(
            UserRole.role_id == role.id,
            User.status != "deleted"
        ).all()
        
        # Lấy danh sách Object Permission thuộc nhóm quyền này
        permissions = db.query(Permission).join(
            RolePermission, RolePermission.permission_id == Permission.id
        ).filter(
            RolePermission.role_id == role.id
        ).all()
        
        # Đóng gói dữ liệu lồng nhau
        full_details_list.append({
            "id": role.id,
            "role_code": role.role_code,
            "role_name": role.role_name,
            "description": role.description,
            "users": users,         # Pydantic sẽ tự động lọc cấu trúc thông qua UserMinInfo
            "permissions": permissions,
            "created_at": role.created_at
        })
        
    return full_details_list

def count_list_roles(db: Session, search_query: str | None = None) -> int:
    query = db.query(Role)
    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter(
            or_(Role.role_code.ilike(search_pattern), Role.role_name.ilike(search_pattern))
        )
    return query.count()

# CUS-API-3: Xem chi tiết nhóm quyền
def get_role_by_id(db: Session, role_id: int) -> Role:
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy Nhóm quyền với ID {role_id}.")
        
    role_permissions = db.query(RolePermission).filter(RolePermission.role_id == role.id).all()
    role.permission_ids = [rp.permission_id for rp in role_permissions]
    
    return role

# CUS-API-4: Cập nhật thông tin nhóm quyền
def update_role(db: Session, role_id: int, payload: RoleUpdate) -> Role:
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Không tìm thấy Nhóm quyền.")

    update_data = payload.model_dump(exclude_unset=True)

    # Kiểm tra trùng lặp mã quyền nếu có yêu cầu đổi
    if "role_code" in update_data and update_data["role_code"]:
        code_exists = db.query(Role).filter(Role.role_code == update_data["role_code"], Role.id != role_id).first()
        if code_exists:
            raise HTTPException(status_code=400, detail="Mã nhóm quyền này đã tồn tại.")

    try:
        # Xử lý cập nhật danh sách Permission
        if "permission_ids" in update_data:
            new_permission_ids = update_data.pop("permission_ids")
            
            # Validate mảng ID mới
            if new_permission_ids:
                valid_count = db.query(Permission).filter(Permission.id.in_(new_permission_ids)).count()
                if valid_count != len(new_permission_ids):
                    raise HTTPException(status_code=400, detail="Quyền được chọn không tồn tại.")
            
            # Xóa sạch các quyền cũ trong bảng trung gian
            db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()
            
            # Thêm mới
            for p_id in new_permission_ids:
                db.add(RolePermission(role_id=role_id, permission_id=p_id))

        # Cập nhật các trường text
        for key, value in update_data.items():
            setattr(role, key, value)

        db.commit()
        db.refresh(role)
        
        # Lấy lại danh sách gán vào object để trả về chuẩn schema
        current_permissions = db.query(RolePermission).filter(RolePermission.role_id == role.id).all()
        role.permission_ids = [rp.permission_id for rp in current_permissions]
        
        return role

    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Lỗi ràng buộc hệ thống khi cập nhật nhóm quyền.")

# CUS-API-5: Xóa nhóm quyền
def delete_role(db: Session, role_id: int) -> dict:
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Không tìm thấy Nhóm quyền.")

    # Kiểm tra ràng buộc: Không cho phép xóa Role đang có người sử dụng
    users_with_role = db.query(UserRole).filter(UserRole.role_id == role_id).first()
    if users_with_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể xóa nhóm quyền này vì đang có người dùng được gán quyền này."
        )

    # Vì bảng Role không có cột status="deleted", ta thực hiện xóa cứng (Hard Delete)
    # Các record trong bảng RolePermission sẽ tự động bị xóa theo nhờ ondelete="CASCADE" trong Model
    db.delete(role)
    db.commit()
    return {"message": "Xóa nhóm quyền thành công."}