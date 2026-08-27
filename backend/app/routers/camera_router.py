from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import Any

from app.database.session import get_db
from app.schemas.camera_schema import CameraCreate, CameraUpdate, CameraResponse
from app.schemas.response_schema import StandardResponse
from app.services import camera_service as services
from app.utils.response import success_response
from app.core.dependencies import RequirePermission, get_current_user

router = APIRouter(prefix="/api/cameras", tags=["Camera Management"])


@router.get("/", response_model=StandardResponse[list[CameraResponse]])
def get_cameras(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Danh sách tất cả camera."""
    cameras = services.get_all_cameras(db)
    return success_response(data=cameras, message="Lấy danh sách camera thành công")


@router.get("/{camera_id}", response_model=StandardResponse[CameraResponse])
def get_camera(
    camera_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Chi tiết một camera."""
    camera = services.get_camera_by_id(db, camera_id)
    return success_response(data=camera, message="Lấy chi tiết camera thành công")


@router.post("/", response_model=StandardResponse[CameraResponse], status_code=status.HTTP_201_CREATED)
def create_camera(
    payload: CameraCreate,
    db: Session = Depends(get_db),
    current_user=Depends(RequirePermission("camera.manage")),
):
    """Thêm camera mới."""
    camera = services.create_camera(db, payload)
    return success_response(data=camera, message=f"Đã thêm camera '{camera.camera_name}'")


@router.patch("/{camera_id}", response_model=StandardResponse[CameraResponse])
def update_camera(
    camera_id: int,
    payload: CameraUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(RequirePermission("camera.manage")),
):
    """Cập nhật thông tin camera."""
    camera = services.update_camera(db, camera_id, payload)
    return success_response(data=camera, message="Cập nhật camera thành công")


@router.delete("/{camera_id}", response_model=StandardResponse[Any])
def delete_camera(
    camera_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(RequirePermission("camera.manage")),
):
    """Xóa camera."""
    services.delete_camera(db, camera_id)
    return success_response(data=None, message="Đã xóa camera thành công")
