"""
Zone & Tracking Router — BE-17, BE-19, BE-24
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from typing import Any
from pydantic import BaseModel, Field

from app.database.session import get_db
from app.schemas.zone_schema import (
    ZoneCreate, ZoneUpdate, ZoneResponse,
    MovementTrackResponse, ZoneVisitResponse, ZoneHeatmapResponse,
)
from app.schemas.response_schema import StandardResponse
from app.services import zone_service as services
from app.services.ai.roi_service import roi_service
from app.utils.response import success_response
from app.core.dependencies import RequirePermission

router = APIRouter(prefix="/api/zones", tags=["Zones & Tracking"])


# ─── Check point (AI-11 debug) ────────────────────────────────────────────────

class CheckPointRequest(BaseModel):
    x: float = Field(..., ge=0.0, le=1.0, description="Tọa độ X tương đối (0..1)")
    y: float = Field(..., ge=0.0, le=1.0, description="Tọa độ Y tương đối (0..1)")


class CheckPointResponse(BaseModel):
    x: float
    y: float
    zone_id: int | None
    zone_name: str | None
    zone_type: str | None
    color: str | None
    is_inside: bool


@router.post("/check-point", response_model=StandardResponse[CheckPointResponse])
def check_point_in_zones(
    payload: CheckPointRequest,
    db: Session = Depends(get_db),
    current_user=Depends(RequirePermission("camera.manage")),
):
    """
    AI-11 Debug: Kiểm tra điểm (x, y) thuộc zone nào.
    Dùng để test ROI trực tiếp trên UI.
    """
    zones_db = services.get_all_zones(db)
    zones = [
        {"id": z.id, "zone_name": z.zone_name, "zone_type": z.zone_type,
         "color": z.color, "polygon": z.polygon or []}
        for z in zones_db
    ]

    result = roi_service.find_zone_for_point(payload.x, payload.y, zones)

    # Lấy thêm zone_type và color nếu tìm thấy
    zone_type = None
    color = None
    if result.zone_id:
        matched = next((z for z in zones if z["id"] == result.zone_id), None)
        if matched:
            zone_type = matched.get("zone_type")
            color = matched.get("color")

    return success_response(
        data=CheckPointResponse(
            x=payload.x,
            y=payload.y,
            zone_id=result.zone_id,
            zone_name=result.zone_name,
            zone_type=zone_type,
            color=color,
            is_inside=result.is_inside,
        ),
        message="Kiểm tra điểm thành công",
    )


# ─── Zone CRUD ────────────────────────────────────────────────────────────────

@router.get("/heatmap", response_model=StandardResponse[ZoneHeatmapResponse])
def get_zone_heatmap(
    start_date: str | None = Query(None, description="YYYY-MM-DD"),
    end_date: str | None = Query(None, description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user=Depends(RequirePermission("camera.manage")),
):
    """
    BE-2 & BE-3: Lấy dữ liệu Heatmap thống kê chi tiêu thời gian và lượt ghé theo từng vùng.
    Min-max scale 0-100% để hiển thị màu sắc tương ứng.
    """
    from datetime import datetime
    from sqlalchemy import func
    from app.models.store_zone import StoreZone
    from app.models.zone_visit import ZoneVisit

    # Lấy danh sách vùng thô
    zones = db.query(StoreZone).all()

    # Query thống kê zone_visits
    query = db.query(
        ZoneVisit.zone_id,
        func.count(ZoneVisit.id).label("total_visits"),
        func.sum(func.coalesce(ZoneVisit.duration_seconds, 0)).label("total_duration")
    )

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(ZoneVisit.enter_time >= start_dt)
        except ValueError:
            pass
    if end_date:
        try:
            end_dt = datetime.combine(datetime.strptime(end_date, "%Y-%m-%d"), datetime.max.time())
            query = query.filter(ZoneVisit.enter_time <= end_dt)
        except ValueError:
            pass

    stats_rows = query.group_by(ZoneVisit.zone_id).all()
    stats_map = {row.zone_id: (row.total_visits, int(row.total_duration or 0)) for row in stats_rows}

    # Tìm max duration
    durations = [val[1] for val in stats_map.values()]
    max_duration = max(durations) if durations else 0
    total_visits_sum = sum(val[0] for val in stats_map.values())

    items = []
    for z in zones:
        visits, duration = stats_map.get(z.id, (0, 0))
        intensity = (duration / max_duration) * 100.0 if max_duration > 0 else 0.0

        items.append({
            "zone_id": z.id,
            "zone_name": z.zone_name,
            "zone_type": z.zone_type,
            "polygon": z.polygon or [],
            "color": z.color,
            "total_visits": visits,
            "total_duration": duration,
            "intensity": round(intensity, 2)
        })

    return success_response(
        data={
            "items": items,
            "max_duration": max_duration,
            "total_visits_sum": total_visits_sum
        },
        message="Lấy dữ liệu Heatmap thành công"
    )


@router.get("/", response_model=StandardResponse[list[ZoneResponse]])
def get_zones(
    db: Session = Depends(get_db),
    current_user=Depends(RequirePermission("camera.manage")),
):
    zones = services.get_all_zones(db)
    return success_response(data=zones, message="Lấy danh sách vùng thành công")


@router.get("/{zone_id}", response_model=StandardResponse[ZoneResponse])
def get_zone(
    zone_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(RequirePermission("camera.manage")),
):
    zone = services.get_zone_by_id(db, zone_id)
    return success_response(data=zone, message="Lấy chi tiết vùng thành công")


@router.post("/", response_model=StandardResponse[ZoneResponse], status_code=status.HTTP_201_CREATED)
def create_zone(
    payload: ZoneCreate,
    db: Session = Depends(get_db),
    current_user=Depends(RequirePermission("camera.manage")),
):
    zone = services.create_zone(db, payload)
    return success_response(data=zone, message=f"Tạo vùng '{zone.zone_name}' thành công")


@router.patch("/{zone_id}", response_model=StandardResponse[ZoneResponse])
def update_zone(
    zone_id: int,
    payload: ZoneUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(RequirePermission("camera.manage")),
):
    zone = services.update_zone(db, zone_id, payload)
    return success_response(data=zone, message="Cập nhật vùng thành công")


@router.delete("/{zone_id}", response_model=StandardResponse[Any])
def delete_zone(
    zone_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(RequirePermission("camera.manage")),
):
    services.delete_zone(db, zone_id)
    return success_response(data=None, message="Xóa vùng thành công")


# ─── Zone Visits ──────────────────────────────────────────────────────────────

@router.get("/{zone_id}/visits", response_model=StandardResponse[list[ZoneVisitResponse]])
def get_zone_visits(
    zone_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(RequirePermission("camera.manage")),
):
    visits = services.get_zone_visits(db, zone_id=zone_id)
    return success_response(
        data=visits,
        message="Lấy lịch sử ghé vùng thành công",
        total=len(visits), skip=0, limit=len(visits),
    )
