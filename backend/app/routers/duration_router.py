# Router cho phần Báo cáo Thời gian lưu trú (PB05)
# Thêm comment chi tiết bằng tiếng Việt để dễ đọc và bảo trì.

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional

from app.database.session import get_db
from app.models.visit_sessions import VisitSession
from app.models.person_profile import PersonProfile
from app.models.customer import Customer
from app.models.customer_identity import CustomerIdentity
from app.models.camera import Camera
from app.models.visit_detection import VisitDetection
from app.schemas.response_schema import StandardResponse
from app.schemas.duration_schema import (
    VisitDurationDetail,
    DurationStatsResponse,
    DurationTrendItem,
    DistributionBucket
)

router = APIRouter(prefix="/api/durations", tags=["Stay Time Analytics"])

def _build_filtered_sessions_query(
    db: Session,
    start_date: Optional[str],
    end_date: Optional[str],
    camera_id: Optional[int]
):
    """
    Hàm phụ trợ xây dựng câu truy vấn VisitSession kèm các bộ lọc ngày và camera.
    Sử dụng distinct để tránh trùng lặp dòng khi join.
    """
    # Khởi tạo truy vấn kết nối bảng VisitSession và PersonProfile để lấy mã anonymous_code
    query = db.query(VisitSession).join(
        PersonProfile, PersonProfile.id == VisitSession.person_profile_id
    )

    # Lọc theo ngày bắt đầu (>= 00:00:00 của ngày đó)
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(VisitSession.entry_time >= start_dt)
        except ValueError:
            pass

    # Lọc theo ngày kết thúc (<= 23:59:59 của ngày đó)
    if end_date:
        try:
            end_dt = datetime.strptime(end_date + " 23:59:59", "%Y-%m-%d %H:%M:%S")
            query = query.filter(VisitSession.entry_time <= end_dt)
        except ValueError:
            pass

    # Lọc theo camera_id: Cần join với bảng visit_detections
    if camera_id is not None:
        query = query.join(
            VisitDetection, VisitDetection.visit_session_id == VisitSession.id
        ).filter(VisitDetection.camera_id == camera_id)

    return query.distinct()


@router.get("/cameras", response_model=StandardResponse[List[dict]])
def get_cameras_list(db: Session = Depends(get_db)):
    """
    API lấy danh sách toàn bộ camera để hiển thị lên dropdown của bộ lọc FE.
    """
    cameras = db.query(Camera).filter(Camera.status == "active").all()
    data = [{"id": c.id, "camera_name": c.camera_name} for c in cameras]
    return StandardResponse(status="success", message="Lấy danh sách camera thành công", data=data)


@router.get("/visits", response_model=StandardResponse[List[VisitDurationDetail]])
def get_visit_durations(
    start_date: Optional[str] = Query(None, description="Định dạng YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Định dạng YYYY-MM-DD"),
    camera_id: Optional[int] = Query(None, description="ID của camera cần lọc"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    db: Session = Depends(get_db)
):
    """
    API lấy danh sách chi tiết các lượt ghé thăm và thời lượng ở lại của khách hàng.
    """
    # Tạo truy vấn gốc
    base_query = _build_filtered_sessions_query(db, start_date, end_date, camera_id)

    # Thực hiện Left Join với Customer để lấy thông tin định danh (nếu có)
    # Sắp xếp lượt mới nhất lên đầu trang
    sessions = (
        base_query.outerjoin(CustomerIdentity, CustomerIdentity.person_profile_id == VisitSession.person_profile_id)
        .outerjoin(Customer, Customer.id == CustomerIdentity.customer_id)
        .order_by(VisitSession.entry_time.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    data = []
    for s in sessions:
        # Lấy tên và ảnh đại diện nếu đã định danh
        customer_name = None
        customer_avatar = None
        
        # Truy vấn thông tin khách hàng liên kết
        identity = db.query(CustomerIdentity).filter(CustomerIdentity.person_profile_id == s.person_profile_id).first()
        if identity and identity.customer:
            customer_name = identity.customer.full_name
            customer_avatar = identity.customer.avatar_url

        # Lấy mã anonymous_code
        profile = db.query(PersonProfile).filter(PersonProfile.id == s.person_profile_id).first()
        anonymous_id = profile.anonymous_code if profile else "UNKNOWN"

        # Nếu chưa định danh nhưng có ảnh từ camera thì dùng làm avatar
        if not customer_avatar and profile and profile.face_image_url:
            customer_avatar = profile.face_image_url

        data.append(
            VisitDurationDetail(
                id=s.id,
                anonymous_id=anonymous_id,
                customer_name=customer_name,
                customer_avatar=customer_avatar,
                entry_time=s.entry_time,
                exit_time=s.exit_time,
                duration_seconds=s.duration_seconds,
                is_identified=s.is_identified
            )
        )

    return StandardResponse(
        status="success",
        message="Lấy danh sách thời lượng lưu trú thành công",
        data=data
    )


@router.get("/stats", response_model=StandardResponse[DurationStatsResponse])
def get_duration_stats(
    start_date: Optional[str] = Query(None, description="Định dạng YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Định dạng YYYY-MM-DD"),
    camera_id: Optional[int] = Query(None, description="ID của camera cần lọc"),
    db: Session = Depends(get_db)
):
    """
    API tổng hợp chỉ số KPI lưu trú và xu hướng trung bình theo từng ngày.
    """
    query = _build_filtered_sessions_query(db, start_date, end_date, camera_id)
    sessions = query.all()

    total_visits = len(sessions)
    durations = [s.duration_seconds for s in sessions if s.duration_seconds is not None]
    
    avg_duration = sum(durations) / len(durations) if durations else 0.0
    max_duration = max(durations) if durations else 0

    # Phân nhóm xu hướng lưu trú trung bình theo ngày bằng Python
    # Giúp tương thích hoàn hảo giữa SQLite và PostgreSQL không lo lỗi hàm định dạng ngày
    trend_map = {}
    for s in sessions:
        date_str = s.entry_time.strftime("%Y-%m-%d")
        if date_str not in trend_map:
            trend_map[date_str] = {"duration_sum": 0, "count": 0}
        
        if s.duration_seconds is not None:
            trend_map[date_str]["duration_sum"] += s.duration_seconds
            trend_map[date_str]["count"] += 1
        else:
            trend_map[date_str]["count"] += 1

    trend = []
    for date_str, stats in sorted(trend_map.items()):
        avg_dur = stats["duration_sum"] / stats["count"] if stats["count"] > 0 else 0.0
        trend.append(
            DurationTrendItem(
                date=date_str,
                avg_duration_seconds=round(avg_dur, 2),
                visit_count=stats["count"]
            )
        )

    data = DurationStatsResponse(
        avg_duration_seconds=round(avg_duration, 2),
        total_visits=total_visits,
        max_duration_seconds=max_duration,
        trend=trend
    )

    return StandardResponse(
        status="success",
        message="Lấy thống kê lưu trú thành công",
        data=data
    )


@router.get("/distribution", response_model=StandardResponse[List[DistributionBucket]])
def get_duration_distribution(
    start_date: Optional[str] = Query(None, description="Định dạng YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Định dạng YYYY-MM-DD"),
    camera_id: Optional[int] = Query(None, description="ID của camera cần lọc"),
    db: Session = Depends(get_db)
):
    """
    API phân nhóm tần số khách ở lại cửa hàng (Histogram) để vẽ biểu đồ cột.
    """
    query = _build_filtered_sessions_query(db, start_date, end_date, camera_id)
    sessions = query.all()

    # Định nghĩa các khoảng thời gian (Buckets)
    buckets = {
        "Dưới 1 phút": 0,
        "1 - 5 phút": 0,
        "5 - 10 phút": 0,
        "10 - 30 phút": 0,
        "Trên 30 phút": 0,
    }

    for s in sessions:
        dur = s.duration_seconds
        if dur is None:
            continue
        
        if dur < 60:
            buckets["Dưới 1 phút"] += 1
        elif dur < 300:
            buckets["1 - 5 phút"] += 1
        elif dur < 600:
            buckets["5 - 10 phút"] += 1
        elif dur < 1800:
            buckets["10 - 30 phút"] += 1
        else:
            buckets["Trên 30 phút"] += 1

    data = [
        DistributionBucket(bucket_name=name, visit_count=count)
        for name, count in buckets.items()
    ]

    return StandardResponse(
        status="success",
        message="Lấy phân bố tần suất lưu trú thành công",
        data=data
    )
