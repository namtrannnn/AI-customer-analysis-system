from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List

from app.database.session import get_db 
from app.models.customer_segment import CustomerSegment
from app.models.customer_segment_member import  CustomerSegmentMember
from app.schemas.customer_segment import CustomerSegmentResponse, CustomerSegmentMemberResponse

from app.services.data_preparation_service import DataPreparationService
from app.services.feature_engineering_service import FeatureEngineeringService
from app.services.ai.ai_clustering_service import AICustomerClusteringService

from app.core.dependencies import get_admin_user, get_current_user
from app.core.dependencies import RequirePermission

router = APIRouter(prefix="/api/segments", tags=["Customer Segments"])

# API CHẠY AI PHÂN CỤM (Yêu cầu quyền Admin/Manager)
@router.post("/run-clustering")
def trigger_ai_clustering(
    db: Session = Depends(get_db),
    admin_user = Depends(get_admin_user)
):
    """
    Kích hoạt luồng tổng hợp dữ liệu thật từ Database và chạy AI phân cụm.
    """
    try:
        data_prep_service = DataPreparationService(db)
        raw_df = data_prep_service.get_customer_feature_dataset()
        
        if raw_df.empty:
            return {"status": "warning", "message": "Hiện chưa có dữ liệu hành vi khách hàng trong Database để AI học."}

        processed_df = FeatureEngineeringService.preprocess_features(raw_df)
        
        ai_service = AICustomerClusteringService(db, n_clusters=5)
        result = ai_service.run_clustering(processed_df, raw_df)

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống pipeline AI: {str(e)}")

# BE-6: Lấy danh sách các Nhóm (Yêu cầu đăng nhập cơ bản)
@router.get("/", response_model=List[CustomerSegmentResponse])
def get_segments(
    db: Session = Depends(get_db),
    # Chỉ cần đăng nhập (có token hợp lệ) là xem được danh sách
    current_user = Depends(get_current_user) 
):
    """
    Trả về danh sách 5 nhóm khách hàng cùng với JSON thống kê chi tiết.
    Dùng cho màn hình Dashboard tổng quan.
    """
    segments = db.query(CustomerSegment).order_by(CustomerSegment.id.asc()).all()
    return segments

# BE-7: Lấy danh sách khách hàng theo Nhóm (Yêu cầu quyền xem chi tiết)
@router.get("/{segment_id}/members", response_model=List[CustomerSegmentMemberResponse])
def get_segment_members(
    segment_id: int, 
    db: Session = Depends(get_db),
    # Có thể yêu cầu quyền cao hơn một chút nếu muốn bảo mật SĐT/Email
    current_user = Depends(RequirePermission("customer.view")) 
):
    """
    Trả về danh sách các khách hàng thuộc một nhóm cụ thể.
    Bao gồm cả thông tin (Tên, SĐT, Email) của khách hàng thật (nếu có).
    """
    segment = db.query(CustomerSegment).filter(CustomerSegment.id == segment_id).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhóm khách hàng này.")

    members = (
        db.query(CustomerSegmentMember)
        .options(joinedload(CustomerSegmentMember.customer))
        .filter(CustomerSegmentMember.segment_id == segment_id)
        .all()
    )
    
    return members