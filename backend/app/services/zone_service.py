"""
Zone Service — BE-17, BE-19, BE-20, BE-21, BE-24
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status

from app.models.store_zone import StoreZone
from app.models.zone_visit import ZoneVisit
from app.models.movement_track import MovementTrack
from app.models.person_profile import PersonProfile
from app.models.visit_sessions import VisitSession
from app.models.customer import Customer
from app.models.customer_identity import CustomerIdentity
from app.schemas.zone_schema import ZoneCreate, ZoneUpdate

# Palette màu mặc định — xoay vòng khi tạo zone mới
ZONE_COLORS = [
    "#3b82f6", "#10b981", "#f59e0b", "#ef4444",
    "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16",
]

# ─── Zone CRUD ────────────────────────────────────────────────────────────────

def get_all_zones(db: Session) -> list[StoreZone]:
    return db.query(StoreZone).order_by(StoreZone.created_at.desc()).all()


def get_zone_by_id(db: Session, zone_id: int) -> StoreZone:
    zone = db.query(StoreZone).filter(StoreZone.id == zone_id).first()
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy vùng theo dõi với ID {zone_id}"
        )
    return zone


def create_zone(db: Session, payload: ZoneCreate) -> StoreZone:
    # Tự động chọn màu nếu không truyền
    color = payload.color
    if not color or color == "#3b82f6":
        used = {z.color for z in db.query(StoreZone.color).all()}
        color = next((c for c in ZONE_COLORS if c not in used), ZONE_COLORS[0])

    zone = StoreZone(
        zone_name=payload.zone_name.strip(),
        zone_type=payload.zone_type,
        description=payload.description,
        polygon=[p.model_dump() for p in payload.polygon],
        color=payload.color or color,
        total_visits=0,
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone


def update_zone(db: Session, zone_id: int, payload: ZoneUpdate) -> StoreZone:
    zone = get_zone_by_id(db, zone_id)

    update_data = payload.model_dump(exclude_unset=True)

    # Serialize polygon list[PointSchema] → list[dict]
    if "polygon" in update_data and update_data["polygon"]:
        update_data["polygon"] = [p.model_dump() for p in payload.polygon]

    for key, value in update_data.items():
        setattr(zone, key, value)

    db.commit()
    db.refresh(zone)
    return zone


def delete_zone(db: Session, zone_id: int) -> None:
    zone = get_zone_by_id(db, zone_id)
    db.delete(zone)
    db.commit()


# ─── Movement Tracks ──────────────────────────────────────────────────────────

def get_movement_tracks(
    db: Session,
    person_id: str | None = None,
    zone_id: int | None = None,
    limit: int = 50,
) -> list[dict]:
    """
    Cách 2: Group theo person_profile_id — mỗi person = 1 đường đi liên tục.
    Merge tất cả track_id của cùng 1 người thành 1 đường đi duy nhất.
    """
    # Lấy danh sách person_profile_id có trong movement_tracks
    person_query = (
        db.query(
            MovementTrack.person_profile_id,
            func.min(MovementTrack.tracked_at).label("entry_time"),
            func.max(MovementTrack.tracked_at).label("exit_time"),
            func.count(MovementTrack.id).label("point_count"),
        )
        .group_by(MovementTrack.person_profile_id)
        .order_by(func.min(MovementTrack.tracked_at).desc())
        .limit(limit)
    )

    if zone_id:
        person_query = person_query.filter(MovementTrack.zone_id == zone_id)

    persons = person_query.all()

    colors = ZONE_COLORS
    result = []

    for idx, person_row in enumerate(persons):
        profile = db.query(PersonProfile).filter(
            PersonProfile.id == person_row.person_profile_id
        ).first()

        if not profile:
            continue

        # Filter theo person_id nếu có
        if person_id and person_id.lower() not in profile.anonymous_code.lower():
            continue

        # Lấy TẤT CẢ points của người này (tất cả track_id)
        # Sort theo tracked_at để đường đi theo thứ tự thời gian
        points_raw = (
            db.query(MovementTrack)
            .filter(MovementTrack.person_profile_id == person_row.person_profile_id)
            .order_by(MovementTrack.tracked_at)
            .all()
        )

        points = [
            {
                "x": p.position_x or 0.0,
                "y": p.position_y or 0.0,
                "zone_id": p.zone_id,
                "tracked_at": p.tracked_at,
            }
            for p in points_raw
        ]
        # print("\n================ POINT ZONES ================")
        # print(profile.anonymous_code)

        # print([p["zone_id"] for p in points])

        # print("============================================")
        zones_visited = []

        for p in points:
            zid = p["zone_id"]

            if zid is None:
                continue

            if not zones_visited or zones_visited[-1] != zid:
                zones_visited.append(zid)

        entry = person_row.entry_time
        exit_ = person_row.exit_time
        duration = int((exit_ - entry).total_seconds()) if entry and exit_ else None

        # Check if this person is identified
        identity = db.query(CustomerIdentity).filter(
            CustomerIdentity.person_profile_id == person_row.person_profile_id
        ).first()

        customer_id_val = None
        customer_name_val = None
        customer_avatar_val = None

        if identity:
            customer = db.query(Customer).filter(Customer.id == identity.customer_id).first()
            if customer:
                customer_id_val = customer.id
                customer_name_val = customer.full_name
                customer_avatar_val = customer.avatar_url

        result.append({
            "id": person_row.person_profile_id,  # dùng profile_id làm id
            "person_profile_id": person_row.person_profile_id,
            "anonymous_id": profile.anonymous_code,
            "visit_session_id": person_row.person_profile_id,  # compat với FE
            "color": colors[idx % len(colors)],
            "entry_time": entry,
            "exit_time": exit_,
            "duration_seconds": duration,
            "zones_visited": zones_visited,
            "points": points,
            "customer_id": customer_id_val,
            "customer_name": customer_name_val,
            "customer_avatar": customer_avatar_val,
        })

    return result


def get_track_by_session_id(db: Session, session_id: int) -> dict:
    """Lấy chi tiết 1 track theo visit_session_id."""
    tracks = get_movement_tracks(db=db, limit=1000)
    for t in tracks:
        if t["visit_session_id"] == session_id:
            return t
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Không tìm thấy track với session ID {session_id}"
    )


# ─── Zone Visits ──────────────────────────────────────────────────────────────

def get_zone_visits(db: Session, zone_id: int | None = None) -> list[dict]:
    """Trả về danh sách zone visits, join thêm anonymous_code và zone_name."""
    query = (
        db.query(ZoneVisit, PersonProfile.anonymous_code, StoreZone.zone_name)
        .join(PersonProfile, PersonProfile.id == ZoneVisit.person_profile_id)
        .join(StoreZone, StoreZone.id == ZoneVisit.zone_id)
        .order_by(ZoneVisit.enter_time.desc())
    )

    if zone_id:
        query = query.filter(ZoneVisit.zone_id == zone_id)

    rows = query.limit(200).all()

    return [
        {
            "id": visit.id,
            "zone_id": visit.zone_id,
            "zone_name": zone_name,
            "person_profile_id": visit.person_profile_id,
            "anonymous_id": anonymous_code,
            "enter_time": visit.enter_time,
            "leave_time": visit.leave_time,
            "duration_seconds": visit.duration_seconds,
        }
        for visit, anonymous_code, zone_name in rows
    ]
