from datetime import time
import os
import shutil

from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, UploadFile, status

from app.models.customer import Customer
from app.schemas.customer_schema import AnonymousCreate, CustomerCreate, CustomerUpdate
from backend.app.models.customer_identity import CustomerIdentity
from backend.app.models.order import Order
from backend.app.models.person_profile import PersonProfile
from backend.app.models.visit_sessions import VisitSession



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
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Lỗi dữ liệu đầu vào. Vui lòng kiểm tra lại.")

# CUS-API-02: Xem danh sách khách hàng
def get_list_customers(db: Session, skip: int = 0, limit: int = 100) -> list[Customer]:
    # Trả về danh sách, sắp xếp theo ID giảm dần (khách mới nhất lên đầu)
    return db.query(Customer)\
             .order_by(Customer.id.desc())\
             .offset(skip)\
             .limit(limit)\
             .all()