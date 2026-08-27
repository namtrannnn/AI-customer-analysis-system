from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.camera import Camera
from app.schemas.camera_schema import CameraCreate, CameraUpdate


def get_all_cameras(db: Session) -> list[Camera]:
    return db.query(Camera).order_by(Camera.id.desc()).all()


def get_camera_by_id(db: Session, camera_id: int) -> Camera:
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy camera ID {camera_id}",
        )
    return camera


def create_camera(db: Session, payload: CameraCreate) -> Camera:
    # Kiểm tra tên camera trùng
    exists = db.query(Camera).filter(Camera.camera_name == payload.camera_name).first()
    if exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên camera đã tồn tại trong hệ thống.",
        )
    camera = Camera(**payload.model_dump())
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


def update_camera(db: Session, camera_id: int, payload: CameraUpdate) -> Camera:
    camera = get_camera_by_id(db, camera_id)
    update_data = payload.model_dump(exclude_unset=True)

    # Kiểm tra tên trùng nếu có đổi tên
    if "camera_name" in update_data and update_data["camera_name"]:
        exists = db.query(Camera).filter(
            Camera.camera_name == update_data["camera_name"],
            Camera.id != camera_id,
        ).first()
        if exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tên camera đã tồn tại trong hệ thống.",
            )

    for key, value in update_data.items():
        setattr(camera, key, value)

    camera.updated_at = func.now()
    db.commit()
    db.refresh(camera)
    return camera


def delete_camera(db: Session, camera_id: int) -> None:
    camera = get_camera_by_id(db, camera_id)
    db.delete(camera)
    db.commit()
