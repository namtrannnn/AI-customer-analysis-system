import asyncio
import cv2
import logging
import os
import shutil
import tempfile
import time
import numpy as np
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models.customer import Customer
from app.models.customer_identity import CustomerIdentity
from app.models.movement_track import MovementTrack
from app.models.person_profile import PersonProfile
from app.models.store_zone import StoreZone
from app.models.visit_detection import VisitDetection
from app.models.visit_sessions import VisitSession
from app.models.zone_visit import ZoneVisit
from app.services.ai.track_from_detection_service import process_detections_for_tracking
from app.services.ai.global_customer_identity_service import (
    global_customer_identity_service,
    SessionIdentityResult,
)
from app.services.processing_job_manager import processing_job_manager
from app.services.video_service_streaming_integrated import (
    streaming_video_pipeline_service,
    subscribe_video_processing,
    unsubscribe_video_processing,
)
from app.utils.supabase_client import supabase


MAX_VIDEO_SIZE = 50 * 1024 * 1024
logger = logging.getLogger(__name__)


def _build_track_to_profile(
    pipeline_result: dict,
    merged_profiles: list,
    detected_customers: list[dict],
) -> dict[int, str]:
    allowed_profile_ids = {
        str(customer.get("anonymous_id"))
        for customer in detected_customers
        if customer.get("anonymous_id")
    }
    if not allowed_profile_ids:
        allowed_profile_ids = {
            str(profile.get("profile_id"))
            for profile in merged_profiles
            if profile.get("profile_id")
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


def _upload_face_to_supabase(local_path: str, profile_id: str) -> str | None:
    try:
        if not local_path or not os.path.exists(local_path):
            return None
        ext = os.path.splitext(local_path)[1] or ".jpg"
        file_path = f"person_profiles/face_{profile_id}_{int(time.time())}{ext}"
        with open(local_path, "rb") as file:
            file_bytes = file.read()
        supabase.storage.from_("avatars").upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": "image/jpeg"},
        )
        public_url = supabase.storage.from_("avatars").get_public_url(file_path)
        print(f"[streaming_video_service] Uploaded face for {profile_id}: {public_url}")
        return public_url
    except Exception as exc:
        print(f"[streaming_video_service] Failed to upload face for {profile_id}: {exc}")
        return None


class StreamingVideoService:
    async def start_job(self, job_id: str) -> None:
        # Chuyển job sang running và đưa pipeline sync sang thread riêng.
        # FastAPI event loop vẫn rảnh để phục vụ status/WebSocket request khác.
        processing_job_manager.mark_running(job_id)
        try:
            await asyncio.to_thread(self._run_job_sync, job_id)
        except Exception as exc:
            processing_job_manager.mark_failed(job_id, str(exc))
        finally:
            processing_job_manager.cleanup_temp_file(job_id)

    def _run_job_sync(self, job_id: str) -> None:
        job = processing_job_manager.get_job(job_id)
        if not job:
            return

        # Context gồm các dữ liệu tạm của riêng job nay.
        # Cuối video context được dùng để đồng bộ PersonProfile/VisitSession/Detection.
        db = SessionLocal()
        output_face_dir = tempfile.mkdtemp(prefix=f"pipeline_faces_{job_id}_")
        started = time.perf_counter()
        frame_width, frame_height, source_fps = self._read_video_metadata(
            job.temp_video_path
        )
        context: dict[str, Any] = {
            "video_fps": source_fps,
            "frame_width": frame_width,
            "frame_height": frame_height,
            "profiles": {},
            "sessions": {},
            "session_bounds": {},
            "final_profile_ids": [],
            "realtime_detections": [],
            "detection_count": 0,
            "gallery": global_customer_identity_service._load_gallery(db),
            "early_identities": {},
        }

        try:
            ai_job = streaming_video_pipeline_service.create_job(
                video_path=job.temp_video_path,
                session_id=job.job_id,
            )
            job.ai_job_id = ai_job.job_id
            job.processing_session_id = ai_job.session_id
            logger.info(
                "Created AI pipeline job for BE job %s: ai_job_id=%s session_id=%s",
                job.job_id,
                ai_job.job_id,
                ai_job.session_id,
            )

            def on_pipeline_event(event: dict[str, Any], annotated_frame=None) -> None:
                # Cầu nối từ AI streaming callback sang BE job manager.
                # frame_result tạo progress/detection realtime; pipeline_error đánh dấu job failed.
                event_type = event.get("type")
                if event_type == "frame_result":
                    self._handle_ai_frame_result(job_id, db, job, context, event)
                    return
                if event_type == "pipeline_error":
                    message = str(event.get("error") or "Pipeline failed")
                    processing_job_manager.mark_failed(job_id, message)

            subscribe_video_processing(ai_job.session_id, on_pipeline_event)
            pipeline_result: dict = streaming_video_pipeline_service.start_job(
                ai_job.job_id,
                background=False,
                output_face_dir=output_face_dir,
                target_fps=10.0,
                debug_video_path=None,
                stream_frame_dir=None,
                stream_emit_every_n_frames=1,
                stream_realtime_sleep=False,
                stream_send_annotated_frame=False,
            )
            unsubscribe_video_processing(ai_job.session_id, on_pipeline_event)

            # BE-06: Sau khi pipeline merge identity xong mới chốt dữ liệu DB chính thức.
            self._finalize_job_data(db, job, context, pipeline_result)
            result = self._build_complete_result(
                db=db,
                job=job,
                context=context,
                pipeline_result=pipeline_result,
                processing_time_ms=int((time.perf_counter() - started) * 1000),
            )
            processing_job_manager.mark_completed(job_id, result)
        except Exception:
            db.rollback()
            raise
        finally:
            try:
                if "ai_job" in locals():
                    unsubscribe_video_processing(ai_job.session_id, on_pipeline_event)
            except Exception:
                pass
            db.close()
            shutil.rmtree(output_face_dir, ignore_errors=True)

    def _handle_ai_frame_result(
        self,
        job_id: str,
        db: Session,
        job,
        context: dict[str, Any],
        event: dict[str, Any],
    ) -> None:
        # BE-04: Cập nhật tiến độ mỗi frame để API status và WebSocket cùng thay đổi.
        processed_frames = int(event.get("processed_frames") or 0)
        total_frames = int(event.get("total_frames") or 0)
        progress_percent = int(round(float(event.get("progress_percent") or 0.0)))
        processing_fps = float(event.get("processing_fps") or 0.0)

        event_source_fps = float(
            event.get("source_fps")
            or event.get("video_fps")
            or context.get("video_fps")
            or 25.0
        )
        if event_source_fps <= 0:
            event_source_fps = 25.0

        event_source_frame_index = int(
            event.get("source_frame_index")
            or event.get("frame_index")
            or 0
        )
        event_source_timestamp_seconds = event.get(
            "source_timestamp_seconds"
        )
        if event_source_timestamp_seconds is None:
            event_source_timestamp_seconds = (
                float(event_source_frame_index) / event_source_fps
            )

        # Progress phải mang timestamp video nguồn ngay cả khi frame không có người.
        # Nếu chỉ cập nhật timestamp qua detection, frontend sẽ pause ở các đoạn
        # không có người hoặc detection đang TEMP/PENDING.
        processing_job_manager.update_progress(job_id, {
            "current_frame": processed_frames,
            "total_frames": total_frames,
            "fps": processing_fps,
            "progress_percent": min(100, max(0, progress_percent)),
            "source_frame_index": event_source_frame_index,
            "source_timestamp_seconds": max(
                0.0,
                float(event_source_timestamp_seconds),
            ),
            "source_fps": event_source_fps,
        })
        if event_source_fps > 0:
            context["video_fps"] = event_source_fps

        person_list = event.get("detections") or event.get("persons") or []
        for person in person_list:
            bbox = self._normalize_stream_bbox(person.get("bbox") or [], context)

            source_frame_index = int(
                person.get("source_frame_index")
                or person.get("frame_index")
                or event.get("source_frame_index")
                or event.get("frame_index")
                or 0
            )

            source_timestamp_seconds = person.get("source_timestamp_seconds")
            if source_timestamp_seconds is None:
                source_timestamp_seconds = event.get("source_timestamp_seconds")
            if source_timestamp_seconds is None:
                source_timestamp_seconds = (
                    float(source_frame_index) / max(event_source_fps, 1.0)
                )

            # 1. Trích xuất embedding từ payload AI
            embedding = person.get("embedding") 

            data = {
                "frame_index": source_frame_index,
                "source_frame_index": source_frame_index,
                "source_timestamp_seconds": max(0.0, float(source_timestamp_seconds)),
                "source_fps": event_source_fps,
                "track_id": int(person.get("track_id") or -1),
                "anonymous_code": person.get("anonymous_code"),
                "confidence": float(person.get("confidence") or 0.0),
                "bbox": bbox,
                "embedding": embedding # 2. Truyền embedding vào data để xử lý tiếp
            }
            enriched = self._handle_detection_event(db, job, context, data)
            if enriched:
                processing_job_manager.publish(job_id, {"type": "detection", "data": enriched})

    def _read_video_metadata(
        self,
        video_path: str,
    ) -> tuple[int, int, float]:
        cap = cv2.VideoCapture(video_path)
        try:
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            if fps <= 0 or not np.isfinite(fps):
                fps = 25.0
            return width, height, fps
        finally:
            cap.release()

    def _normalize_stream_bbox(
        self,
        bbox: list[float],
        context: dict[str, Any],
    ) -> list[float]:
        if len(bbox) != 4:
            return []
        values = [float(v) for v in bbox]
        if all(0.0 <= value <= 1.0 for value in values):
            return values

        frame_width = float(context.get("frame_width") or 0)
        frame_height = float(context.get("frame_height") or 0)
        if frame_width <= 0 or frame_height <= 0:
            return values

        x1, y1, x2, y2 = values
        return [
            max(0.0, min(1.0, x1 / frame_width)),
            max(0.0, min(1.0, y1 / frame_height)),
            max(0.0, min(1.0, x2 / frame_width)),
            max(0.0, min(1.0, y2 / frame_height)),
        ]

    def _handle_detection_event(
        self,
        db: Session,
        job,
        context: dict[str, Any],
        data: dict[str, Any],
    ) -> dict[str, Any] | None:
        
        anonymous_code = data.get("anonymous_code") or ""
        anonymous_code_str = str(anonymous_code).upper()
        track_id = int(data.get("track_id") or 0)
        confidence = float(data.get("confidence") or 0.0)

        # 1. Chặn mã TEMP hiển thị
        is_temp = anonymous_code_str.startswith("TEMP") or not anonymous_code or "PENDING" in anonymous_code_str
        identity_status = "PENDING" if is_temp else "CONFIRMED"

        # Tận dụng hàm quét vét cạn mọi key của service để tìm embedding
        embedding = global_customer_identity_service.extract_profile_embedding(data)

        # =================================================================
        # ĐẶT MÁY NGHE LÉN LOG (DEBUG) - HÃY NHÌN VÀO TERMINAL CỦA BACKEND
        # =================================================================
        if confidence >= 0.85 and track_id not in context.get("logged_tracks", set()):
            context.setdefault("logged_tracks", set()).add(track_id)
            print(f"\n[EARLY-RECOG DEBUG] Track {track_id} đạt conf {confidence:.2f}. Có Vector AI gửi kèm không?: {embedding is not None}")
        # =================================================================

        # 2. Xử lý nhận diện sớm (Early Recognition)
        if track_id not in context["early_identities"]:
            if confidence >= 0.85 and embedding is not None:
                gallery = context.get("gallery", {})
                
                match_result = global_customer_identity_service.match_embedding(
                    embedding=embedding,
                    gallery=gallery
                )
                
                print(f"[EARLY-RECOG DEBUG] Track {track_id} so sánh DB -> Matched: {match_result.matched} | P_ID: {match_result.person_profile_id} | Điểm khớp: {match_result.best_similarity:.4f}")

                if match_result and match_result.matched and match_result.person_profile_id:
                    person = db.get(PersonProfile, match_result.person_profile_id)
                    customer = self._get_customer_for_profile(db, person.id) if person else None
                    
                    context["early_identities"][track_id] = {
                        "customer_id": customer.id if customer else None,
                        "customer_name": customer.full_name if customer else None,
                        "customer_type": "returning" if customer else "new",
                        "stored_profile_avatar": person.face_image_url if person else None,
                        "identified_customer_avatar": customer.avatar_url if customer else None,
                        "session_profile_id": str(person.anonymous_code) if person else None,
                    }
                else:
                    context["early_identities"][track_id] = {"customer_type": "new"}

        early_info = context["early_identities"].get(track_id, {})
        
        display_code = early_info.get("session_profile_id") or str(anonymous_code)
        if identity_status != "CONFIRMED" and not early_info.get("session_profile_id"):
             display_code = str(track_id)

        # 3. Đóng gói trả về Frontend
        context["realtime_detections"].append({
            "frame_index": int(data.get("frame_index") or 0),
            "source_frame_index": int(data.get("source_frame_index") or 0),
            "source_timestamp_seconds": max(0.0, float(data.get("source_timestamp_seconds") or 0.0)),
            "source_fps": max(1.0, float(data.get("source_fps") or 25.0)),
            "track_id": track_id,
            "anonymous_code": display_code,
            "confidence": confidence,
            "bbox": data.get("bbox") or [],
        })

        return {
            "frame_index": int(data.get("frame_index") or 0),
            "source_timestamp_seconds": max(0.0, float(data.get("source_timestamp_seconds") or 0.0)),
            "track_id": track_id,
            "anonymous_code": display_code,
            "session_profile_id": early_info.get("session_profile_id") or (display_code if not is_temp else None),
            "identity_status": "CONFIRMED" if early_info.get("session_profile_id") else identity_status, 
            "confidence": confidence,
            "bbox": data.get("bbox") or [],
            "customer_type": early_info.get("customer_type") or "new",
            "customer_id": early_info.get("customer_id"),
            "customer_name": early_info.get("customer_name"),
            "stored_profile_avatar": early_info.get("stored_profile_avatar"),
            "identified_customer_avatar": early_info.get("identified_customer_avatar"),
            "current_video_avatar": None, 
        }

    def _finalize_job_data(
        self,
        db: Session,
        job,
        context: dict[str, Any],
        pipeline_result: dict[str, Any],
    ) -> None:
        """
        Đồng bộ dữ liệu cuối video bằng GlobalCustomerIdentityService.

        P_000X chỉ là session_profile_id. PersonProfile toàn cục được nhận
        bằng embedding và có anonymous_code ANON_xxxxxxxx.
        """
        merged_profiles = pipeline_result.get("merged_profiles") or []
        final_track_to_profile = self._build_final_track_to_profile(
            pipeline_result,
            merged_profiles,
        )

        print("\n[streaming_video_service] START GLOBAL IDENTITY")
        identity_results: list[SessionIdentityResult] = (
            global_customer_identity_service.classify_pipeline_profiles(
                db=db,
                merged_profiles=merged_profiles,
                seen_at=datetime.now(),
                commit=False,
            )
        )
        print(
            "[streaming_video_service] GLOBAL IDENTITY COMPLETED",
            len(identity_results),
        )

        identity_by_session = {
            str(result.session_profile_id): result
            for result in identity_results
        }
        merged_by_session = {
            str(profile.get("profile_id")): profile
            for profile in merged_profiles
            if profile.get("profile_id")
        }

        profile_confidence = {
            session_pid: max(
                0.0,
                min(1.0, float(result.confidence or 0.0)),
            )
            for session_pid, result in identity_by_session.items()
        }

        final_bounds = self._build_final_session_bounds(
            job=job,
            context=context,
            pipeline_result=pipeline_result,
            track_to_profile=final_track_to_profile,
            profile_confidence=profile_confidence,
        )

        context["final_profile_ids"] = list(identity_by_session.keys())
        context["profiles"] = {}
        context["identity_meta"] = {}
        context["current_face_paths"] = {}
        pending_face_uploads: list[tuple[int, str, str]] = []

        for session_pid, result in identity_by_session.items():
            person = db.get(PersonProfile, int(result.person_profile_id))
            if person is None:
                continue

            profile = merged_by_session.get(session_pid) or {}
            bounds = final_bounds.get(session_pid)
            detected_at = (
                bounds["entry_time"]
                if bounds
                else datetime.now()
            )

            context["profiles"][session_pid] = int(person.id)
            context["identity_meta"][session_pid] = {
                "anonymous_code": str(person.anonymous_code),
                "customer_type": str(result.customer_type),
                "total_visits": int(person.total_visits or 0),
                "matched_similarity": float(result.matched_similarity),
            }

            face_path = result.face_image_path or profile.get(
                "best_face_image_path"
            )
            if face_path:
                context["current_face_paths"][session_pid] = str(face_path)

            if (
                not person.face_image_url
                and face_path
                and os.path.exists(face_path)
            ):
                pending_face_uploads.append(
                    (int(person.id), str(person.anonymous_code), str(face_path))
                )

            if not bounds:
                bounds = {
                    "entry_time": detected_at,
                    "exit_time": detected_at,
                    "confidence_sum": float(result.confidence or 0.0),
                    "confidence_count": 1 if result.confidence > 0 else 0,
                }

            session = self._get_or_create_job_session(
                db,
                job,
                context,
                person,
                bounds["entry_time"],
            )
            entry_time = bounds["entry_time"]
            exit_time = bounds["exit_time"]
            session.entry_time = entry_time
            session.exit_time = exit_time
            session.duration_seconds = max(
                0,
                int((exit_time - entry_time).total_seconds()),
            )
            context["session_bounds"][person.id] = bounds

        self._save_final_visit_detections(
            db,
            job,
            context,
            pipeline_result,
            final_track_to_profile,
        )

        try:
            with db.begin_nested():
                self._save_movement_and_zone_data(
                    db,
                    job,
                    context,
                    pipeline_result,
                )
        except Exception:
            logger.exception(
                "Failed to save movement/zone data for processing job %s",
                job.job_id,
            )


        db.commit()

        # Phát mapping cuối cho frontend trước khi job chuyển sang complete.
        # Nhiều track/P_id online có thể cùng thuộc một PersonProfile toàn cục.
        session_profile_mapping: dict[str, dict[str, Any]] = {}
        track_identity_mapping: dict[str, dict[str, Any]] = {}

        for session_pid, result in identity_by_session.items():
            person = db.get(PersonProfile, int(result.person_profile_id))
            if person is None:
                continue

            customer = self._get_customer_for_profile(db, person.id)

            identity_payload = {
                "session_profile_id": session_pid,
                "person_profile_id": int(person.id),
                "anonymous_code": str(person.anonymous_code),
                "customer_type": str(result.customer_type),
                "total_visits": int(person.total_visits or 0),
                "matched_similarity": float(result.matched_similarity or 0.0),
                "customer_id": customer.id if customer else None,
                "customer_name": customer.full_name if customer else None,
                "stored_profile_avatar": person.face_image_url,
                "identified_customer_avatar": customer.avatar_url if customer else None,
                "current_video_avatar": None,
            }
            session_profile_mapping[session_pid] = identity_payload

        for track_id, session_pid in final_track_to_profile.items():
            identity_payload = session_profile_mapping.get(str(session_pid))
            if identity_payload is None:
                continue
            track_identity_mapping[str(int(track_id))] = {
                **identity_payload,
                "session_profile_id": str(session_pid),
            }

        processing_job_manager.publish(
            job.job_id,
            {
                "type": "global_identity_result",
                "data": {
                    "session_profile_mapping": session_profile_mapping,
                    "track_identity_mapping": track_identity_mapping,
                    "final_customer_count": len(
                        {
                            item["person_profile_id"]
                            for item in session_profile_mapping.values()
                        }
                    ),
                },
            },
        )

        self._upload_profile_faces(db, pending_face_uploads)

    def _upload_profile_faces(
        self,
        db: Session,
        pending_face_uploads: list[tuple[int, str, str]],
    ) -> None:
        for person_id, profile_id, face_image_path in pending_face_uploads:
            try:
                person = db.query(PersonProfile).filter(PersonProfile.id == person_id).first()
                if not person or person.face_image_url:
                    continue
                face_url = _upload_face_to_supabase(face_image_path, profile_id)
                if not face_url:
                    continue
                person.face_image_url = face_url
                db.commit()
            except Exception:
                db.rollback()
                logger.exception("Failed to upload/update face image for profile %s", profile_id)

    def _build_final_track_to_profile(
        self,
        pipeline_result: dict[str, Any],
        merged_profiles: list[dict[str, Any]],
    ) -> dict[int, str]:
        final_detected_customers = [
            {"anonymous_id": profile.get("profile_id")}
            for profile in merged_profiles
            if profile.get("profile_id")
        ]
        return _build_track_to_profile(
            pipeline_result=pipeline_result,
            merged_profiles=merged_profiles,
            detected_customers=final_detected_customers,
        )

    def _build_final_session_bounds(
        self,
        job,
        context: dict[str, Any],
        pipeline_result: dict[str, Any],
        track_to_profile: dict[int, str],
        profile_confidence: dict[str, float],
    ) -> dict[str, dict[str, Any]]:
        # Tính entry_time/exit_time theo frame đầu/cuối mỗi profile xuất hiện.
        bounds_by_profile: dict[str, dict[str, Any]] = {}
        debug_person_records = pipeline_result.get("debug_person_records") or []

        if not debug_person_records:
            for profile_id, record in self._iter_person_path_records(pipeline_result):
                frame_index = int(record.get("frame_index") or 0)
                detected_at = self._detected_at(job, frame_index, context)
                confidence = float(profile_confidence.get(profile_id, 0.0) or 0.0)
                bounds = bounds_by_profile.setdefault(profile_id, {
                    "entry_time": detected_at,
                    "exit_time": detected_at,
                    "confidence_sum": 0.0,
                    "confidence_count": 0,
                })
                if detected_at < bounds["entry_time"]:
                    bounds["entry_time"] = detected_at
                if detected_at > bounds["exit_time"]:
                    bounds["exit_time"] = detected_at
                if confidence:
                    bounds["confidence_sum"] += confidence
                    bounds["confidence_count"] += 1
            return bounds_by_profile

        for record in debug_person_records:
            track_id = int(record.get("track_id", -1))
            profile_id = track_to_profile.get(track_id)
            if not profile_id:
                continue

            frame_index = int(record.get("frame_index") or 0)
            detected_at = self._detected_at(job, frame_index, context)
            confidence = float(profile_confidence.get(profile_id, 0.0) or 0.0)

            bounds = bounds_by_profile.setdefault(profile_id, {
                "entry_time": detected_at,
                "exit_time": detected_at,
                "confidence_sum": 0.0,
                "confidence_count": 0,
            })
            if detected_at < bounds["entry_time"]:
                bounds["entry_time"] = detected_at
            if detected_at > bounds["exit_time"]:
                bounds["exit_time"] = detected_at
            if confidence:
                bounds["confidence_sum"] += confidence
                bounds["confidence_count"] += 1

        return bounds_by_profile

    def _save_final_visit_detections(
        self,
        db: Session,
        job,
        context: dict[str, Any],
        pipeline_result: dict[str, Any],
        track_to_profile: dict[int, str],
    ) -> None:
        # BE-05: Lưu VisitDetection chính thức sau khi track_id đã map sang profile_id.
        debug_person_records = pipeline_result.get("debug_person_records") or []
        if not debug_person_records:
            self._save_final_visit_detections_from_person_paths(db, job, context, pipeline_result)
            return

        profile_to_person = {
            anonymous_code: db.query(PersonProfile).filter(PersonProfile.id == person_id).first()
            for anonymous_code, person_id in context.get("profiles", {}).items()
        }

        saved_count = 0
        for record in debug_person_records:
            track_id = int(record.get("track_id", -1))
            profile_id = track_to_profile.get(track_id)
            person = profile_to_person.get(profile_id)
            if not profile_id or not person:
                continue

            session_id = context["sessions"].get(person.id)
            if not session_id:
                continue

            bbox = self._normalize_record_bbox(record)
            bbox_x, bbox_y, bbox_width, bbox_height = self._bbox_to_db_values(bbox)
            detected_at = self._detected_at(job, int(record.get("frame_index") or 0), context)
            confidence = float(person.confidence_avg or 0.0)

            db.add(VisitDetection(
                visit_session_id=session_id,
                person_profile_id=person.id,
                video_id=None,
                bbox_x=bbox_x,
                bbox_y=bbox_y,
                bbox_width=bbox_width,
                bbox_height=bbox_height,
                confidence_score=confidence,
                detected_at=detected_at,
            ))
            saved_count += 1

        context["detection_count"] = saved_count

    def _save_final_visit_detections_from_person_paths(
        self,
        db: Session,
        job,
        context: dict[str, Any],
        pipeline_result: dict[str, Any],
    ) -> None:
        saved_count = 0
        profile_to_person = {
            anonymous_code: db.query(PersonProfile).filter(PersonProfile.id == person_id).first()
            for anonymous_code, person_id in context.get("profiles", {}).items()
        }

        for profile_id, record in self._iter_person_path_records(pipeline_result):
            person = profile_to_person.get(profile_id)
            if not person:
                continue
            session_id = context["sessions"].get(person.id)
            if not session_id:
                continue
            bbox = self._normalize_record_bbox(record)
            bbox_x, bbox_y, bbox_width, bbox_height = self._bbox_to_db_values(bbox)
            detected_at = self._detected_at(job, int(record.get("frame_index") or 0), context)
            db.add(VisitDetection(
                visit_session_id=session_id,
                person_profile_id=person.id,
                video_id=None,
                bbox_x=bbox_x,
                bbox_y=bbox_y,
                bbox_width=bbox_width,
                bbox_height=bbox_height,
                confidence_score=float(person.confidence_avg or 0.0),
                detected_at=detected_at,
            ))
            saved_count += 1

        context["detection_count"] = saved_count

    def _save_movement_and_zone_data(
        self,
        db: Session,
        job,
        context: dict[str, Any],
        pipeline_result: dict[str, Any],
    ) -> None:
        # BE-06: Lưu lịch sử di chuyển và zone visit nếu video có zone hợp lệ.
        debug_person_records = pipeline_result.get("debug_person_records") or []
        if not debug_person_records:
            self._save_movement_from_person_paths(db, job, context, pipeline_result)
            return

        zones_db = db.query(StoreZone).all()
        zones = [
            {
                "id": zone.id,
                "zone_name": zone.zone_name,
                "zone_type": zone.zone_type,
                "polygon": zone.polygon or [],
                "color": zone.color,
            }
            for zone in zones_db
            if zone.polygon and len(zone.polygon) >= 3
        ]
        if not zones:
            return

        detected_customers = [
            {"anonymous_id": profile_id}
            for profile_id in context.get("profiles", {}).keys()
        ]
        track_to_profile = _build_track_to_profile(
            pipeline_result=pipeline_result,
            merged_profiles=pipeline_result.get("merged_profiles") or [],
            detected_customers=detected_customers,
        )
        tracking_records = [
            rec for rec in debug_person_records
            if int(rec.get("track_id", -1)) in track_to_profile
        ]
        if not tracking_records:
            return

        movement_result = process_detections_for_tracking(
            debug_person_records=tracking_records,
            zones=zones,
            video_fps=float(pipeline_result.get("video_fps") or context.get("video_fps") or 1.0),
        )

        profile_to_person = {
            person.anonymous_code: person
            for person in db.query(PersonProfile)
            .filter(PersonProfile.anonymous_code.in_(set(track_to_profile.values())))
            .all()
        }

        for track in movement_result.tracks:
            profile_id = track_to_profile.get(track.track_id)
            person = profile_to_person.get(profile_id)
            if not person:
                continue
            session_id = context["sessions"].get(person.id)
            if not session_id:
                continue
            for point in track.points:
                db.add(MovementTrack(
                    visit_session_id=session_id,
                    person_profile_id=person.id,
                    zone_id=point.zone_id,
                    position_x=round(point.x, 4),
                    position_y=round(point.y, 4),
                    tracked_at=point.tracked_at,
                ))

        for zone_visit in movement_result.zone_visits:
            profile_id = track_to_profile.get(zone_visit.track_id)
            person = profile_to_person.get(profile_id)
            if not person:
                continue
            session_id = context["sessions"].get(person.id)
            if not session_id:
                continue
            db.add(ZoneVisit(
                visit_session_id=session_id,
                person_profile_id=person.id,
                zone_id=zone_visit.zone_id,
                enter_time=zone_visit.enter_time or datetime.now(),
                leave_time=zone_visit.leave_time,
                duration_seconds=zone_visit.duration_seconds,
            ))

    def _save_movement_from_person_paths(
        self,
        db: Session,
        job,
        context: dict[str, Any],
        pipeline_result: dict[str, Any],
    ) -> None:
        profile_to_person = {
            anonymous_code: db.query(PersonProfile).filter(PersonProfile.id == person_id).first()
            for anonymous_code, person_id in context.get("profiles", {}).items()
        }

        frame_width = float(context.get("frame_width") or 0)
        frame_height = float(context.get("frame_height") or 0)

        for profile_id, record in self._iter_person_path_records(pipeline_result):
            person = profile_to_person.get(profile_id)
            if not person:
                continue
            session_id = context["sessions"].get(person.id)
            if not session_id:
                continue

            center = record.get("center") or []
            if len(center) == 2 and frame_width > 0 and frame_height > 0:
                position_x = float(center[0]) / frame_width
                position_y = float(center[1]) / frame_height
            elif len(center) == 2:
                position_x = float(center[0])
                position_y = float(center[1])
            else:
                bbox = self._normalize_record_bbox(record)
                if len(bbox) == 4:
                    position_x = (bbox[0] + bbox[2]) / 2.0
                    position_y = (bbox[1] + bbox[3]) / 2.0
                else:
                    continue

            db.add(MovementTrack(
                visit_session_id=session_id,
                person_profile_id=person.id,
                zone_id=None,
                position_x=max(0.0, min(1.0, position_x)),
                position_y=max(0.0, min(1.0, position_y)),
                tracked_at=self._detected_at(job, int(record.get("frame_index") or 0), context),
            ))

    def _build_complete_result(
        self,
        db: Session,
        job,
        context: dict[str, Any],
        pipeline_result: dict[str, Any],
        processing_time_ms: int,
    ) -> dict[str, Any]:
        import base64

        detected_persons: list[dict[str, Any]] = []
        confidences: list[float] = []
        returning_count = 0

        for index, session_pid in enumerate(
            context.get("final_profile_ids") or [],
            start=1,
        ):
            person_id = context.get("profiles", {}).get(session_pid)
            if person_id is None:
                continue

            person = db.get(PersonProfile, int(person_id))
            if person is None:
                continue

            meta = context.get("identity_meta", {}).get(session_pid, {})
            customer_type = str(meta.get("customer_type") or "new")
            if customer_type == "returning":
                returning_count += 1

            customer = self._get_customer_for_profile(db, person.id)
            confidence = max(
                0.0,
                min(1.0, float(person.confidence_avg or 0.0)),
            )
            confidences.append(confidence)

            current_avatar = None
            face_path = context.get("current_face_paths", {}).get(session_pid)
            if face_path and os.path.exists(face_path):
                try:
                    with open(face_path, "rb") as image_file:
                        encoded = base64.b64encode(
                            image_file.read()
                        ).decode("utf-8")
                    current_avatar = (
                        "data:image/jpeg;base64," + encoded
                    )
                except Exception:
                    logger.exception(
                        "Failed to encode current video avatar for %s",
                        session_pid,
                    )

            detected_persons.append({
                "id": index,
                "session_profile_id": session_pid,
                "person_profile_id": int(person.id),
                "anonymous_id": str(person.anonymous_code),
                "customer_type": customer_type,
                "total_visits": int(person.total_visits or 0),
                "person_type": "identified" if customer else "anonymous",
                "confidence": confidence,
                "first_detected_at": self._format_first_detected(
                    job,
                    person.id,
                    context,
                ),
                "appearances": 1,
                "zone": None,
                # Màn hình kết quả ưu tiên ảnh của video hiện tại.
                "thumbnail_url": current_avatar,
                "current_video_avatar": current_avatar,
                "stored_profile_avatar": person.face_image_url,
                "identified_customer_avatar": (
                    customer.avatar_url if customer else None
                ),
                "customer_id": customer.id if customer else None,
                "customer_name": customer.full_name if customer else None,
            })

        total = len(detected_persons)
        identified = sum(
            1 for person in detected_persons
            if person["person_type"] == "identified"
        )
        avg_confidence = (
            sum(confidences) / len(confidences)
            if confidences
            else 0.0
        )

        return {
            "video_id": int(time.time() * 1000),
            "video_name": job.file_name,
            "duration": self._job_duration_seconds(context),
            "processed_at": datetime.now().isoformat(),
            "stats": {
                "total_customers": total,
                "new_customers": total - returning_count,
                "returning_customers": returning_count,
                "identified_customers": identified,
                "avg_confidence": round(avg_confidence, 3),
                "processing_time_ms": processing_time_ms,
            },
            "detected_persons": detected_persons,
        }

    def _get_or_create_person_profile(
        self,
        db: Session,
        anonymous_code: str,
        confidence: float,
        detected_at: datetime,
    ) -> PersonProfile:
        raise RuntimeError(
            "Legacy P_000X PersonProfile creation is disabled. "
            "Use global_customer_identity_service instead."
        )

    def _get_or_create_job_session(
        self,
        db: Session,
        job,
        context: dict[str, Any],
        person: PersonProfile,
        detected_at: datetime,
    ) -> VisitSession:
        existing_session_id = context["sessions"].get(person.id)
        if existing_session_id:
            session = db.query(VisitSession).filter(VisitSession.id == existing_session_id).first()
            if session:
                return session

        session = VisitSession(
            person_profile_id=person.id,
            entry_time=detected_at,
            exit_time=None,
            duration_seconds=None,
            is_identified=False,
        )
        db.add(session)
        db.flush()
        context["sessions"][person.id] = session.id
        context["profiles"][person.anonymous_code] = person.id
        job.person_session_map[person.anonymous_code] = session.id
        return session

    def _get_customer_for_profile(self, db: Session, person_profile_id: int) -> Customer | None:
        return (
            db.query(Customer)
            .join(CustomerIdentity, CustomerIdentity.customer_id == Customer.id)
            .filter(CustomerIdentity.person_profile_id == person_profile_id)
            .first()
        )

    def _detected_at(self, job, frame_index: int, context: dict[str, Any]) -> datetime:
        started_at = job.started_at or datetime.now()
        fps = float(context.get("video_fps") or 15.0)
        return started_at + timedelta(seconds=frame_index / max(fps, 1.0))

    def _bbox_to_db_values(self, bbox: list[float]) -> tuple[float | None, float | None, float | None, float | None]:
        if len(bbox) != 4:
            return None, None, None, None
        x1, y1, x2, y2 = [float(v) for v in bbox]
        return x1, y1, max(0.0, x2 - x1), max(0.0, y2 - y1)

    def _normalize_record_bbox(self, record: dict[str, Any]) -> list[float]:
        bbox = record.get("bbox") or []
        if len(bbox) != 4:
            return []
        frame_width = float(record.get("frame_width") or 0)
        frame_height = float(record.get("frame_height") or 0)
        if frame_width <= 0 or frame_height <= 0:
            return [float(v) for v in bbox]

        x1, y1, x2, y2 = [float(v) for v in bbox]
        return [
            max(0.0, min(1.0, x1 / frame_width)),
            max(0.0, min(1.0, y1 / frame_height)),
            max(0.0, min(1.0, x2 / frame_width)),
            max(0.0, min(1.0, y2 / frame_height)),
        ]

    def _iter_person_path_records(self, pipeline_result: dict[str, Any]):
        person_paths = pipeline_result.get("person_paths") or {}
        for profile_id, records in person_paths.items():
            if not profile_id or not isinstance(records, list):
                continue
            for record in records:
                if not isinstance(record, dict):
                    continue
                yield str(profile_id), record

    def _format_first_detected(self, job, person_id: int, context: dict[str, Any]) -> str:
        bounds = context["session_bounds"].get(person_id)
        if not bounds:
            return "00:00"
        started_at = job.started_at or bounds["entry_time"]
        seconds = max(0, int((bounds["entry_time"] - started_at).total_seconds()))
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    def _job_duration_seconds(self, context: dict[str, Any]) -> int:
        if not context["session_bounds"]:
            return 0
        earliest = min(bounds["entry_time"] for bounds in context["session_bounds"].values())
        latest = max(bounds["exit_time"] for bounds in context["session_bounds"].values())
        return max(0, int((latest - earliest).total_seconds()))


def validate_video_upload(file) -> None:
    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Sai dinh dang. Phai la file video.")
    if file.size and file.size > MAX_VIDEO_SIZE:
        raise HTTPException(status_code=413, detail="File qua lon. Vui long upload video duoi 50MB.")


streaming_video_service = StreamingVideoService()