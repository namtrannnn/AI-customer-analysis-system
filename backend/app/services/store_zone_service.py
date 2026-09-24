from sqlalchemy.orm import Session
from app.models.store_zone import StoreZone

def get_zone_by_type(db: Session, zone_type: str = None):
    # Lấy từ DB
    if zone_type:
        zone = db.query(StoreZone).filter(StoreZone.zone_type == zone_type).first()
    else:
        zone = db.query(StoreZone).first()

    # Xử lý Logic: Nếu chưa ai cấu hình trong DB, trả về tọa độ mặc định
    if not zone:
        default_polygon = [
            {"x": 0.6, "y": 0.5},
            {"x": 1.0, "y": 0.5},
            {"x": 1.0, "y": 1.0},
            {"x": 0.6, "y": 1.0}
        ]
        return {
            "zone_type": zone_type or "cashier",
            "polygon": default_polygon
        }

    return {
        "id": zone.id,
        "zone_type": zone.zone_type,
        "polygon": zone.polygon
    }