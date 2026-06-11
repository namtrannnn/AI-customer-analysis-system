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

# CUS-API-1: API thêm user (Luồng cấp phát tự động)
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

    user_data = payload.model_dump(exclude={"role_ids"})
    role_ids_from_ui = payload.role_ids
    
    try:
        # 1. Tạo User
        new_user = User(
            **user_data,
            username=new_username,
            password_hash=hashed_password,
            status="active"
        )
        db.add(new_user)
        
        # 2. Đẩy tạm xuống DB để lấy ID (nếu có lỗi khóa ngoại sẽ bị bắt ngay)
        db.flush() 

        # 3. Duyệt vòng lặp để gán nhiều Role
        for r_id in role_ids_from_ui:
            new_user_role = UserRole(user_id=new_user.id, role_id=r_id)
            db.add(new_user_role)

        # 4. Chốt transaction
        db.commit()
        db.refresh(new_user)

        new_user.role_ids = role_ids_from_ui
        
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
    
# CUS-API-2 - 6 - 7: Gộp Xem danh sách, Tìm kiếm và Lọc trạng thái 
def get_list_users(
    db: Session, 
    search_query: str | None = None, 
    status_param: str | None = None, 
    skip: int = 0, 
    limit: int = 100
) -> list[User]:
    # 1. Khởi tạo câu truy vấn gốc, LOẠI TRỪ NGAY các user đã bị deleted
    query = db.query(User).filter(User.status != "deleted")
    
    # Đắp thêm điều kiện Lọc theo trạng thái 
    if status_param:
        if status_param not in ["active", "inactive"]: 
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Trạng thái lọc không hợp lệ. Chỉ chấp nhận 'active' hoặc 'inactive'." 
            )
        query = query.filter(User.status == status_param) 
        
    # Đắp thêm điều kiện Tìm kiếm không phân biệt hoa thường 
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
        
    # Thực thi truy vấn với phân trang (Mới nhất lên đầu)
    users = query.order_by(User.id.desc()).offset(skip).limit(limit).all()
    
    # Lặp qua từng user để gắn thêm role_id
    for user in users:
        # Lấy tất cả role trả về dạng mảng như logic đã update
        user_roles = db.query(UserRole).filter(UserRole.user_id == user.id).all()
        user.role_ids = [role.role_id for role in user_roles]
        
    return users


def count_list_users(
    db: Session, 
    search_query: str | None = None, 
    status_param: str | None = None
) -> int:
    """Đếm tổng số lượng người dùng khớp điều kiện để xử lý phân trang chính xác"""
    # LOẠI TRỪ các user đã bị deleted ra khỏi kết quả đếm tổng
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

# CUS-API-3: API xem chi tiết user
def get_user_by_id(db: Session, user_id: int):
    # Thêm điều kiện chặn xem chi tiết user đã deleted
    user = db.query(User).filter(User.id == user_id, User.status != "deleted").first()
    if not user:
        raise HTTPException(
            status_code=404, 
            detail=f"Không tìm thấy hoặc người dùng với ID {user_id} đã bị xóa."
        )
        
    # Lấy TẤT CẢ record trong bảng phân quyền
    user_roles = db.query(UserRole).filter(UserRole.user_id == user.id).all()
    
    # Trích xuất ra thành mảng (List Comprehension) [1, 2, 3]
    user.role_ids = [role.role_id for role in user_roles]
    
    return user

# CUS-API-7: API cập nhật thông tin user
def update_user(db: Session, user_id: int, payload: UserUpdate) -> User:
    # 1. Kiểm tra sự tồn tại của user (bỏ qua những tài khoản đã bị xóa mềm)
    user = db.query(User).filter(User.id == user_id, User.status != "deleted").first() 
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy người dùng hoạt động với ID {user_id}" 
        )
    
    # Loại bỏ các trường không được gửi lên từ Frontend
    update_data = payload.model_dump(exclude_unset=True)
    
    # 2. Kiểm tra trùng lặp email duy nhất (nếu có yêu cầu đổi email)
    if "email" in update_data and update_data["email"]:
        email_exists = db.query(User).filter(User.email == update_data["email"], User.id != user_id).first() 
        if email_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email này đã được đăng ký bởi người dùng khác." 
            )

    # 3. Kiểm tra trùng lặp số điện thoại (nếu có yêu cầu đổi SĐT)
    if "phone" in update_data and update_data["phone"]:
        phone_exists = db.query(User).filter(User.phone == update_data["phone"], User.id != user_id).first() 
        if phone_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Số điện thoại này đã được đăng ký bởi người dùng khác." 
            )

    try:
        # 4. XỬ LÝ CẬP NHẬT NHIỀU ROLE CÙNG LÚC
        if "role_ids" in update_data:
            # Cắt danh sách role_ids ra khỏi update_data để không bị lỗi gán vào bảng User
            new_role_ids = update_data.pop("role_ids")
            
            # Xóa toàn bộ Role cũ của user này trong bảng phân quyền
            db.query(UserRole).filter(UserRole.user_id == user_id).delete()
            
            # Quét mảng mới và Insert lại toàn bộ vào DB
            for r_id in new_role_ids:
                new_user_role = UserRole(user_id=user_id, role_id=r_id)
                db.add(new_user_role)
                
        # 5. CẬP NHẬT CÁC TRƯỜNG THÔNG TIN CÒN LẠI
        for key, value in update_data.items():
            setattr(user, key, value)
            
        # Tự động cập nhật thời gian sửa đổi
        user.updated_at = func.now() 
        
        # Chốt transaction lưu vào Database
        db.commit()
        db.refresh(user)
        
        # 6. Lấy lại danh sách Role mới nhất từ DB để gán vào biến động trả về Frontend
        current_roles = db.query(UserRole).filter(UserRole.user_id == user_id).all()
        user.role_ids = [role.role_id for role in current_roles]
        
        return user
        
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dữ liệu cập nhật vi phạm ràng buộc hệ thống (Ví dụ: ID vai trò không tồn tại)."
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi hệ thống khi cập nhật người dùng. Chi tiết: {str(e)}"
        )


# CUS-API-5: API xóa mềm user 
def soft_delete_user(db: Session, user_id: int) -> dict:
    user = db.query(User).filter(User.id == user_id, User.status != "deleted").first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy hoặc người dùng với ID {user_id} đã bị xóa trước đó." 
        )
        
    # Chuyển trạng thái sang deleted thay vì xóa vật lý khỏi hệ thống
    user.status = "deleted" 
    user.updated_at = func.now()
    db.commit()
    return {"message": "Xóa mềm tài khoản người dùng thành công."}


# CUS-API-8: API upload/lưu ảnh user
MAX_FILE_SIZE = 3 * 1024 * 1024  # Giới hạn dung lượng file ảnh (3MB)

def upload_user_avatar(db: Session, user_id: int, file: UploadFile) -> User:
    # 1. Kiểm tra sự tồn tại của người dùng
    user = db.query(User).filter(User.id == user_id, User.status != "deleted").first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy người dùng với ID {user_id}" 
        )
    
    # Kiểm tra định dạng hình ảnh và kích thước file tải lên
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File tải lên bắt buộc phải là định dạng hình ảnh.")

    file_bytes = file.file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Dung lượng ảnh vượt quá giới hạn cho phép (3MB).")

    try:
        # Dọn dẹp tệp tin ảnh cũ trên Cloud Storage (nếu có) nhằm tối ưu không gian lưu trữ
        if user.avatar_url: 
            try:
                old_file_path = user.avatar_url.split("/public/avatars/")[-1] 
                supabase.storage.from_("avatars").remove([old_file_path])
            except Exception as delete_error:
                print(f"[Warning] Không thể dọn dẹp ảnh cũ trên Supabase Storage: {delete_error}")

        # Upload ảnh đại diện mới lên Supabase Storage
        file_extension = file.filename.split(".")[-1]
        file_path = f"users/avatar_{user_id}_{int(time.time())}.{file_extension}"
        
        supabase.storage.from_("avatars").upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": file.content_type}
        )
        
        # Lấy Public URL và đồng bộ vào DB
        public_url = supabase.storage.from_("avatars").get_public_url(file_path)
        user.avatar_url = public_url 
        user.updated_at = func.now() 
        
        db.commit()
        db.refresh(user)

        current_roles = db.query(UserRole).filter(UserRole.user_id == user_id).all()
        user.role_ids = [role.role_id for role in current_roles]

        return user
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Gặp lỗi hệ thống khi lưu trữ hình ảnh lên Cloud. Chi tiết: {str(e)}"
        )
