from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.dependencies import RequirePermission, get_admin_user, get_current_user
from app.database.session import get_db
from app.models.customer import Customer
from app.models.customer_identity import CustomerIdentity
from app.models.customer_segment import CustomerSegment
from app.models.customer_segment_member import CustomerSegmentMember
from app.models.order import Order
from app.models.person_profile import PersonProfile
from app.models.visit_sessions import VisitSession
from app.services.ai.ai_clustering_service import AICustomerClusteringService
from app.services.data_preparation_service import DataPreparationService
from app.services.feature_engineering_service import FeatureEngineeringService
from app.utils.response import success_response

router = APIRouter(prefix="/api/segments", tags=["Customer Segments"])

# API CHẠY AI PHÂN CỤM (Yêu cầu quyền Admin/Manager)
@router.post("/run-clustering")
def trigger_ai_clustering(
    n_clusters: int = Body(default=3, embed=True, ge=2, le=10),
    db: Session = Depends(get_db),
    admin_user=Depends(get_admin_user),
):
    """
    Kích hoạt luồng tổng hợp dữ liệu thật từ Database và chạy AI phân cụm.
    """
    try:
        ai_service = AICustomerClusteringService(db=db, n_clusters=n_clusters)
    
        data_prep = DataPreparationService(db)
        raw_df = data_prep.get_customer_feature_dataset()

        if raw_df.empty:
            return success_response(
                data={
                    "status": "warning",
                    "message": "Hiện chưa có dữ liệu hành vi khách hàng trong Database để AI học.",
                    "segments_created": 0,
                    "total_customers_processed": 0,
                    "features_used": [],
                },
                message="Chưa có dữ liệu phân cụm",
            )

        processed_df = FeatureEngineeringService.preprocess_features(raw_df)
        ai_service = AICustomerClusteringService(db, n_clusters=n_clusters)
        result = ai_service.run_clustering(processed_df, raw_df)

        return success_response(
            data=result,
            message=result.get("message", "Chạy phân cụm thành công"),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống pipeline AI: {exc}")

# BE-6: Lấy danh sách các Nhóm (Yêu cầu đăng nhập cơ bản)
@router.get("/")
def get_segments(
    db: Session = Depends(get_db),
    # Chỉ cần đăng nhập (có token hợp lệ) là xem được danh sách
    current_user=Depends(get_current_user),
):
    """
    Trả về danh sách 5 nhóm khách hàng cùng với JSON thống kê chi tiết.
    Dùng cho màn hình Dashboard tổng quan.
    """
    segments = db.query(CustomerSegment).order_by(CustomerSegment.id.asc()).all()
    data = []

    for segment in segments:
        rule = segment.rule_definition or {}
        stats = rule.get("statistics") or {}
        data.append({
            "id": segment.id,
            "segment_name": segment.segment_name,
            "description": segment.description,
            "member_count": int(stats.get("member_count") or 0),
            "avg_visits": float(stats.get("avg_visits") or 0),
            "avg_duration": float(stats.get("avg_duration") or 0),
            "avg_spent": float(stats.get("avg_spent") or 0),
            "created_at": segment.created_at,
        })

    return success_response(data=data, message="Lấy danh sách nhóm khách hàng thành công")

# BE-7: Lấy danh sách khách hàng theo Nhóm (Yêu cầu quyền xem chi tiết)
@router.get("/{segment_id}/members")
def get_segment_members(
    segment_id: int,
    db: Session = Depends(get_db),
    # Có thể yêu cầu quyền cao hơn một chút nếu muốn bảo mật SĐT/Email
    current_user=Depends(RequirePermission("customer.view")),
):
    """
    Trả về danh sách các khách hàng thuộc một nhóm cụ thể.
    Bao gồm cả thông tin (Tên, SĐT, Email) của khách hàng thật (nếu có).
    """
    segment = db.query(CustomerSegment).filter(CustomerSegment.id == segment_id).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhóm khách hàng này.")

    duration_sq = (
        db.query(
            VisitSession.person_profile_id.label("person_profile_id"),
            func.avg(VisitSession.duration_seconds).label("avg_duration_seconds"),
        )
        .group_by(VisitSession.person_profile_id)
        .subquery()
    )

    spent_sq = (
        db.query(
            Order.person_profile_id.label("person_profile_id"),
            func.sum(Order.total_amount).label("total_spent"),
        )
        .group_by(Order.person_profile_id)
        .subquery()
    )

    rows = (
        db.query(
            CustomerSegmentMember,
            PersonProfile,
            Customer,
            duration_sq.c.avg_duration_seconds,
            spent_sq.c.total_spent,
        )
        .join(PersonProfile, PersonProfile.id == CustomerSegmentMember.person_profile_id)
        .outerjoin(CustomerIdentity, CustomerIdentity.person_profile_id == PersonProfile.id)
        .outerjoin(Customer, Customer.id == CustomerIdentity.customer_id)
        .outerjoin(duration_sq, duration_sq.c.person_profile_id == PersonProfile.id)
        .outerjoin(spent_sq, spent_sq.c.person_profile_id == PersonProfile.id)
        .filter(CustomerSegmentMember.segment_id == segment_id)
        .order_by(CustomerSegmentMember.assigned_at.desc())
        .all()
    )

    data = [
        {
            "person_profile_id": profile.id,
            "anonymous_code": profile.anonymous_code,
            "person_type": profile.person_type,
            "customer_name": customer.full_name if customer else None,
            "customer_code": customer.customer_code if customer else None,
            "total_visits": int(profile.total_visits or 0),
            "avg_duration_seconds": int(avg_duration or 0),
            "total_spent": float(total_spent or 0),
            "score": member.score,
            "assigned_at": member.assigned_at,
        }
        for member, profile, customer, avg_duration, total_spent in rows
    ]

    return success_response(data=data, message="Lấy danh sách khách hàng trong nhóm thành công")
