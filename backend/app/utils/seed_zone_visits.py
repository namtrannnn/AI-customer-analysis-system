import random
from datetime import datetime, timedelta

# Import các models để SQLAlchemy đăng ký đầy đủ metadata
from app.models.customer import Customer
from app.models.person_profile import PersonProfile
from app.models.store_zone import StoreZone
from app.models.visit_sessions import VisitSession
from app.models.zone_visit import ZoneVisit

from app.database.session import SessionLocal

def seed():
    db = SessionLocal()

    # Xóa dữ liệu cũ nếu có
    db.query(ZoneVisit).delete()
    db.commit()

    # Zone IDs đã lấy từ DB
    zone_ids = [13, 14, 15, 16, 42, 43]
    
    # Danh sách cặp (visit_session_id, person_profile_id) hợp lệ từ DB
    valid_pairs = [
        (59, 50), (60, 51), (61, 52), (62, 53), (63, 54), (64, 55),
        (65, 50), (66, 51), (67, 52), (68, 53), (69, 54), (70, 55)
    ]

    # Phân phối thời gian ở lại khác nhau cho mỗi zone để tạo bản đồ nhiệt rõ rệt
    zone_weights = {
        13: {"visits": 35, "dur_range": (15, 45)},
        14: {"visits": 25, "dur_range": (120, 480)},
        15: {"visits": 30, "dur_range": (60, 180)},
        16: {"visits": 10, "dur_range": (10, 60)},
        42: {"visits": 20, "dur_range": (40, 120)},
        43: {"visits": 15, "dur_range": (30, 90)}
    }

    # Ngày hiện tại là 2026-07-14 theo local time của user
    base_date = datetime(2026, 7, 14, 12, 0, 0)

    count = 0
    for zone_id, weight in zone_weights.items():
        for _ in range(weight["visits"]):
            # Phân bố ngẫu nhiên trong vòng 10 ngày gần đây
            days_ago = random.randint(0, 9)
            hours_offset = random.randint(-8, 8)
            mins_offset = random.randint(0, 59)
            
            enter_time = base_date - timedelta(days=days_ago, hours=hours_offset, minutes=mins_offset)
            duration = random.randint(*weight["dur_range"])
            leave_time = enter_time + timedelta(seconds=duration)
            
            session_id, profile_id = random.choice(valid_pairs)
            
            visit = ZoneVisit(
                visit_session_id=session_id,
                person_profile_id=profile_id,
                zone_id=zone_id,
                enter_time=enter_time,
                leave_time=leave_time,
                duration_seconds=duration
            )
            db.add(visit)
            count += 1

    db.commit()
    print(f"[SEED SUCCESS] Da tao va cam ket {count} luot ghe tham zone (ZoneVisits) trong DB!")
    db.close()

if __name__ == "__main__":
    seed()
