from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session
from typing import Any

from app.schemas import user_schema as schemas
from app.schemas.response_schema import StandardResponse
from app.services import user_service as services
from app.database.session import get_db 
from app.utils.response import success_response

router = APIRouter(
    prefix="/api/users", 
    tags=["Users"]
)

# CUS-API-01: API thêm user
@router.post("/", response_model=StandardResponse[schemas.UserCreateResponse], status_code=status.HTTP_201_CREATED)
def create_user(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    
    result = services.create_user(db=db, payload=payload)
    new_user = result["user"]
    temp_pass = result["plain_password"]
    
    # Trả về data khớp với Schema UserCreateResponse
    return success_response(
        data={
            "id": new_user.id,
            "full_name": new_user.full_name,
            "username": new_user.username,
            "temporary_password": temp_pass
        },
        message="Tạo người dùng mới thành công. Vui lòng lưu lại Tên đăng nhập và Mật khẩu."
    )

# CUS-API-02-06-07: API xem danh sách user Tìm kiếm và Lọc User
@router.get("/", response_model=StandardResponse[list[schemas.UserResponse]])
def get_users(
    q: str | None = Query(default=None, description="Từ khóa tìm kiếm theo tên, username, sđt hoặc email"),
    status_param: str | None = Query(default=None, alias="status", description="Trạng thái cần lọc: active hoặc inactive"),
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """API lấy danh sách người dùng, có hỗ trợ tìm kiếm, lọc và phân trang"""
    users = services.get_list_users(
        db=db, 
        search_query=q, 
        status_param=status_param, 
        skip=skip, 
        limit=limit
    )
    
    total = services.count_list_users(
        db=db, 
        search_query=q, 
        status_param=status_param
    ) 
    
    return success_response(
        data=users, 
        message="Lấy danh sách người dùng thành công",
        total=total, 
        skip=skip, 
        limit=limit
    )

# CUS-API-03: API xem chi tiết user
@router.get("/{user_id}", response_model=StandardResponse[schemas.UserResponse])
def get_user(user_id: int, db: Session = Depends(get_db)):
    """API lấy chi tiết thông tin người dùng bằng ID"""
    user = services.get_user_by_id(db=db, user_id=user_id)
    return success_response(data=user, message="Lấy chi tiết người dùng thành công")


# CUS-API-4: API cập nhật thông tin user
@router.patch("/{user_id}", response_model=StandardResponse[schemas.UserResponse])
def update_user(user_id: int, payload: schemas.UserUpdate, db: Session = Depends(get_db)):
    """API cập nhật thông tin người dùng (truyền lên các field cần update)"""
    updated_user = services.update_user(db=db, user_id=user_id, payload=payload)
    return success_response(
        data=updated_user, 
        message="Cập nhật thông tin người dùng thành công"
    )

# CUS-API-5: API xóa mềm user
@router.delete("/{user_id}", response_model=StandardResponse[Any], status_code=status.HTTP_200_OK)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """API xóa mềm người dùng (chuyển trạng thái sang deleted)"""
    services.soft_delete_user(db=db, user_id=user_id)
    return success_response(
        data=None, 
        message="Xóa người dùng thành công"
    )

# CUS-API-8: API upload/lưu ảnh user
@router.post("/{user_id}/avatar", response_model=StandardResponse[schemas.UserResponse])
def upload_avatar(
    user_id: int, 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    """API tải lên và cập nhật ảnh đại diện của người dùng (tối đa 3MB)"""
    user = services.upload_user_avatar(db=db, user_id=user_id, file=file)
    return success_response(
        data=user, 
        message="Cập nhật ảnh đại diện thành công"
    )