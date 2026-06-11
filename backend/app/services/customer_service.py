import time

from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, UploadFile, status
from app.utils.supabase_client import supabase

from app.models.customer import Customer
from app.schemas.customer_schema import AnonymousCreate, CustomerCreate, CustomerUpdate
from app.models.customer_identity import CustomerIdentity
from app.models.order import Order
from app.models.person_profile import PersonProfile
from app.models.visit_sessions import VisitSession

def generate_customer_code(number: int) -> str:
    return f"CUS{number:06d}"

def get_next_customer_code(db: Session) -> str:
    result = db.execute(text("SELECT nextval('customer_code_seq')"))
    next_number = result.scalar_one()
    return generate_customer_code(next_number)

def generate_anonymous_code(prefix: str = "ANO") -> str:
    # Sinh mã dựa trên timestamp để đảm bảo unique
    return f"{prefix}{int(time.time() * 1000)}"

# CUS-API-01: Thêm khách hàng
# LUỒNG 1: Camera gọi API này khi phát hiện khuôn mặt mới (Thêm anonymous)
def create_anonymous_profile(db: Session, payload: AnonymousCreate) -> PersonProfile:
    new_profile = PersonProfile(
        anonymous_code=generate_anonymous_code("ANO"),
        person_type="anonymous",
        first_seen_at=func.now(),
        last_seen_at=func.now(),
        total_visits=1,
        confidence_avg=payload.confidence_avg
    )
    
    db.add(new_profile)
    db.commit()
    db.refresh(new_profile)
    return new_profile

# LUỒNG 2: Nhân viên tạo khách hàng chính thức tại quầy (Thêm khách hàng)
def create_customer(db: Session, payload: CustomerCreate) -> Customer:
    # 1. Kiểm tra số điện thoại và Email
    if payload.phone and db.query(Customer).filter(Customer.phone == payload.phone).first():
        raise HTTPException(status_code=400, detail="Số điện thoại này đã được đăng ký.")

    if payload.email and db.query(Customer).filter(Customer.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email này đã được đăng ký.")

    # 2. Tạo record Khách hàng
    customer_data = payload.model_dump(exclude={"person_profile_id", "captured_avatar_url"})
    if payload.captured_avatar_url:
        customer_data["avatar_url"] = payload.captured_avatar_url

    new_customer = Customer(
        customer_code=get_next_customer_code(db),
        **customer_data,
        status="active" 
    )
    db.add(new_customer)
    db.flush() # Lưu tạm để lấy new_customer.id

    # 3. Logic xử lý PersonProfile và Identity
    if payload.person_profile_id:
        # TH1: Khách đã bị camera bắt dạng ẩn danh trước đó
        person_profile = db.query(PersonProfile).filter(PersonProfile.id == payload.person_profile_id).first()
        if not person_profile:
            db.rollback()
            raise HTTPException(status_code=404, detail="Không tìm thấy dữ liệu khuôn mặt ẩn danh này.")
        # Kiểm tra xem hồ sơ này đã được định danh cho khách khác chưa
        existing_identity = db.query(CustomerIdentity).filter(
            CustomerIdentity.person_profile_id == payload.person_profile_id
        ).first()
        
        if existing_identity:
            db.rollback()
            raise HTTPException(
                status_code=400, 
                detail="Khuôn mặt này đã được định danh cho một khách hàng khác trong hệ thống."
            )

        person_profile.person_type = "identified"

        #Kế thừa số lượt ghé thăm từ hồ sơ camera
        new_customer.total_visits = person_profile.total_visits
        
        identity = CustomerIdentity(
            person_profile_id=person_profile.id,
            customer_id=new_customer.id,
            identification_method="manual_at_counter",
            confidence_score=1.0,
            note="Định danh từ hồ sơ ẩn danh có sẵn"
        )
        db.add(identity)
    else:
        # TH2: Khách chưa từng bị camera bắt (vd: đăng ký qua mạng hoặc camera hỏng lúc vào)
        # Phải tự động tạo PersonProfile để camera có ID tracking về sau
        new_profile = PersonProfile(
            anonymous_code=generate_anonymous_code("USR"),
            person_type="identified",
            first_seen_at=func.now(),
            last_seen_at=func.now(),
            total_visits=0
        )
        db.add(new_profile)
        db.flush()

        identity = CustomerIdentity(
            person_profile_id=new_profile.id,
            customer_id=new_customer.id,
            identification_method="system_generated",
            confidence_score=1.0,
            note="Tạo tự động khi nhân viên thêm khách hàng mới"
        )
        db.add(identity)

    # 4. Commit toàn bộ transaction
    try:
        db.commit()
        db.refresh(new_customer)
        return new_customer
    except IntegrityError as e:
        db.rollback()
        
        # Lấy thông báo lỗi gốc từ database (nếu có), nếu không thì lấy chuỗi lỗi mặc định
        error_message = str(e.orig) if hasattr(e, 'orig') else str(e)
        
        raise HTTPException(
            status_code=400, 
            detail=f"Lỗi dữ liệu đầu vào. Vui lòng kiểm tra lại. Chi tiết: {error_message}"
        )

# CUS-API-02-06-07: Xem danh sách khách hàng + lọc + tìm kiếm
def get_list_customers(
    db: Session, 
    search_query: str | None = None, 
    status_param: str | None = None, 
    gender_param: str | None = None,  # Thêm bộ lọc giới tính
    skip: int = 0, 
    limit: int = 100
) -> list[Customer]:
    
    # Khởi tạo câu truy vấn gốc
    query = db.query(Customer)
    
    # Đắp thêm điều kiện Lọc theo trạng thái 
    if status_param:
        if status_param not in ["active", "inactive"]: 
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Trạng thái lọc không hợp lệ. Chỉ chấp nhận 'hoạt động' hoặc 'ngừng hoạt động'." 
            )
        query = query.filter(Customer.status == status_param) 
        
    # Đắp điều kiện lọc giới tính (nếu có)
    if gender_param:
        query = query.filter(Customer.gender == gender_param)
        
    # Đắp điều kiện tìm kiếm từ khóa (nếu có)
    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter(
            or_(
                Customer.full_name.ilike(search_pattern),
                Customer.phone.ilike(search_pattern),
                Customer.email.ilike(search_pattern),
                Customer.customer_code.ilike(search_pattern)
            )
        )
        
    # thực thi truy vấn với phân trang
    return query.order_by(Customer.id.desc()).offset(skip).limit(limit).all()


def count_list_customers(
    db: Session, 
    search_query: str | None = None, 
    status_param: str | None = None,
    gender_param: str | None = None  # Thêm bộ lọc giới tính cho hàm đếm tổng
) -> int:
    
    # Khởi tạo câu đếm gốc
    query = db.query(Customer)
    
    # Điều kiện đếm phải khớp 100% với hàm lấy danh sách ở trên
    if status_param:
        query = query.filter(Customer.status == status_param)
        
    if gender_param:
        query = query.filter(Customer.gender == gender_param)
        
    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter(
            or_(
                Customer.full_name.ilike(search_pattern),
                Customer.phone.ilike(search_pattern),
                Customer.email.ilike(search_pattern),
                Customer.customer_code.ilike(search_pattern)
            )
        )
        
    return query.count()

# CUS-API-03: Xem chi tiết khách hàng
def get_customer_by_id(db: Session, customer_id: int) -> Customer:
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    
    # Nếu không tìm thấy, ném lỗi 404 để Router trả về cho Client
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Không tìm thấy khách hàng với ID {customer_id}"
        )
        
    return customer

# CUS-API-04: API cập nhật thông tin khách hàng
def update_customer(db: Session, customer_id: int, payload: CustomerUpdate) -> Customer:
    # Chỉ tìm kiếm các khách hàng chưa bị xóa mềm
    customer = db.query(Customer).filter(Customer.id == customer_id).first()

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy khách hàng với ID {customer_id}"
        )

    if customer.status == "inactive":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể cập nhật khách hàng đã bị ngừng hoạt động"
        )
    
    # Chuyển đổi payload thành dict, loại bỏ các trường không được truyền lên (PATCH)
    update_data = payload.model_dump(exclude_unset=True)
    
    # Kiểm tra trùng lặp số điện thoại (nếu có gửi lên và không rỗng)
    if "phone" in update_data and update_data["phone"]:
        phone_exists = db.query(Customer).filter(
            Customer.phone == update_data["phone"], 
            Customer.id != customer_id
        ).first()
        if phone_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Số điện thoại này đã được đăng ký bởi khách hàng khác."
            )

    # Kiểm tra trùng lặp email (nếu có gửi lên và không rỗng)
    if "email" in update_data and update_data["email"]:
        email_exists = db.query(Customer).filter(
            Customer.email == update_data["email"], 
            Customer.id != customer_id
        ).first()
        if email_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email này đã được đăng ký bởi khách hàng khác."
            )
            
    # Tiến hành cập nhật từng trường dữ liệu vào model
    for key, value in update_data.items():
        setattr(customer, key, value)
        
    try:
        db.commit()
        db.refresh(customer)
        return customer
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dữ liệu cập nhật không hợp lệ hoặc vi phạm ràng buộc hệ thống."
        )

# CUS-API-05: API xóa mềm khách hàng
def soft_delete_customer(db: Session, customer_id: int) -> dict:
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy khách hàng với ID {customer_id}."
        )
        
    if customer.status == "inactive":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể khóa. Khách hàng này đã ở trạng thái ngừng hoạt động."
        )
        
    # Thay đổi trạng thái thành 'inactive' thay vì xóa vật lý khỏi database
    customer.status = "inactive"
    db.commit()
    return {"message": "Xóa mềm khách hàng thành công."}

# CUS-API-08: API upload/lưu ảnh khách hàng
# Giới hạn kích thước file tải lên (3MB)
MAX_FILE_SIZE = 3 * 1024 * 1024  

def upload_customer_avatar(db: Session, customer_id: int, file: UploadFile) -> Customer:
    # 1. Kiểm tra khách hàng
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy khách hàng với ID {customer_id}."
        )
        
    if customer.status == "inactive":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể lưu ảnh. Khách hàng này đã bị ngừng hoạt động."
        )
    
    # 2. Validate định dạng và dung lượng
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File tải lên phải là hình ảnh.")

    file_bytes = file.file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Dung lượng ảnh vượt quá 3MB.")

    try:
        # XÓA ẢNH CŨ TRƯỚC KHI CẬP NHẬT
        if customer.avatar_url:
            # URL của Supabase thường có dạng:
            # https://[project_id].supabase.co/storage/v1/object/public/avatars/customers/best_capture_1_171542.jpg
            # cần cắt lấy phần "customers/best_capture_..." để gọi hàm remove()
            try:
                old_file_path = customer.avatar_url.split("/public/avatars/")[-1]
                supabase.storage.from_("avatars").remove([old_file_path])
            except Exception as delete_error:
                # Chỉ log cảnh báo nếu xóa thất bại (ví dụ file cũ đã bị ai đó xóa tay), 
                # không chặn quá trình lưu ảnh mới của Camera
                print(f"[Warning] Không thể dọn dẹp ảnh cũ trên Supabase: {delete_error}")

        # LƯU ẢNH "BEST CAPTURE" MỚI NHẤT
        file_extension = file.filename.split(".")[-1]
        # Đổi tên file để thể hiện rõ đây là ảnh tốt nhất từ AI thuật toán
        file_path = f"customers/best_capture_{customer_id}_{int(time.time())}.{file_extension}"
        
        supabase.storage.from_("avatars").upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": file.content_type}
        )
        
        # Lấy Public URL mới
        public_url = supabase.storage.from_("avatars").get_public_url(file_path)
        
        # Cập nhật vào DB
        customer.avatar_url = public_url
        db.commit()
        db.refresh(customer)
        
        return customer
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Lỗi hệ thống khi lưu ảnh Camera lên Cloud. Chi tiết: {str(e)}"
        )
    
# CUS-API-09: API lấy lịch sử ghé của khách
def get_customer_visit_history(db: Session, customer_id: int, skip: int = 0, limit: int = 100):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy khách hàng với ID {customer_id}."
        )
    # Join qua bảng customer_identities để tìm các phiên ghé thăm của khách hàng này
    visits = db.query(VisitSession).join(
        CustomerIdentity, 
        CustomerIdentity.person_profile_id == VisitSession.person_profile_id
    ).filter(
        CustomerIdentity.customer_id == customer_id
    ).order_by(VisitSession.entry_time.desc()).offset(skip).limit(limit).all()
    
    return visits

# CUS-API-10: API lấy lịch sử mua hàng của khách
def get_customer_order_history(db: Session, customer_id: int, skip: int = 0, limit: int = 100):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy khách hàng với ID {customer_id}."
        )
    # Truy vấn trực tiếp bảng orders bằng customer_id
    orders = db.query(Order).filter(
        Order.customer_id == customer_id
    ).order_by(Order.order_time.desc()).offset(skip).limit(limit).all()
    
    return orders