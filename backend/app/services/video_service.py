import tempfile
from datetime import datetime
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session

from app.schemas.video_schema import VideoAnalysisResponse
from app.services.ai.video_pipeline_service import video_pipeline_service
from app.services.ai.track_from_detection_service import process_detections_for_tracking
from app.models.store_zone import StoreZone
from app.models.person_profile import PersonProfile
from app.models.visit_sessions import VisitSession
from app.models.movement_track import MovementTrack
from app.models.zone_visit import ZoneVisit


def _build_track_to_profile(merged_profiles: list) -> dict[int, str]:
    """merged_profiles[].merged_track_ids → {track_id: "P_000X"}"""
    mapping: dict[int, str] = {}
    for profile in merged_profiles:
        profile_id = profile.get("profile_id", "")
        for track_id in profile.get("merged_track_ids", []):
            mapping[int(track_id)] = profile_id
    return mapping


def _get_or_create_person_profile(db, anonymous_code, confidence):
    existing = db.query(PersonProfile).filter(
        PersonProfile.anonymous_code == anonymous_code
    ).first()
    if existing:
        return existing
    profile = PersonProfile(
        anonymous_code=anonymous_code,
        person_type="anonymous",
        first_seen_at=datetime.now(),
        last_seen_at=datetime.now(),
        total_visits=1,
        confidence_avg=confidence,
    )
    db.add(profile)
    db.flush()
    return profile


def _save_tracking_to_db(db, movement_result, track_to_profile, profile_confidence):
    saved_count = 0
    try:
        for track in movement_result.tracks:
            if not track.points:
                continue

            profile_id_str = track_to_profile.get(track.track_id, f"TRK_{track.track_id:04d}")
            print(f"[save_tracking] Saving track_id={track.track_id} → {profile_id_str} ({len(track.points)} pts)")
            confidence = profile_confidence.get(profile_id_str, 0.0)
            person_profile = _get_or_create_person_profile(db, profile_id_str, confidence)

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

            for pt in track.points:
                db.add(MovementTrack(
                    visit_session_id=session.id,
                    person_profile_id=person_profile.id,
                    zone_id=pt.zone_id,
                    position_x=round(pt.x, 4),
                    position_y=round(pt.y, 4),
                    tracked_at=pt.tracked_at,
                ))

            saved_count += 1

        for zv in movement_result.zone_visits:
            profile_id_str = track_to_profile.get(zv.track_id, f"TRK_{zv.track_id:04d}")
            person_profile = db.query(PersonProfile).filter(
                PersonProfile.anonymous_code == profile_id_str
            ).first()
            if not person_profile:
                continue

            session = (
                db.query(VisitSession)
                .filter(VisitSession.person_profile_id == person_profile.id)
                .order_by(VisitSession.entry_time.desc())
                .first()
            )
            if not session:
                continue

            db.add(ZoneVisit(
                visit_session_id=session.id,
                person_profile_id=person_profile.id,
                zone_id=zv.zone_id,
                enter_time=zv.enter_time or datetime.now(),
                leave_time=zv.leave_time,
                duration_seconds=zv.duration_seconds,
            ))

        db.commit()
        print(f"[video_service] Đã lưu {saved_count} tracks vào DB")

    except Exception as e:
        db.rollback()
        print(f"[video_service] Lỗi lưu tracking: {e}")

    return saved_count


async def process_temporary_video(
    file: UploadFile,
    db: Session | None = None,
) -> VideoAnalysisResponse:
    
    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Sai định dạng. Phải là file video.")

    MAX_SIZE = 50 * 1024 * 1024
    if file.size and file.size > MAX_SIZE:
        raise HTTPException(status_code=413, detail="File quá lớn. Vui lòng upload video dưới 50MB.")

    video_bytes = await file.read()
    if len(video_bytes) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="File quá lớn. Vui lòng upload video dưới 50MB.")

    with tempfile.NamedTemporaryFile(delete=True, suffix=".mp4") as temp_video:
        temp_video.write(video_bytes)
        temp_video.flush()

        # ── 1. Video pipeline: nhận diện khuôn mặt ───────────────────────────
        pipeline_result: dict = video_pipeline_service.process_video(
            temp_video.name,
            target_fps=5.0,
        )

        merged_profiles: list = pipeline_result.get("merged_profiles", [])
        debug_person_records: list = pipeline_result.get("debug_person_records", [])
        video_fps: float = pipeline_result.get("video_fps", 1.0)
        total_customers = len(merged_profiles)
        print(f"video_fps={video_fps}")

        if debug_person_records:
            frames = [r["frame_index"] for r in debug_person_records]

            print(f"min_frame={min(frames)}")
            print(f"max_frame={max(frames)}")
            print(f"total_records={len(frames)}")
        # Map track_id → P_000X dùng merged_track_ids (cùng ByteTrack session)
        track_to_profile = _build_track_to_profile(merged_profiles)
        profile_confidence = {
            p.get("profile_id", ""): float(p.get("best_face_confidence") or 0.0)
            for p in merged_profiles
        }

        print(f"\n[video_service] track_to_profile: {track_to_profile}")
        print(f"[video_service] total debug_person_records: {len(debug_person_records)}")
        if debug_person_records:
            sample = debug_person_records[0]
            print(f"[video_service] Sample record: {sample}")
            fw = sample.get("frame_width", "N/A")
            fh = sample.get("frame_height", "N/A")
            print(f"[video_service] Frame size from record: {fw}x{fh}")

        detected_customers = [
            {
                "anonymous_id": p.get("profile_id", "UNKNOWN"),
                "customer_type": "new",
                "confidence": round(float(p.get("best_face_confidence") or 0.0), 2),
            }
            for p in merged_profiles
        ]

        # ── 2. Tracking dùng debug_person_records (cùng ByteTrack session) ────
        if db is not None and debug_person_records:
            zones_db = db.query(StoreZone).all()
            zones = [
                {"id": z.id, "zone_name": z.zone_name, "zone_type": z.zone_type,
                 "polygon": z.polygon or [], "color": z.color}
                for z in zones_db if z.polygon and len(z.polygon) >= 3
            ]

            if zones:
                print(f"\n[video_service] Tracking {len(debug_person_records)} records với {len(zones)} zones...")
                print(f"[video_service] Zones: {[z['zone_name'] for z in zones]}")

                try:
                    movement_result = process_detections_for_tracking(
                        debug_person_records=debug_person_records,
                        zones=zones,
                        video_fps=video_fps,
                    )

                    print(f"\n[video_service] Tracking result:")
                    print(f"  total_persons (tracks): {movement_result.total_persons}")
                    print(f"  zone_visits: {len(movement_result.zone_visits)}")
                    for track in movement_result.tracks[:5]:
                        mapped = track_to_profile.get(track.track_id, f"TRK_{track.track_id:04d}")
                        pts = track.points[:2] if track.points else []
                        print(f"  track_id={track.track_id} → {mapped} | {len(track.points)} points | sample={pts}")

                    # Gán anonymous_id → P_000X nếu map được
                    for track in movement_result.tracks:
                        track.anonymous_id = track_to_profile.get(
                            track.track_id, f"TRK_{track.track_id:04d}"
                        )
                    # THÊM ĐOẠN NÀY
                    print("\n================ TRACK CHECK ================")
                    for track in movement_result.tracks:
                        print(
                            f"{track.anonymous_id} | "
                            f"track_id={track.track_id} | "
                            f"zones={track.zones_visited}"
                        )
                    print("=============================================\n")
                    print("[video_service] Bắt đầu lưu tracking vào DB...")
                    _save_tracking_to_db(db, movement_result, track_to_profile, profile_confidence)
                    print(
                        f"[video_service] Tracking xong: "
                        f"{movement_result.total_persons} tracks, "
                        f"{len(movement_result.zone_visits)} zone visits"
                    )
                except Exception as e:
                    import traceback
                    print(f"[video_service] Tracking lỗi: {e}")
                    traceback.print_exc()
            else:
                print("[video_service] Không có zone hợp lệ — bỏ qua tracking")

        if total_customers == 0:
            message = "Không phát hiện người trong video theo cấu hình hiện tại."
        else:
            message = f"Phân tích video thành công. Phát hiện {total_customers} người."

        return VideoAnalysisResponse(
            total_customers=total_customers,
            new_customers=total_customers,
            returning_customers=0,
            detected_customers=detected_customers,
            message=message,
        )
