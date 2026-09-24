from datetime import datetime
import logging
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, text
from app.models.visit_sessions import VisitSession
from app.models.person_profile import PersonProfile
from app.models.customer_identity import CustomerIdentity
from app.models.customer import Customer
from app.models.face_embedding import FaceEmbedding
from app.schemas.cashier_schema import CreateOrderRequest, CustomerSummary, InStoreVisitorResponse, LinkProfileCustomerRequest
from app.models.order import Order

def get_active_customers_in_store(db: Session, skip: int = 0, limit: int = 10):
    # Tạo câu query cơ bản
    query = (
        db.query(
            VisitSession.id.label("session_id"),
            VisitSession.entry_time,
            PersonProfile.id.label("profile_id"),
            PersonProfile.anonymous_code,
            PersonProfile.person_type,
            FaceEmbedding.image_url.label("face_image_url"),
            Customer.id.label("customer_id"),
            Customer.full_name,
            Customer.phone,
            Customer.email
        )
        .join(PersonProfile, VisitSession.person_profile_id == PersonProfile.id)
        # Left join với face_embeddings để lấy ảnh mới nhất (lấy 1 ảnh đại diện)
        .outerjoin(FaceEmbedding, FaceEmbedding.person_profile_id == PersonProfile.id)
        # Left join với danh tính và khách hàng
        .outerjoin(CustomerIdentity, CustomerIdentity.person_profile_id == PersonProfile.id)
        .outerjoin(Customer, CustomerIdentity.customer_id == Customer.id)
        # Lọc những người chưa có exit_time (đang trong cửa hàng)
        .filter(VisitSession.exit_time.is_(None))
    )

    # Do 1 người có thể có nhiều face_embeddings, dùng distinct để tránh trùng lặp session_id
    query = query.distinct(VisitSession.id)

    # Đếm tổng số lượng (hỗ trợ phân trang cho frontend)
    total = query.count()

    # Phân trang
    results = query.offset(skip).limit(limit).all()

    # Format lại data chuẩn bị trả về Schema
    formatted_results = []
    for row in results:
        profile_info = {
            "id": row.profile_id,
            "anonymous_code": row.anonymous_code,
            "person_type": row.person_type,
            "face_image_url": row.face_image_url
        }
        
        customer_info = None
        if row.customer_id:
            customer_info = {
                "id": row.customer_id,
                "full_name": row.full_name,
                "phone": row.phone,
                "email": row.email
            }
        
        formatted_results.append({
            "session_id": row.session_id,
            "entry_time": row.entry_time,
            "profile": profile_info,
            "customer": customer_info
        })

    return {"total": total, "items": formatted_results}

logger = logging.getLogger(__name__)

def get_in_store_visitors(db: Session, skip: int = 0, limit: int = 10):
    try:
        query = (
            db.query(
                VisitSession.id.label("session_id"),
                VisitSession.entry_time,
                PersonProfile.id.label("profile_id"),
                PersonProfile.anonymous_code,
                PersonProfile.person_type,
                FaceEmbedding.image_url.label("face_image_url"),
                Customer.id.label("customer_id"),
                Customer.customer_code,
                Customer.full_name,
                Customer.phone
            )
            .join(PersonProfile, VisitSession.person_profile_id == PersonProfile.id)
            .outerjoin(FaceEmbedding, FaceEmbedding.person_profile_id == PersonProfile.id)
            .outerjoin(CustomerIdentity, CustomerIdentity.person_profile_id == PersonProfile.id)
            .outerjoin(Customer, CustomerIdentity.customer_id == Customer.id)
            .filter(VisitSession.exit_time.is_(None))
        )

        # Dùng distinct() để phòng trường hợp 1 profile có nhiều dòng face_embedding làm trùng lặp session
        query = query.distinct(VisitSession.id)

        total = query.count()
        records = query.offset(skip).limit(limit).all()

        # Build danh sách Pydantic object theo style person_profile_service
        items = []
        for row in records:
            customer_summary = None
            if row.customer_id:
                customer_summary = CustomerSummary(
                    id=row.customer_id,
                    customer_code=row.customer_code,
                    full_name=row.full_name,
                    phone=row.phone
                )
            
            visitor = InStoreVisitorResponse(
                session_id=row.session_id,
                entry_time=row.entry_time,
                profile_id=row.profile_id,
                anonymous_code=row.anonymous_code,
                person_type=row.person_type,
                face_image_url=row.face_image_url,
                customer=customer_summary
            )
            items.append(visitor)

        return {
            "total": total,
            "items": items
        }

    except Exception as e:
        logger.error(f"Error in get_in_store_visitors: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Đã xảy ra lỗi khi lấy danh sách khách hàng trong cửa hàng."
        )

def link_profile_to_existing_customer(db: Session, data: LinkProfileCustomerRequest):
    try:
        # 1. Kiểm tra profile có tồn tại không
        profile = db.query(PersonProfile).filter(PersonProfile.id == data.person_profile_id).first()
        if not profile:
            raise HTTPException(status_code=404, detail="Hồ sơ khách hàng không tồn tại.")

        # 2. Kiểm tra customer có tồn tại không
        customer = db.query(Customer).filter(Customer.id == data.customer_id).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Khách hàng (customer) không tồn tại.")

        # 3. Guard: Kiểm tra profile đã được định danh/link chưa
        existing_identity = db.query(CustomerIdentity).filter(
            CustomerIdentity.person_profile_id == data.person_profile_id
        ).first()
        
        if existing_identity:
            raise HTTPException(
                status_code=400, 
                detail="Hồ sơ này đã được định danh và liên kết với một khách hàng trong hệ thống."
            )

        # 4. Đổi person_type của profile sang "identified"
        profile.person_type = "identified"

        # 5. Insert CustomerIdentity
        new_identity = CustomerIdentity(
            person_profile_id=data.person_profile_id,
            customer_id=data.customer_id,
            identification_method="manual_at_counter",
            confidence_score=1.0
        )
        
        db.add(new_identity)
        
        # Commit transaction
        db.commit()
        db.refresh(new_identity)
        
        return {
            "identity_id": new_identity.id,
            "person_profile_id": new_identity.person_profile_id,
            "customer_id": new_identity.customer_id
        }

    except HTTPException:
        # Nếu là lỗi logic (HTTPException 400, 404) do mình raise -> rollback và ném tiếp
        db.rollback()
        raise
    except Exception as e:
        # Bắt lỗi hệ thống/DB khác
        db.rollback()
        logger.error(f"Error in link_profile_to_existing_customer: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Đã xảy ra lỗi khi liên kết hồ sơ với khách hàng."
        )

def create_store_order(db: Session, data: CreateOrderRequest):
    # 1. Chặn nếu không có bất kỳ định danh nào
    if not data.customer_id and not data.person_profile_id and not data.ai_session_code:
        raise HTTPException(status_code=400, detail="Phải cung cấp ít nhất customer_id, person_profile_id, hoặc ai_session_code")
    
    try:
        # 2. Tạo mã đơn hàng (Sequence)
        try:
            seq_val = db.execute(text("SELECT nextval('order_code_seq')")).scalar()
        except Exception:
            db.rollback()
            db.execute(text("CREATE SEQUENCE IF NOT EXISTS order_code_seq START 1"))
            db.commit()
            seq_val = db.execute(text("SELECT nextval('order_code_seq')")).scalar()

        order_code = f"ORD{seq_val:08d}"

        # 3. Lưu đơn hàng
        new_order = Order(
            customer_id=data.customer_id,
            person_profile_id=data.person_profile_id,
            ai_session_code=data.ai_session_code, # Lưu mã Live (VD: DEMO_1A2B_P_0006)
            
            order_code=order_code,
            total_amount=data.total_amount,
            item_summary=data.item_summary,
            payment_method=data.payment_method,
            order_time=data.order_time or datetime.now()
        )
        
        db.add(new_order)
        
        if data.customer_id:
            db.execute(
                text("UPDATE customers SET total_orders = COALESCE(total_orders, 0) + 1 WHERE id = :cid"),
                {"cid": data.customer_id}
            )
            
        db.commit()
        db.refresh(new_order)
        
        return new_order
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating order: {str(e)}")
        raise HTTPException(status_code=500, detail="Lỗi hệ thống khi tạo đơn hàng.")

import uuid
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from fastapi import HTTPException, status
# Đảm bảo đã import PersonProfile, Customer, CustomerIdentity, Order

def link_profile_to_existing_customer(db: Session, data: LinkProfileCustomerRequest):
    person_profile_id = data.person_profile_id
    customer_id = data.customer_id
    ai_session_code = data.ai_session_code

    # 1. Kiểm tra khách hàng gốc
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy thông tin khách hàng.")

    # =====================================================================
    # 2. XỬ LÝ KHUÔN MẶT AI (THUẬT TOÁN TÌM KIẾM THÔNG MINH BẢN VÁ MỚI)
    # =====================================================================
    profile = None
    
    # ƯU TIÊN 1: Tìm theo chuỗi ai_session_code (để tóm gọn các mã ANON_XXX AI đã tạo)
    if ai_session_code:
        profile = db.query(PersonProfile).filter(PersonProfile.anonymous_code == ai_session_code).first()

    # ƯU TIÊN 2: Nếu chuỗi không có, mà ID > 0 thì thử tìm theo ID
    if not profile and person_profile_id > 0:
        profile = db.query(PersonProfile).filter(PersonProfile.id == person_profile_id).first()

    # NẾU TÌM THẤY TỪ DB:
    if profile:
        profile.person_type = "identified"
        person_profile_id = profile.id  # Chốt ID thật của DB
        note_str = f"Liên kết thủ công từ mã {ai_session_code or person_profile_id}"
        
    # NẾU KHÔNG CÓ TRONG DB (Thực sự là khách đang Live bằng mã LIVE_...):
    else:
        temp_code = f"TEMP_{uuid.uuid4().hex[:8].upper()}"
        profile = PersonProfile(
            anonymous_code=temp_code,
            person_type="identified",
            first_seen_at=func.now(),
            last_seen_at=func.now(),
            total_visits=0
        )
        db.add(profile)
        db.flush() 
        
        # Gán mã chuẩn
        profile.anonymous_code = f"ANON_{int(profile.id):08d}"
        person_profile_id = profile.id  # Lấy ID vừa sinh ra
        note_str = f"LIVE_SESSION:{ai_session_code}"

    # 3. Tiến hành ghép nối (Identity)
    existing_link = db.query(CustomerIdentity).filter(
        CustomerIdentity.person_profile_id == person_profile_id,
        CustomerIdentity.customer_id == customer_id
    ).first()

    if not existing_link:
        new_identity = CustomerIdentity(
            person_profile_id=person_profile_id,
            customer_id=customer_id,
            identification_method="manual_at_counter",
            confidence_score=1.0,
            note=note_str
        )
        db.add(new_identity)
    
    # =====================================================================
    # 4. HỒI TỐ ĐƠN HÀNG LỠ TẠO
    # Bản vá: Không chỉ cập nhật customer_id, mà phải cập nhật ĐÚNG cả person_profile_id
    # =====================================================================
    updated_orders = db.query(Order).filter(
        or_(
            Order.person_profile_id == person_profile_id,
            Order.ai_session_code == ai_session_code if ai_session_code else False
        ),
        Order.customer_id.is_(None)
    ).update({
        "customer_id": customer_id,
        "person_profile_id": person_profile_id  # <--- Ép gán lại ID thật để đơn hàng 100% thuộc về Person này
    }, synchronize_session=False)

    # =====================================================================
    # 5. ĐỒNG BỘ THỐNG KÊ (TOTALS) CHO KHÁCH HÀNG SAU KHI LIÊN KẾT
    # =====================================================================
    
    # 5.1. Tính lại tổng đơn hàng và tổng tiền đã chi tiêu
    order_stats = db.query(
        func.count(Order.id),
        func.coalesce(func.sum(Order.total_amount), 0.0)
    ).filter(
        Order.customer_id == customer_id
    ).first()

    if order_stats:
        customer.total_orders = order_stats[0]
        customer.total_spent = order_stats[1]

    # 5.2. Tính lại tổng số lần ghé thăm (Gom tất cả các khuôn mặt của người này lại)
    visit_count = db.query(func.count(VisitSession.id)).join(
        CustomerIdentity, 
        CustomerIdentity.person_profile_id == VisitSession.person_profile_id
    ).filter(
        CustomerIdentity.customer_id == customer_id
    ).scalar()

    # Cập nhật số lần ghé (nếu chưa có visit nào thì mặc định là 1 cho lần Live hiện tại)
    customer.total_visits = visit_count if visit_count and visit_count > 0 else 1

    db.add(customer) # Lưu các con số mới vào bảng Customer

    try:
        db.commit()
        print(f"✅ Đã ghép Person {person_profile_id} vào Khách {customer.full_name}. Hồi tố {updated_orders} đơn. Tổng chi: {customer.total_spent}")
        return {"message": "Liên kết thành công", "customer_id": customer.id, "full_name": customer.full_name}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Lỗi hệ thống: {str(e)}")