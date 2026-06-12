from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status
from app.models.user import User
from app.schemas.auth_schema import LoginRequest, ChangePasswordRequest
from app.core.security import verify_password, get_password_hash, create_access_token
from app.utils.helpers import generate_random_password
from app.models.user_role import UserRole

# AUTH-API-01: Đăng nhập
def authenticate_user(db: Session, payload: LoginRequest) -> dict:
    # 1. Tìm user và kiểm tra trạng thái
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

    # 2. Lấy danh sách Role từ bảng phân quyền
    user_roles = db.query(UserRole).filter(UserRole.user_id == user.id).all()
    role_ids = [role.role_id for role in user_roles]

    # 3. Tạo Token
    access_token = create_access_token(data={"sub": user.username, "id": user.id})

    # 4. Trả về toàn bộ thông tin chi tiết
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "is_first_login": is_first_login,
        "user_info": {
            "id": user.id,
            "full_name": user.full_name,
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "avatar_url": user.avatar_url,
            "status": user.status,
            "role_ids": role_ids,
            "last_login_at": user.last_login_at,
            "created_at": user.created_at,
            "updated_at": user.updated_at
        }
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