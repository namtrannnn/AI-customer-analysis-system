from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt

from app.database.session import get_db
from app.models.user import User
from app.core.security import SECRET_KEY, ALGORITHM
from app.models.user_role import UserRole
from app.models.permission import Permission
from app.models.role_permission import RolePermission

# Khai báo chuẩn OAuth2 của FastAPI. 
# tokenUrl là đường dẫn API dùng để lấy token (giúp Swagger UI tự động hiện nút Authorize)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: Session = Depends(get_db)
) -> User:
    """
    Hàm giải mã JWT Token để lấy thông tin User hiện tại.
    Sẽ được tái sử dụng trong tất cả các API cần bảo mật.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Không thể xác thực thông tin đăng nhập (Token không hợp lệ hoặc đã hết hạn).",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Giải mã token bằng SECRET_KEY
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Lấy username (đã lưu vào trường 'sub' lúc tạo token)
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
            
    except jwt.PyJWTError: # Bắt các lỗi của pyjwt như ExpiredSignatureError, DecodeError...
        raise credentials_exception

    # Sau khi giải mã thành công, truy vấn Database để lấy object User thực tế
    user = db.query(User).filter(User.username == username, User.status != "deleted").first()
    
    if user is None:
        raise credentials_exception
        
    if user.status == "inactive":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản của bạn đã bị khóa."
        )

    return user

def get_admin_user(
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency kiểm tra xem người dùng hiện tại có phải là Admin hay không.
    """
    ADMIN_ROLE_ID = 1 # Giả sử 1 là ID của quyền Admin
    
    is_admin = db.query(UserRole).filter(
        UserRole.user_id == current_user.id,
        UserRole.role_id == ADMIN_ROLE_ID
    ).first()
    
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Truy cập bị từ chối. Chỉ Quản trị viên (Admin) mới có quyền thực hiện hành động này."
        )
        
    return current_user

class RequirePermission:
    """
    Dependency dùng để kiểm tra xem User hiện tại có sở hữu một Quyền cụ thể hay không.
    Sử dụng: Depends(RequirePermission("CUSTOMER_CREATE"))
    """
    def __init__(self, required_permission: str):
        self.required_permission = required_permission

    def __call__(self, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        # 1. Kiểm tra xem user có được gán nhóm quyền nào chưa
        if not current_user.role_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tài khoản của bạn chưa được phân quyền để sử dụng hệ thống."
            )

        # 2. Truy vấn Database (JOIN 2 bảng) để dò xem Role của User có chứa mã Quyền này không
        has_permission = db.query(RolePermission).join(
            Permission, RolePermission.permission_id == Permission.id
        ).filter(
            RolePermission.role_id == current_user.role_id,
            Permission.permission_code == self.required_permission
        ).first()

        # 3. Chặn đứng và ném lỗi 403 nếu không tìm thấy quyền
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Truy cập bị từ chối! Bạn không có quyền thực hiện hành động này. (Mã quyền yêu cầu: {self.required_permission})"
            )

        # 4. Nếu hợp lệ, cho phép đi tiếp và trả về thông tin user
        return current_user