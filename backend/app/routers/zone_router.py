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
    MovementTrackResponse, ZoneVisitResponse,
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
