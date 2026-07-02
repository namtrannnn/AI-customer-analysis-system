"""
Movement Track Router — BE-24
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.zone_schema import MovementTrackResponse, ZoneVisitResponse
from app.schemas.response_schema import StandardResponse
from app.services import zone_service as services
from app.utils.response import success_response
from app.core.dependencies import RequirePermission

router = APIRouter(prefix="/api/tracks", tags=["Movement Tracking"])


@router.get("/", response_model=StandardResponse[list[MovementTrackResponse]])
def get_tracks(
    person_id: str | None = Query(None, description="Lọc theo anonymous_code (fuzzy)"),
    zone_id: int | None = Query(None, description="Chỉ lấy track có ghé qua zone này"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(RequirePermission("camera.manage")),
):
    """
    Trả về danh sách movement tracks.
    Mỗi track gom nhóm theo visit_session — gồm list points + metadata.
    """
    tracks = services.get_movement_tracks(db, person_id=person_id, zone_id=zone_id, limit=limit)
    return success_response(
        data=tracks,
        message="Lấy dữ liệu tracking thành công",
        total=len(tracks), skip=0, limit=limit,
    )


@router.get("/{session_id}", response_model=StandardResponse[MovementTrackResponse])
def get_track_detail(
    session_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(RequirePermission("camera.manage")),
):
    """Lấy chi tiết 1 track theo visit_session_id."""
    track = services.get_track_by_session_id(db, session_id)
    return success_response(data=track, message="Lấy chi tiết track thành công")
