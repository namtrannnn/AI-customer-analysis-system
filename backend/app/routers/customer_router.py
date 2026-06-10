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

# CUS-API-06: API tìm kiếm khách hàng
@router.get("/search", response_model=StandardResponse[list[schemas.CustomerResponse]])
def search_customers(
    q: str = Query(..., min_length=1, description="Từ khóa tìm kiếm theo tên, sđt, email hoặc mã"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    customers = services.search_customers(db=db, query_str=q, skip=skip, limit=limit)
    total = len(customers)
    return success_response(
        data=customers, 
        message="Tìm kiếm khách hàng thành công",
        total=total, skip=skip, limit=limit
    )

# CUS-API-07: API lọc khách hàng theo trạng thái
@router.get("/filter", response_model=StandardResponse[list[schemas.CustomerResponse]])
def filter_customers(
    status: str = Query(..., description="Trạng thái cần lọc: active hoặc inactive"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    customers = services.filter_customers_by_status(db=db, status_param=status, skip=skip, limit=limit)
    total = len(customers)
    return success_response(
        data=customers, 
        message="Lọc danh sách khách hàng thành công",
        total=total, skip=skip, limit=limit
    )

# CUS-API-03: Xem chi tiết khách hàng
@router.get("/{customer_id}", response_model=StandardResponse[schemas.CustomerResponse])
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    customer = services.get_customer_by_id(db=db, customer_id=customer_id)
    return success_response(data=customer, message="Lấy chi tiết khách hàng thành công")

# CUS-API-04: API cập nhật thông tin khách hàng
@router.patch("/{customer_id}", response_model=StandardResponse[schemas.CustomerResponse])
def update_customer(customer_id: int, customer: schemas.CustomerUpdate, db: Session = Depends(get_db)):
    updated_customer = services.update_customer(db=db, customer_id=customer_id, payload=customer)
    return success_response(data=updated_customer, message="Cập nhật thông tin khách hàng thành công")

# CUS-API-05: API xóa mềm khách hàng
@router.delete("/{customer_id}", response_model=StandardResponse[Any], status_code=status.HTTP_200_OK)
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    # Service soft_delete_customer đã thực hiện xóa mềm
    services.soft_delete_customer(db=db, customer_id=customer_id)
    return success_response(data=None, message="Xóa mềm khách hàng thành công")

# CUS-API-08: API upload/lưu ảnh khách hàng
@router.post("/{customer_id}/avatar", response_model=StandardResponse[schemas.CustomerResponse])
def upload_avatar(
    customer_id: int, 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    customer = services.upload_customer_avatar(db=db, customer_id=customer_id, file=file)
    return success_response(
        data=customer, 
        message="Cập nhật ảnh khuôn mặt thành công"
    )

# CUS-API-09: API lấy lịch sử ghé của khách
@router.get("/{customer_id}/visits", response_model=StandardResponse[list[schemas.VisitHistoryResponse]])
def get_visit_history(
    customer_id: int, 
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    visits = services.get_customer_visit_history(db=db, customer_id=customer_id, skip=skip, limit=limit)
    total = len(visits)
    return success_response(
        data=visits, 
        message="Lấy lịch sử ghé thăm thành công",
        total=total, skip=skip, limit=limit
    )

# CUS-API-10: API lấy lịch sử mua hàng của khách
@router.get("/{customer_id}/orders", response_model=StandardResponse[list[schemas.OrderHistoryResponse]])
def get_order_history(
    customer_id: int, 
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    orders = services.get_customer_order_history(db=db, customer_id=customer_id, skip=skip, limit=limit)
    total = len(orders)
    return success_response(
        data=orders, 
        message="Lấy lịch sử mua hàng thành công",
        total=total, skip=skip, limit=limit
    )
