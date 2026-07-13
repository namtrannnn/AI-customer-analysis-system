import os
import time
import tempfile
import uuid
from datetime import datetime
from typing import Any, Callable
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session

from app.schemas.video_schema import VideoAnalysisResponse
from app.services.ai.video_pipeline_live_stream_service import video_pipeline_service
from app.services.ai.streaming.streaming_result_publisher import StreamingResultPublisher
from app.services.ai.streaming.streaming_video_pipeline_service import (
    StreamingVideoPipelineService,
    ProcessingJobState,
)
from app.services.ai.track_from_detection_service import process_detections_for_tracking
from app.services.ai.global_customer_identity_service import (
    global_customer_identity_service,
    SessionIdentityResult,
)
from app.models.face_embedding import FaceEmbedding
from app.models.store_zone import StoreZone
from app.models.person_profile import PersonProfile
from app.models.visit_sessions import VisitSession
from app.models.movement_track import MovementTrack
from app.models.zone_visit import ZoneVisit
from app.utils.supabase_client import supabase


video_result_publisher = StreamingResultPublisher()

streaming_video_pipeline_service = StreamingVideoPipelineService(
    pipeline_service=video_pipeline_service,
    publisher=video_result_publisher,
    detection_sink=None,
    job_state_sink=None,
)


def subscribe_video_processing(
    processing_session_id: str,
    callback: Callable[[dict, Any], None],
) -> None:
    video_result_publisher.subscribe(str(processing_session_id), callback)


def unsubscribe_video_processing(
    processing_session_id: str,
    callback: Callable[[dict, Any], None],
) -> None:
    video_result_publisher.unsubscribe(str(processing_session_id), callback)


def get_video_processing_job(job_id: str) -> ProcessingJobState | None:
    return streaming_video_pipeline_service.get_job(str(job_id))


def serialize_video_processing_job(
    state: ProcessingJobState | None,
) -> dict | None:
    if state is None:
        return None
    return {
        "processing_session_id": state.session_id,
        "job_id": state.job_id,
        "video_path": state.video_path,
        "status": state.status.value,
        "processed_frames": state.processed_frames,
        "total_frames": state.total_frames,
        "progress_percent": state.progress_percent,
        "processing_fps": state.processing_fps,
        "error": state.error,
        "started_at": state.started_at,
        "completed_at": state.completed_at,
    }


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


def _upload_face_to_supabase(local_path: str, profile_id: str) -> str | None:
    """Upload face crop image to Supabase Storage, return public URL."""
    try:
        if not local_path or not os.path.exists(local_path):
            return None
        ext = os.path.splitext(local_path)[1] or ".jpg"
        file_path = f"person_profiles/face_{profile_id}_{int(time.time())}{ext}"
        with open(local_path, "rb") as f:
            file_bytes = f.read()
        supabase.storage.from_("avatars").upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": "image/jpeg"}
        )
        public_url = supabase.storage.from_("avatars").get_public_url(file_path)
        print(f"[video_service] Uploaded face for {profile_id}: {public_url}")
        return public_url
    except Exception as e:
        print(f"[video_service] Failed to upload face for {profile_id}: {e}")
        return None


def _save_tracking_to_db(db, movement_result, track_to_profile, profile_confidence, merged_profiles=None):
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

            # Upload best face image to Supabase if available and not yet uploaded
            if merged_profiles and not person_profile.face_image_url:
                for mp in merged_profiles:
                    if mp.get("profile_id") == profile_id_str and mp.get("best_face_image_path"):
                        face_url = _upload_face_to_supabase(
                            mp["best_face_image_path"], profile_id_str
                        )
                        if face_url:
                            person_profile.face_image_url = face_url
                        break

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


def _build_detected_customers(pipeline_result: dict, merged_profiles: list, db: Session | None = None) -> list[dict]:
    raw_list = []
    if merged_profiles:
        raw_list = [
            {
                "anonymous_id": p.get("profile_id", "UNKNOWN"),
                "customer_type": "new",
                "confidence": round(float(p.get("best_face_confidence") or 0.0), 2),
            }
            for p in merged_profiles
            if p.get("profile_id")
        ]
    else:
        detected_customers = pipeline_result.get("detected_customers") or []
        if detected_customers:
            raw_list = [
                {
                    "anonymous_id": c.get("anonymous_id", "UNKNOWN"),
                    "customer_type": c.get("customer_type", "new"),
                    "confidence": float(c.get("confidence") or 0.0),
                }
                for c in detected_customers
            ]

    # Build dictionary of profile_id -> base64 crop image from video
    profile_avatars = {}
    for p in merged_profiles:
        pid = p.get("profile_id")
        path = p.get("best_face_image_path")
        if pid and path and os.path.exists(path):
            import base64
            try:
                with open(path, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode("utf-8")
                    profile_avatars[pid] = f"data:image/jpeg;base64,{encoded}"
            except Exception as e:
                print(f"[video_service] Error encoding base64 avatar: {e}")

    # Set default avatar from video crop
    for item in raw_list:
        item["customer_avatar"] = profile_avatars.get(item["anonymous_id"])
        item["customer_id"] = None
        item["customer_name"] = None

    # Enrich with database customer information
    if db is not None:
        from app.models.customer import Customer
        from app.models.customer_identity import CustomerIdentity
        for item in raw_list:
            anon_id = item["anonymous_id"]
            cust_profile = (
                db.query(Customer)
                .join(CustomerIdentity, CustomerIdentity.customer_id == Customer.id)
                .join(PersonProfile, PersonProfile.id == CustomerIdentity.person_profile_id)
                .filter(PersonProfile.anonymous_code == anon_id)
                .first()
            )
            if cust_profile:
                item["customer_id"] = cust_profile.id
                item["customer_name"] = cust_profile.full_name
                if cust_profile.avatar_url:
                    item["customer_avatar"] = cust_profile.avatar_url
                item["customer_type"] = "returning"

    return raw_list


def _identity_results_by_session_pid(
    results: list[SessionIdentityResult],
) -> dict[str, SessionIdentityResult]:
    return {
        str(item.session_profile_id): item
        for item in results
    }


def _build_track_to_person_profile_id(
    track_to_session_profile: dict[int, str],
    identity_results: list[SessionIdentityResult],
) -> dict[int, int]:
    by_session_pid = _identity_results_by_session_pid(
        identity_results
    )
    mapping: dict[int, int] = {}

    for track_id, session_pid in track_to_session_profile.items():
        result = by_session_pid.get(str(session_pid))
        if result is not None:
            mapping[int(track_id)] = int(
                result.person_profile_id
            )

    return mapping


def _find_customer_for_person_profile(
    db: Session,
    person_profile_id: int,
):
    try:
        from app.models.customer import Customer
        from app.models.customer_identity import CustomerIdentity

        return (
            db.query(Customer)
            .join(
                CustomerIdentity,
                CustomerIdentity.customer_id == Customer.id,
            )
            .filter(
                CustomerIdentity.person_profile_id
                == int(person_profile_id)
            )
            .first()
        )
    except Exception as exc:
        print(
            "[video_service] Không enrich được Customer cho "
            f"person_profile_id={person_profile_id}: {exc}"
        )
        return None


def _upload_identity_avatars(
    *,
    db: Session,
    identity_results: list[SessionIdentityResult],
) -> None:
    """
    Upload best face trước khi temp_face_dir bị xóa.
    Mỗi PersonProfile chỉ upload khi chưa có face_image_url.
    """
    handled_profile_ids: set[int] = set()

    for result in identity_results:
        person_profile_id = int(result.person_profile_id)
        if person_profile_id in handled_profile_ids:
            continue
        handled_profile_ids.add(person_profile_id)

        person = db.get(PersonProfile, person_profile_id)
        if person is None or person.face_image_url:
            continue

        local_path = result.face_image_path
        if not local_path or not os.path.exists(local_path):
            continue

        public_url = _upload_face_to_supabase(
            local_path,
            str(person.anonymous_code),
        )
        if not public_url:
            continue

        person.face_image_url = public_url

        # Gắn URL vào embedding mới nhất chưa có image_url.
        latest_embedding = (
            db.query(FaceEmbedding)
            .filter(
                FaceEmbedding.person_profile_id
                == person_profile_id
            )
            .order_by(FaceEmbedding.captured_at.desc())
            .first()
        )
        if (
            latest_embedding is not None
            and not latest_embedding.image_url
        ):
            latest_embedding.image_url = public_url

    db.flush()


def _encode_current_face_as_data_url(local_path: str | None) -> str | None:
    if not local_path or not os.path.exists(local_path):
        return None

    import base64

    try:
        with open(local_path, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode("utf-8")
        return f"data:image/jpeg;base64,{encoded}"
    except Exception as exc:
        print(f"[video_service] Không encode được current face: {exc}")
        return None


def _build_global_detected_customers(
    *,
    db: Session | None,
    identity_results: list[SessionIdentityResult],
) -> list[dict]:
    customers: list[dict] = []
    emitted_profile_ids: set[int] = set()

    for result in identity_results:
        person_profile_id = int(result.person_profile_id)
        if person_profile_id in emitted_profile_ids:
            continue
        emitted_profile_ids.add(person_profile_id)

        person = (
            db.get(PersonProfile, person_profile_id)
            if db is not None
            else None
        )
        linked_customer = (
            _find_customer_for_person_profile(
                db,
                person_profile_id,
            )
            if db is not None
            else None
        )

        customer_type = result.customer_type
        customer_name = None
        customer_id = None

        # Trong màn hình đang phân tích, luôn ưu tiên khuôn mặt vừa cắt từ
        # video hiện tại. Avatar DB chỉ là hồ sơ lưu trữ/fallback.
        current_video_avatar = _encode_current_face_as_data_url(
            result.face_image_path
        )
        stored_profile_avatar = (
            person.face_image_url
            if person is not None
            else None
        )
        identified_customer_avatar = None

        if linked_customer is not None:
            customer_id = linked_customer.id
            customer_name = linked_customer.full_name
            identified_customer_avatar = linked_customer.avatar_url

        avatar = (
            current_video_avatar
            or identified_customer_avatar
            or stored_profile_avatar
        )

        customers.append({
            "session_profile_id": result.session_profile_id,
            "person_profile_id": person_profile_id,
            "anonymous_id": result.anonymous_code,
            "customer_type": customer_type,
            "total_visits": (
                int(person.total_visits or 0)
                if person is not None
                else result.total_visits
            ),
            "first_seen_at": (
                person.first_seen_at.isoformat()
                if person is not None
                and person.first_seen_at is not None
                else None
            ),
            "last_seen_at": (
                person.last_seen_at.isoformat()
                if person is not None
                and person.last_seen_at is not None
                else None
            ),
            "confidence": round(
                float(
                    person.confidence_avg
                    if person is not None
                    and person.confidence_avg is not None
                    else result.confidence
                ),
                4,
            ),
            "matched_similarity": round(
                float(result.matched_similarity),
                4,
            ),
            "matched_margin": round(
                float(result.matched_margin),
                4,
            ),
            # Avatar dùng cho card/overlay trong lần phân tích hiện tại.
            "customer_avatar": avatar,
            "current_video_avatar": current_video_avatar,
            # Avatar đã lưu của profile toàn cục, dùng cho trang hồ sơ.
            "stored_profile_avatar": stored_profile_avatar,
            "identified_customer_avatar": identified_customer_avatar,
            "customer_id": customer_id,
            "customer_name": customer_name,
        })

    return customers


def _save_global_visits_and_tracking(
    *,
    db: Session,
    movement_result,
    track_to_person_profile_id: dict[int, int],
) -> int:
    """
    Một PersonProfile chỉ có một VisitSession cho một video,
    kể cả người đó có nhiều raw track_id.
    """
    tracks_by_person: dict[int, list] = {}
    skipped_tracks = 0

    for track in movement_result.tracks:
        person_profile_id = track_to_person_profile_id.get(
            int(track.track_id)
        )
        if person_profile_id is None or not track.points:
            skipped_tracks += 1
            continue

        tracks_by_person.setdefault(
            int(person_profile_id),
            [],
        ).append(track)

    visit_by_person: dict[int, VisitSession] = {}

    try:
        for person_profile_id, tracks in tracks_by_person.items():
            entries = [
                track.entry_time
                for track in tracks
                if track.entry_time is not None
            ]
            exits = [
                track.exit_time
                for track in tracks
                if track.exit_time is not None
            ]

            entry_time = (
                min(entries)
                if entries
                else datetime.now()
            )
            exit_time = max(exits) if exits else None

            duration_seconds = None
            if exit_time is not None:
                duration_seconds = max(
                    0,
                    int(
                        (
                            exit_time - entry_time
                        ).total_seconds()
                    ),
                )
            else:
                durations = [
                    int(track.duration_seconds or 0)
                    for track in tracks
                ]
                duration_seconds = (
                    max(durations) if durations else 0
                )

            visit = VisitSession(
                person_profile_id=person_profile_id,
                entry_time=entry_time,
                exit_time=exit_time,
                duration_seconds=duration_seconds,
                is_identified=False,
            )
            db.add(visit)
            db.flush()
            visit_by_person[person_profile_id] = visit

            for track in tracks:
                for point in track.points:
                    db.add(MovementTrack(
                        visit_session_id=visit.id,
                        person_profile_id=person_profile_id,
                        zone_id=point.zone_id,
                        position_x=round(point.x, 4),
                        position_y=round(point.y, 4),
                        tracked_at=point.tracked_at,
                    ))

        for zone_visit in movement_result.zone_visits:
            person_profile_id = (
                track_to_person_profile_id.get(
                    int(zone_visit.track_id)
                )
            )
            if person_profile_id is None:
                continue

            visit = visit_by_person.get(person_profile_id)
            if visit is None:
                continue

            db.add(ZoneVisit(
                visit_session_id=visit.id,
                person_profile_id=person_profile_id,
                zone_id=zone_visit.zone_id,
                enter_time=(
                    zone_visit.enter_time
                    or visit.entry_time
                ),
                leave_time=zone_visit.leave_time,
                duration_seconds=zone_visit.duration_seconds,
            ))

        db.commit()
        print(
            "[video_service] Đã lưu "
            f"{len(visit_by_person)} VisitSession toàn cục; "
            f"skip {skipped_tracks} raw tracks"
        )
        return len(visit_by_person)
    except Exception:
        db.rollback()
        raise


def _publish_global_identity_result(
    *,
    processing_session_id: str,
    job_id: str,
    identity_results: list[SessionIdentityResult],
    track_to_session_profile: dict[int, str],
) -> None:
    session_map = {
        item.session_profile_id: {
            "person_profile_id": item.person_profile_id,
            "anonymous_code": item.anonymous_code,
            "customer_type": item.customer_type,
            "total_visits": item.total_visits,
            "matched_similarity": item.matched_similarity,
        }
        for item in identity_results
    }

    track_map = {}
    for track_id, session_pid in track_to_session_profile.items():
        global_identity = session_map.get(str(session_pid))
        if global_identity is not None:
            track_map[str(track_id)] = {
                "session_profile_id": str(session_pid),
                **global_identity,
            }

    video_result_publisher.publish(
        processing_session_id,
        {
            "type": "global_identity_result",
            "processing_session_id": processing_session_id,
            "job_id": job_id,
            "session_profile_mapping": session_map,
            "track_identity_mapping": track_map,
        },
        None,
    )


async def process_temporary_video(
    file: UploadFile,
    db: Session | None = None,
    processing_session_id: str | None = None,
) -> VideoAnalysisResponse:
    
    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Sai định dạng. Phải là file video.")

    MAX_SIZE = 100 * 1024 * 1024
    if file.size and file.size > MAX_SIZE:
        raise HTTPException(status_code=413, detail="File quá lớn. Vui lòng upload video dưới 50MB.")

    video_bytes = await file.read()
    if len(video_bytes) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="File quá lớn. Vui lòng upload video dưới 50MB.")

    temp_video_path = None
    temp_face_dir = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_video:
            temp_video.write(video_bytes)
            temp_video.flush()
            os.fsync(temp_video.fileno())
            temp_video_path = temp_video.name

        # ── 1. Video pipeline: nhận diện khuôn mặt ───────────────────────────
        processing_session_id = processing_session_id or str(uuid.uuid4())
        temp_face_dir = tempfile.mkdtemp(prefix="pipeline_faces_")

        processing_job = streaming_video_pipeline_service.create_job(
            video_path=temp_video_path,
            session_id=processing_session_id,
        )

        print(
            f"[video_service] processing_session_id={processing_session_id} "
            f"job_id={processing_job.job_id}"
        )

        pipeline_result: dict = streaming_video_pipeline_service.start_job(
            processing_job.job_id,
            background=False,
            output_face_dir=temp_face_dir,
            target_fps=10.0,
            debug_video_path=None,
            stream_frame_dir=None,
            stream_emit_every_n_frames=1,
            stream_realtime_sleep=False,
            stream_send_annotated_frame=False,
        )

        merged_profiles: list = pipeline_result.get("merged_profiles", [])
        debug_person_records: list = pipeline_result.get("debug_person_records", [])
        video_fps: float = pipeline_result.get("video_fps", 1.0)

        # P_000X chỉ là ID trong session hiện tại.
        track_to_session_profile = _build_track_to_profile(
            pipeline_result=pipeline_result,
            merged_profiles=merged_profiles,
            detected_customers=[],
        )

        identity_results: list[SessionIdentityResult] = []
        track_to_person_profile_id: dict[int, int] = {}

        if db is not None:
            identity_results = (
                global_customer_identity_service
                .classify_pipeline_profiles(
                    db=db,
                    merged_profiles=merged_profiles,
                    seen_at=datetime.now(),
                    commit=False,
                )
            )

            _upload_identity_avatars(
                db=db,
                identity_results=identity_results,
            )
            db.commit()

            track_to_person_profile_id = (
                _build_track_to_person_profile_id(
                    track_to_session_profile,
                    identity_results,
                )
            )

            detected_customers = (
                _build_global_detected_customers(
                    db=db,
                    identity_results=identity_results,
                )
            )

            _publish_global_identity_result(
                processing_session_id=processing_session_id,
                job_id=processing_job.job_id,
                identity_results=identity_results,
                track_to_session_profile=track_to_session_profile,
            )
        else:
            # Không có DB thì chỉ trả P_id tạm trong video,
            # chưa thể phân loại Returning toàn cục.
            detected_customers = _build_detected_customers(
                pipeline_result,
                merged_profiles,
                db=None,
            )

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
        # Mapping trong pipeline: raw track_id -> P_id tạm của session.
        track_to_profile = track_to_session_profile
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

                    print(
                        "[video_service] Bắt đầu lưu VisitSession theo "
                        "person_profile_id toàn cục..."
                    )
                    _save_global_visits_and_tracking(
                        db=db,
                        movement_result=movement_result,
                        track_to_person_profile_id=(
                            track_to_person_profile_id
                        ),
                    )
                    print(
                        f"[video_service] Tracking xong: "
                        f"{movement_result.total_persons} raw tracks, "
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
            message = (
                f"Phân tích video thành công. Phát hiện {total_customers} người. "
                f"Session: {processing_session_id}; Job: {processing_job.job_id}"
            )

        new_customers = sum(
            1
            for item in detected_customers
            if item.get("customer_type") == "new"
        )
        returning_customers = sum(
            1
            for item in detected_customers
            if item.get("customer_type") == "returning"
        )

        return VideoAnalysisResponse(
            total_customers=total_customers,
            new_customers=new_customers,
            returning_customers=returning_customers,
            detected_customers=detected_customers,
            message=message,
        )
    finally:
        if temp_video_path and os.path.exists(temp_video_path):
            try:
                os.remove(temp_video_path)
            except OSError:
                pass

        if temp_face_dir and os.path.exists(temp_face_dir):
            try:
                import shutil
                shutil.rmtree(temp_face_dir, ignore_errors=True)
            except OSError:
                pass