from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status
from app.models.user import User
from app.schemas.auth_schema import LoginRequest, ChangePasswordRequest
from app.core.security import verify_password, get_password_hash, create_access_token
from app.utils.helpers import generate_random_password
from app.models.user_role import UserRole
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission

# AUTH-API-01: Đăng nhập
def authenticate_user(db: Session, payload: LoginRequest) -> dict:
    # Tìm user và kiểm tra trạng thái
    user = db.query(User).filter(User.username == payload.username, User.status != "deleted").first()
    
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Sai tên đăng nhập hoặc mật khẩu."
        )
        
    if user.status == "inactive":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Tài khoản của bạn đã bị khóa. Vui lòng liên hệ Admin."
        )

    is_first_login = (user.last_login_at is None)

    if not is_first_login:
        user.last_login_at = func.now()
        db.commit()
        db.refresh(user) # Refresh lại để lấy last_login_at mới nhất

    # Tạo Token liên kết
    access_token = create_access_token(data={"sub": user.username, "id": user.id})

    # Truy vấn Duy nhất 1 lần để lấy mối quan hệ Role-User
    user_role_assoc = db.query(UserRole).filter(UserRole.user_id == user.id).first()
    
    role_data = None
    permissions_list = []

    if user_role_assoc:
        role = db.query(Role).filter(Role.id == user_role_assoc.role_id).first()
        if role:
            # Gói thông tin Role thành cấu trúc khớp với RoleLoginInfo Schema
            role_data = {
                "id": role.id,
                "role_code": role.role_code,
                "role_name": role.role_name
            }
            
            # Truy vấn danh sách chuỗi mã quyền phẳng (Flat list of string permission codes)
            perms = db.query(Permission.permission_code).join(
                RolePermission, RolePermission.permission_id == Permission.id
            ).filter(
                RolePermission.role_id == role.id
            ).all()
            
            permissions_list = [p[0] for p in perms]

    # Đóng gói object user_info đầy đủ trường để khít hoàn toàn với UserLoginInfo Schema
    user_info_dict = {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "avatar_url": user.avatar_url,
        "status": user.status,
        "role": role_data,
        "permissions": permissions_list,
        "last_login_at": user.last_login_at, 
        "created_at": user.created_at,
        "updated_at": user.updated_at
    }

    # 5. Trả về kết quả đầu ra sạch sẽ
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_info": user_info_dict,
        "is_first_login": is_first_login
    }

# AUTH-API-02: Đổi mật khẩu (Dùng chung cho lần đầu và bình thường)
def change_user_password(db: Session, user_id: int, payload: ChangePasswordRequest) -> dict:
    user = db.query(User).filter(User.id == user_id, User.status != "deleted").first()
    
    # 1. Kiểm tra mật khẩu cũ
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Mật khẩu hiện tại không chính xác."
        )
        
    # 2. Băm và cập nhật mật khẩu mới
    user.password_hash = get_password_hash(payload.new_password)
    
    # 3. Đánh dấu đã đăng nhập thành công (Thoát khỏi trạng thái first_login)
    user.last_login_at = func.now()
    user.updated_at = func.now()
    
    db.commit()
    return {"message": "Đổi mật khẩu thành công."}

# AUTH-API-03: Admin cấp lại mật khẩu (Reset Password)
def admin_reset_user_password(db: Session, target_user_id: int, admin_id: int) -> str:
    # 1. BẢO MẬT: Chặn Admin tự cấp lại mật khẩu cho chính mình
    if admin_id == target_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bạn không thể tự cấp lại mật khẩu cho chính mình. Vui lòng sử dụng tính năng Đổi mật khẩu cá nhân."
        )

    # 2. Bỏ qua những user đã bị xóa mềm (deleted)
    user = db.query(User).filter(User.id == target_user_id, User.status != "deleted").first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Không tìm thấy người dùng."
        )
        
    # 3. Sinh mật khẩu ngẫu nhiên độ bảo mật cao (Ví dụ: xT8#mP2!qL)
    new_plain_password = generate_random_password(length=10)
    
    # 4. Băm mật khẩu và lưu vào DB
    user.password_hash = get_password_hash(new_plain_password)
    
    # 5. Trả last_login_at về None để bắt người dùng phải đổi mật khẩu ngay khi đăng nhập lại
    user.last_login_at = None 
    user.updated_at = func.now()
    
    db.commit()
    
    # Trả về mật khẩu chưa băm để Router hiển thị cho Admin copy
    return new_plain_password