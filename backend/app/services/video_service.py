import tempfile
from datetime import datetime
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session

from app.schemas.video_schema import VideoAnalysisResponse
from app.services.ai.video_pipeline_service import video_pipeline_service
from app.services.ai.movement_track_pipeline_service import movement_track_pipeline
from app.models.store_zone import StoreZone
from app.models.person_profile import PersonProfile
from app.models.visit_sessions import VisitSession
from app.models.movement_track import MovementTrack
from app.models.zone_visit import ZoneVisit


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_or_create_person_profile(db: Session, profile_id_str: str, confidence: float) -> PersonProfile:
    """Tìm hoặc tạo PersonProfile từ profile_id string (e.g. 'P_0001')."""
    existing = db.query(PersonProfile).filter(
        PersonProfile.anonymous_code == profile_id_str
    ).first()

    if existing:
        return existing

    profile = PersonProfile(
        anonymous_code=profile_id_str,
        person_type="anonymous",
        first_seen_at=datetime.now(),
        last_seen_at=datetime.now(),
        total_visits=1,
        confidence_avg=confidence,
    )
    db.add(profile)
    db.flush()  # lấy ID ngay
    return profile


def _save_tracking_to_db(
    db: Session,
    movement_result,
    track_to_profile: dict,
    profile_confidence: dict,
) -> int:
    """
    Lưu kết quả tracking vào DB:
    - person_profiles (tạo mới nếu chưa có)
    - visit_sessions (1 per track)
    - movement_tracks (N points per track)
    - zone_visits
    """
    saved_count = 0

    try:
        for track in movement_result.tracks:
            if not track.points:
                continue

            # Lấy profile_id từ track_to_profile mapping
            profile_id_str = track_to_profile.get(track.track_id)
            if not profile_id_str:
                profile_id_str = track.anonymous_id or f"TRK_{track.track_id:04d}"

            confidence = profile_confidence.get(profile_id_str, 0.0)

            # Tạo hoặc lấy PersonProfile
            person_profile = _get_or_create_person_profile(db, profile_id_str, confidence)

            # Tạo VisitSession
            entry = track.entry_time or datetime.now()
            session = VisitSession(
                person_profile_id=person_profile.id,
                entry_time=entry,
                exit_time=track.exit_time,
                duration_seconds=track.duration_seconds,
                is_identified=False,
            )
            db.add(session)
            db.flush()

            # Lưu track points vào movement_tracks
            for pt in track.points:
                mt = MovementTrack(
                    visit_session_id=session.id,
                    person_profile_id=person_profile.id,
                    camera_id=None,
                    zone_id=pt.zone_id,
                    position_x=round(pt.x, 4),
                    position_y=round(pt.y, 4),
                    tracked_at=pt.tracked_at,
                )
                db.add(mt)

            saved_count += 1

        # Lưu zone visits
        for zv in movement_result.zone_visits:
            profile_id_str = track_to_profile.get(zv.track_id, f"TRK_{zv.track_id:04d}")
            person_profile = db.query(PersonProfile).filter(
                PersonProfile.anonymous_code == profile_id_str
            ).first()

            if not person_profile:
                continue

            # Tìm session tương ứng
            session = db.query(VisitSession).filter(
                VisitSession.person_profile_id == person_profile.id
            ).order_by(VisitSession.entry_time.desc()).first()

            if not session:
                continue

            zone_visit = ZoneVisit(
                visit_session_id=session.id,
                person_profile_id=person_profile.id,
                zone_id=zv.zone_id,
                enter_time=zv.enter_time or datetime.now(),
                leave_time=zv.leave_time,
                duration_seconds=zv.duration_seconds,
            )
            db.add(zone_visit)

        db.commit()
        print(f"[video_service] Đã lưu {saved_count} tracks vào DB")

    except Exception as e:
        db.rollback()
        print(f"[video_service] Lỗi lưu tracking vào DB (bỏ qua): {e}")

    return saved_count


# ─── Main service ─────────────────────────────────────────────────────────────

async def process_temporary_video(
    file: UploadFile,
    db: Session | None = None,
) -> VideoAnalysisResponse:
    """
    1. Validate file
    2. Chạy video_pipeline (nhận diện khách)
    3. Nếu có zones trong DB → chạy movement_track_pipeline (tracking đường đi)
    4. Lưu kết quả tracking vào DB
    5. Trả về response
    """

    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(
            status_code=400,
            detail="Sai định dạng. File tải lên bắt buộc phải là video.",
        )

    MAX_SIZE = 50 * 1024 * 1024

    if file.size and file.size > MAX_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File quá lớn. Vui lòng upload video dưới 50MB.",
        )

    video_bytes = await file.read()

    if len(video_bytes) > MAX_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File quá lớn. Vui lòng upload video dưới 50MB.",
        )

    with tempfile.NamedTemporaryFile(delete=True, suffix=".mp4") as temp_video:
        temp_video.write(video_bytes)
        temp_video.flush()

        # ── 1. Video pipeline (nhận diện) ─────────────────────────────────────
        pipeline_result: dict = video_pipeline_service.process_video(temp_video.name)

        merged_profiles: list = pipeline_result.get("merged_profiles", [])
        track_to_profile: dict = pipeline_result.get("track_to_profile", {})
        total_customers = len(merged_profiles)

        # Map confidence per profile
        profile_confidence = {
            p.get("profile_id", ""): float(p.get("best_face_confidence") or 0.0)
            for p in merged_profiles
        }

        # Build detected_customers
        detected_customers = []
        for profile in merged_profiles:
            detected_customers.append({
                "anonymous_id": profile.get("profile_id", "UNKNOWN"),
                "customer_type": "new",
                "confidence": round(
                    float(profile.get("best_face_confidence") or 0.0), 2
                ),
            })

        # ── 2. Movement tracking (nếu có zones và có DB session) ──────────────
        if db is not None:
            zones_db = db.query(StoreZone).all()
            zones = [
                {
                    "id": z.id,
                    "zone_name": z.zone_name,
                    "zone_type": z.zone_type,
                    "polygon": z.polygon or [],
                    "color": z.color,
                }
                for z in zones_db
                if z.polygon and len(z.polygon) >= 3
            ]

            if zones:
                print(f"\n[video_service] Bắt đầu tracking với {len(zones)} zones...")
                try:
                    movement_result = movement_track_pipeline.process_video(
                        video_path=temp_video.name,
                        zones=zones,
                    )
                    _save_tracking_to_db(
                        db=db,
                        movement_result=movement_result,
                        track_to_profile=track_to_profile,
                        profile_confidence=profile_confidence,
                    )
                    print(
                        f"[video_service] Tracking xong: "
                        f"{movement_result.total_persons} tracks, "
                        f"{len(movement_result.zone_visits)} zone visits"
                    )
                except Exception as e:
                    print(f"[video_service] Tracking lỗi (bỏ qua): {e}")
            else:
                print("[video_service] Không có zone nào — bỏ qua tracking")

        # ── 3. Build response ─────────────────────────────────────────────────
        if total_customers == 0:
            message = "Không phát hiện người trong video theo cấu hình hiện tại."
        else:
            message = (
                f"Phân tích video thành công. Phát hiện {total_customers} người."
            )

        return VideoAnalysisResponse(
            total_customers=total_customers,
            new_customers=total_customers,
            returning_customers=0,
            detected_customers=detected_customers,
            message=message,
        )
