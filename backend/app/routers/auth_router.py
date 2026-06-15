from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.auth_schema import LoginRequest, ChangePasswordRequest
from app.schemas.response_schema import StandardResponse
from app.services import auth_service as services
from app.utils.response import success_response
from app.core.dependencies import get_admin_user, get_current_user 
from app.schemas import auth_schema as schemas

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# AUTH-API-01: Đăng nhập
@router.post("/login", response_model=StandardResponse[schemas.LoginResponseData])
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """API Đăng nhập. Nếu is_first_login = true, Frontend cần chuyển sang trang đổi mật khẩu."""
    result = services.authenticate_user(db=db, payload=payload)
    
    return success_response(
        data=result,
        message="Đăng nhập thành công."
    )

# AUTH-API-02: User tự đổi mật khẩu
@router.post("/change-password", response_model=StandardResponse)
def change_password(
    payload: ChangePasswordRequest, 
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user) # Bắt buộc phải truyền Token
):
    """API Đổi mật khẩu (Dùng cho cả lần đầu đăng nhập và lúc bình thường)"""
    result = services.change_user_password(db=db, user_id=current_user.id, payload=payload)
    return success_response(data=None, message=result["message"])

# AUTH-API-03: Admin cấp lại mật khẩu cho User
@router.post("/admin/reset-password/{target_user_id}", response_model=StandardResponse)
def admin_reset_password(
    target_user_id: int, 
    db: Session = Depends(get_db),
    admin_user = Depends(get_admin_user)
):
    """API Admin khởi tạo lại mật khẩu cho nhân viên."""
    new_password = services.admin_reset_user_password(
        db=db, 
        target_user_id=target_user_id,
        admin_id=admin_user.id 
    )
    
    return success_response(
        data={"new_temporary_password": new_password},
        message=f"Cấp lại mật khẩu thành công. Mật khẩu mới là: {new_password}"
    )

# AUTH-API-04: Đăng xuất (Logout)
@router.post("/logout", response_model=StandardResponse)
def logout(current_user = Depends(get_current_user)):
    # Xử lý đăng xuất
    return success_response(data=None, message="Đăng xuất thành công.")