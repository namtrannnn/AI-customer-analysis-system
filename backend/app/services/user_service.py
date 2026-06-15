import time

from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, UploadFile, status
from app.utils.supabase_client import supabase

from app.models.user import User
from app.schemas.user_schema import UserCreate, UserUpdate
from app.core.security import get_password_hash
from app.models.user_role import UserRole
from app.utils.helpers import generate_corporate_username, generate_random_password
from app.models.role import Role

# API thêm user (Luồng cấp phát tự động)
def create_user(db: Session, payload: UserCreate) -> dict:
    # Kiểm tra dữ liệu trùng lặp
    if payload.email and db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email này đã được đăng ký.")

    if payload.phone and db.query(User).filter(User.phone == payload.phone).first():
        raise HTTPException(status_code=400, detail="Số điện thoại này đã được đăng ký.")

    # Sinh username từ tên và sinh password ngẫu nhiên 
    new_username = generate_corporate_username(payload.full_name, db)
    plain_password = generate_random_password(length=10) 
    
    # Chỉ lấy chuỗi hash để lưu DB 
    hashed_password = get_password_hash(plain_password)

    user_data = payload.model_dump(exclude={"role_id"})
    role_id_from_ui = payload.role_id

    if role_id_from_ui:
        role_exists = db.query(Role).filter(Role.id == role_id_from_ui).first()
        if not role_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Vai trò (Role) không tồn tại trong hệ thống. Vui lòng tải lại trang."
            )
    
    try:
        # 1. Tạo User
        new_user = User(
            **user_data,
            username=new_username,
            password_hash=hashed_password,
            status="active"
        )
        db.add(new_user)
        
        # 2. Đẩy tạm xuống DB để lấy ID
        db.flush() 

        # 3. Gán đúng 1 Role vào bảng trung gian
        if role_id_from_ui:
            new_user_role = UserRole(user_id=new_user.id, role_id=role_id_from_ui)
            db.add(new_user_role)

        # 4. Chốt transaction
        db.commit()
        db.refresh(new_user)

        new_user.role_id = role_id_from_ui
        
        return {
            "user": new_user,
            "plain_password": plain_password
        }
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Lỗi dữ liệu. Vui lòng kiểm tra lại."
        )
    
# Xem danh sách, Tìm kiếm và Lọc trạng thái 
def get_list_users(
    db: Session, 
    search_query: str | None = None, 
    status_param: str | None = None, 
    skip: int = 0, 
    limit: int = 100
) -> list[User]:
    # 1. Khởi tạo câu truy vấn gốc
    query = db.query(User).filter(User.status != "deleted")
    
    # Đắp thêm điều kiện Lọc theo trạng thái 
    if status_param:
        if status_param not in ["active", "inactive"]: 
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Trạng thái lọc không hợp lệ. Chỉ chấp nhận 'active' hoặc 'inactive'." 
            )
        query = query.filter(User.status == status_param) 
        
    # Đắp thêm điều kiện Tìm kiếm
    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter(
            or_(
                User.full_name.ilike(search_pattern),
                User.username.ilike(search_pattern), 
                User.email.ilike(search_pattern), 
                User.phone.ilike(search_pattern) 
            )
        )
        
    users = query.order_by(User.id.desc()).offset(skip).limit(limit).all()
    
    for user in users:
        user_role = db.query(UserRole).filter(UserRole.user_id == user.id).first()
        user.role_id = user_role.role_id if user_role else None
        
    return users


def count_list_users(
    db: Session, 
    search_query: str | None = None, 
    status_param: str | None = None
) -> int:
    query = db.query(User).filter(User.status != "deleted")
    
    if status_param:
        query = query.filter(User.status == status_param) 
        
    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter(
            or_(
                User.full_name.ilike(search_pattern), 
                User.username.ilike(search_pattern), 
                User.email.ilike(search_pattern), 
                User.phone.ilike(search_pattern) 
            )
        )
        
    return query.count()

# API xem chi tiết user
def get_user_by_id(db: Session, user_id: int):
    user = db.query(User).filter(User.id == user_id, User.status != "deleted").first()
    if not user:
        raise HTTPException(
            status_code=404, 
            detail=f"Không tìm thấy hoặc người dùng với ID {user_id} đã bị xóa."
        )
        
    # Lấy 1 record phân quyền duy nhất
    user_role = db.query(UserRole).filter(UserRole.user_id == user.id).first()
    user.role_id = user_role.role_id if user_role else None
    
    return user

# API cập nhật thông tin user
def update_user(db: Session, user_id: int, payload: UserUpdate) -> User:
    user = db.query(User).filter(User.id == user_id, User.status != "deleted").first() 
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy người dùng hoạt động với ID {user_id}" 
        )
    
    update_data = payload.model_dump(exclude_unset=True)
    
    if "email" in update_data and update_data["email"]:
        email_exists = db.query(User).filter(User.email == update_data["email"], User.id != user_id).first() 
        if email_exists:
            raise HTTPException(status_code=400, detail="Email này đã được đăng ký bởi người dùng khác.")

    if "phone" in update_data and update_data["phone"]:
        phone_exists = db.query(User).filter(User.phone == update_data["phone"], User.id != user_id).first() 
        if phone_exists:
            raise HTTPException(status_code=400, detail="Số điện thoại này đã được đăng ký bởi người dùng khác.")

    try:
        if "role_id" in update_data:
            new_role_id = update_data.pop("role_id")

            if new_role_id:
                role_exists = db.query(Role).filter(Role.id == new_role_id).first()
                if not role_exists:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST, 
                        detail="Vai trò (Role) được chọn không tồn tại."
                    )
            
            # Xóa Role cũ trong bảng phân quyền
            db.query(UserRole).filter(UserRole.user_id == user_id).delete()
            
            # Insert 1 Role mới
            if new_role_id:
                db.add(UserRole(user_id=user_id, role_id=new_role_id))
                
        # CẬP NHẬT CÁC TRƯỜNG THÔNG TIN CÒN LẠI
        for key, value in update_data.items():
            setattr(user, key, value)
            
        user.updated_at = func.now() 
        
        db.commit()
        db.refresh(user)
        
        # Gắn role_id vào biến động để trả về
        current_role = db.query(UserRole).filter(UserRole.user_id == user_id).first()
        user.role_id = current_role.role_id if current_role else None
        
        return user
        
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dữ liệu cập nhật vi phạm ràng buộc hệ thống."
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi hệ thống khi cập nhật người dùng. Chi tiết: {str(e)}"
        )


# API xóa mềm user 
def soft_delete_user(db: Session, user_id: int, admin_id: int) -> dict:
    # Chặn Admin tự xóa mình 
    if admin_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bạn không thể tự xóa tài khoản của chính mình."
        )
    
    user = db.query(User).filter(User.id == user_id, User.status != "deleted").first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy hoặc người dùng với ID {user_id} đã bị xóa trước đó." 
        )
        
    user.status = "deleted" 
    user.updated_at = func.now()
    db.commit()
    return {"message": "Xóa mềm tài khoản người dùng thành công."}


# API upload/lưu ảnh user
MAX_FILE_SIZE = 3 * 1024 * 1024  

def upload_user_avatar(db: Session, user_id: int, file: UploadFile) -> User:
    user = db.query(User).filter(User.id == user_id, User.status != "deleted").first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy người dùng với ID {user_id}" 
        )
    
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File tải lên bắt buộc phải là định dạng hình ảnh.")

    file_bytes = file.file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Dung lượng ảnh vượt quá giới hạn cho phép (3MB).")

    try:
        if user.avatar_url: 
            try:
                old_file_path = user.avatar_url.split("/public/avatars/")[-1] 
                supabase.storage.from_("avatars").remove([old_file_path])
            except Exception as delete_error:
                pass

        file_extension = file.filename.split(".")[-1]
        file_path = f"users/avatar_{user_id}_{int(time.time())}.{file_extension}"
        
        supabase.storage.from_("avatars").upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": file.content_type}
        )
        
        public_url = supabase.storage.from_("avatars").get_public_url(file_path)
        user.avatar_url = public_url 
        user.updated_at = func.now() 
        
        db.commit()
        db.refresh(user)

        # Lấy 1 role duy nhất
        current_role = db.query(UserRole).filter(UserRole.user_id == user_id).first()
        user.role_id = current_role.role_id if current_role else None

        return user
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Gặp lỗi hệ thống khi lưu trữ hình ảnh lên Cloud. Chi tiết: {str(e)}"
        )