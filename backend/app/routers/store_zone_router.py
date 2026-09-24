from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional

from app.database.session import get_db
from app.schemas.store_zone_schema import StoreZoneResponse
from app.services import store_zone_service

router = APIRouter()

@router.get("", response_model=StoreZoneResponse)
def get_store_zone(
    type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    API lấy tọa độ khu vực (VD: Quầy thu ngân). 
    Request: GET /api/store-zones?type=cashier
    """
    # Gọi Service xử lý nghiệp vụ
    result = store_zone_service.get_zone_by_type(db=db, zone_type=type)
    return result