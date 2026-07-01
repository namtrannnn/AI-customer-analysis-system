import os
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


def _build_track_to_profile(
    pipeline_result: dict,
    merged_profiles: list,
    detected_customers: list[dict],
) -> dict[int, str]:
    """
    Build track_id -> P_id using realtime pipeline identity mapping first.
    ROI runs on raw tracker records, but DB identity must follow realtime P_id,
    never create one person_profile per raw track.
    """
    allowed_profile_ids = {
        str(c.get("anonymous_id"))
        for c in detected_customers
        if c.get("anonymous_id")
    }
    if not allowed_profile_ids:
        allowed_profile_ids = {
            str(p.get("profile_id"))
            for p in merged_profiles
            if p.get("profile_id")
        }

    realtime_mapping = pipeline_result.get("track_to_profile") or {}
    if realtime_mapping:
        mapping: dict[int, str] = {}
        for track_id, profile_id in realtime_mapping.items():
            if not profile_id:
                continue
            profile_id = str(profile_id)
            if allowed_profile_ids and profile_id not in allowed_profile_ids:
                continue
            mapping[int(track_id)] = profile_id
        return mapping

    mapping: dict[int, str] = {}
    for profile in merged_profiles:
        profile_id = profile.get("profile_id", "")
        if allowed_profile_ids and profile_id not in allowed_profile_ids:
            continue
        for track_id in profile.get("merged_track_ids", []):
            mapping[int(track_id)] = profile_id
    return mapping


def _print_profile_track_merge_log(track_to_profile: dict[int, str]) -> None:
    profile_to_tracks: dict[str, list[int]] = {}
    for track_id, profile_id in track_to_profile.items():
        profile_to_tracks.setdefault(str(profile_id), []).append(int(track_id))

    print("\n[video_service] Person ID merge summary:")
    if not profile_to_tracks:
        print("  (empty)")
        return

    for profile_id, track_ids in sorted(profile_to_tracks.items()):
        track_ids = sorted(track_ids)
        print(f"  {profile_id} <= tracks {track_ids}")


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
    skipped_unassigned = 0
    try:
        for track in movement_result.tracks:
            if not track.points:
                continue

            profile_id_str = track_to_profile.get(track.track_id)
            if not profile_id_str:
                skipped_unassigned += 1
                continue

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
            profile_id_str = track_to_profile.get(zv.track_id)
            if not profile_id_str:
                continue

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
        print(
            f"[video_service] Đã lưu {saved_count} mapped tracks vào DB "
            f"(skip {skipped_unassigned} unassigned raw tracks)"
        )

    except Exception as e:
        import traceback

        db.rollback()
        print(f"[video_service] Lỗi lưu tracking: {e}")
        traceback.print_exc()

    return saved_count


def _build_detected_customers(pipeline_result: dict, merged_profiles: list) -> list[dict]:
    if merged_profiles:
        return [
            {
                "anonymous_id": p.get("profile_id", "UNKNOWN"),
                "customer_type": "new",
                "confidence": round(float(p.get("best_face_confidence") or 0.0), 2),
            }
            for p in merged_profiles
            if p.get("profile_id")
        ]

    detected_customers = pipeline_result.get("detected_customers") or []
    if detected_customers:
        return [
            {
                "anonymous_id": c.get("anonymous_id", "UNKNOWN"),
                "customer_type": c.get("customer_type", "new"),
                "confidence": float(c.get("confidence") or 0.0),
            }
            for c in detected_customers
        ]

    return [
        {
            "anonymous_id": p.get("profile_id", "UNKNOWN"),
            "customer_type": "new",
            "confidence": round(float(p.get("best_face_confidence") or 0.0), 2),
        }
        for p in merged_profiles
    ]


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

    temp_video_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_video:
            temp_video.write(video_bytes)
            temp_video.flush()
            os.fsync(temp_video.fileno())
            temp_video_path = temp_video.name

        # ── 1. Video pipeline: nhận diện khuôn mặt ───────────────────────────
        pipeline_result: dict = video_pipeline_service.process_video(
            temp_video_path,
            target_fps=15.0,
        )

        merged_profiles: list = pipeline_result.get("merged_profiles", [])
        debug_person_records: list = pipeline_result.get("debug_person_records", [])
        video_fps: float = pipeline_result.get("video_fps", 1.0)
        detected_customers = _build_detected_customers(pipeline_result, merged_profiles)
        total_customers = len(detected_customers)
        print(f"video_fps={video_fps}")

        if debug_person_records:
            frames = [r["frame_index"] for r in debug_person_records]

            print(f"min_frame={min(frames)}")
            print(f"max_frame={max(frames)}")
            print(f"total_records={len(frames)}")
        # Map track_id -> P_000X from realtime pipeline identity mapping.
        # This keeps ROI tracking aligned with realtime identity and prevents
        # raw tracker fragments from becoming person_profiles.
        track_to_profile = _build_track_to_profile(
            pipeline_result=pipeline_result,
            merged_profiles=merged_profiles,
            detected_customers=detected_customers,
        )
        profile_confidence = {
            p.get("profile_id", ""): float(p.get("best_face_confidence") or 0.0)
            for p in merged_profiles
        }
        profile_confidence.update({
            c["anonymous_id"]: float(c.get("confidence") or 0.0)
            for c in detected_customers
            if c.get("anonymous_id")
        })

        print(f"\n[video_service] track_to_profile: {track_to_profile}")
        _print_profile_track_merge_log(track_to_profile)
        print(f"[video_service] total debug_person_records: {len(debug_person_records)}")
        if debug_person_records:
            sample = debug_person_records[0]
            print(f"[video_service] Sample record: {sample}")
            fw = sample.get("frame_width", "N/A")
            fh = sample.get("frame_height", "N/A")
            print(f"[video_service] Frame size from record: {fw}x{fh}")

        # ── 2. Tracking dùng debug_person_records (cùng ByteTrack session) ────
        if db is not None and debug_person_records:
            tracking_records = [
                rec for rec in debug_person_records
                if int(rec.get("track_id", -1)) in track_to_profile
            ]
            skipped_records = len(debug_person_records) - len(tracking_records)
            print(
                f"[video_service] ROI input records: {len(tracking_records)} mapped, "
                f"{skipped_records} unassigned skipped"
            )

            zones_db = db.query(StoreZone).all()
            zones = [
                {"id": z.id, "zone_name": z.zone_name, "zone_type": z.zone_type,
                 "polygon": z.polygon or [], "color": z.color}
                for z in zones_db if z.polygon and len(z.polygon) >= 3
            ]

            if zones and tracking_records:
                print(f"\n[video_service] Tracking {len(tracking_records)} mapped records với {len(zones)} zones...")
                print(f"[video_service] Zones: {[z['zone_name'] for z in zones]}")

                try:
                    movement_result = process_detections_for_tracking(
                        debug_person_records=tracking_records,
                        zones=zones,
                        video_fps=video_fps,
                    )

                    print(f"\n[video_service] Tracking result:")
                    print(f"  total_raw_tracks: {movement_result.total_persons}")
                    print(f"  zone_visits: {len(movement_result.zone_visits)}")
                    for track in movement_result.tracks[:5]:
                        mapped = track_to_profile.get(track.track_id, "UNASSIGNED")
                        pts = track.points[:2] if track.points else []
                        print(f"  track_id={track.track_id} → {mapped} | {len(track.points)} points | sample={pts}")

                    # Gán anonymous_id → P_000X theo realtime identity mapping
                    for track in movement_result.tracks:
                        track.anonymous_id = track_to_profile.get(track.track_id)

                    print("[video_service] Bắt đầu lưu tracking vào DB...")
                    _save_tracking_to_db(db, movement_result, track_to_profile, profile_confidence)
                    print(
                        f"[video_service] Tracking xong: "
                        f"{movement_result.total_persons} mapped raw tracks, "
                        f"{len(movement_result.zone_visits)} zone visits"
                    )
                except Exception as e:
                    import traceback
                    print(f"[video_service] Tracking lỗi: {e}")
                    traceback.print_exc()
            elif not zones:
                print("[video_service] Không có zone hợp lệ — bỏ qua tracking")
            else:
                print("[video_service] Không có track nào đã map P_id — bỏ qua tracking")

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
    finally:
        if temp_video_path and os.path.exists(temp_video_path):
            try:
                os.remove(temp_video_path)
            except OSError:
                pass
