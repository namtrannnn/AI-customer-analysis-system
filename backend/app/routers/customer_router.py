from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session
from typing import Any

from app.schemas import customer_schema as schemas
from app.schemas.response_schema import StandardResponse
from app.services import customer_service as services
from app.database.session import get_db 
from app.utils.response import success_response

router = APIRouter(
    prefix="/api/customers", 
    tags=["Customers"]
)

# CUS-API-01: API cho Camera tạo khách ẩn danh
@router.post("/anonymous", response_model=StandardResponse[schemas.PersonProfileResponse], status_code=status.HTTP_201_CREATED)
def create_anonymous(payload: schemas.AnonymousCreate, db: Session = Depends(get_db)):
    """API dành riêng cho Camera gọi khi phát hiện khuôn mặt mới chưa từng xuất hiện"""
    profile = services.create_anonymous_profile(db=db, payload=payload)
    return success_response(data=profile, message="Tạo hồ sơ ẩn danh thành công")

# CUS-API-01: API cho Nhân viên thêm khách hàng chính thức
@router.post("/", response_model=StandardResponse[schemas.CustomerResponse], status_code=status.HTTP_201_CREATED)
def create_customer(payload: schemas.CustomerCreate, db: Session = Depends(get_db)):
    """API tạo khách hàng. Tự động xử lý liên kết khuôn mặt nếu có truyền person_profile_id"""
    customer = services.create_customer(db=db, payload=payload)
    return success_response(data=customer, message="Tạo khách hàng mới thành công")

# CUS-API-02: API xem danh sách khách hàng
@router.get("/", response_model=StandardResponse[list[schemas.CustomerResponse]])
def get_customers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    customers = services.get_list_customers(db=db, skip=skip, limit=limit)
    # Lưu ý: Để tối ưu phân trang, bạn có thể viết thêm hàm đếm tổng (count) trong service
    total = len(customers) 
    return success_response(
        data=customers, 
        message="Lấy danh sách khách hàng thành công",
        total=total, skip=skip, limit=limit
    )
