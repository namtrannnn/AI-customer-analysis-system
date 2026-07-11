import asyncio
import os
import shutil
import tempfile
import time
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
from app.services.ai.video_pipeline_service import video_pipeline_service
from app.services.processing_job_manager import processing_job_manager
from app.services.video_service import _build_track_to_profile, _upload_face_to_supabase


MAX_VIDEO_SIZE = 50 * 1024 * 1024


class StreamingVideoService:
    async def start_job(self, job_id: str) -> None:
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

        db = SessionLocal()
        output_face_dir = tempfile.mkdtemp(prefix=f"pipeline_faces_{job_id}_")
        started = time.perf_counter()
        context: dict[str, Any] = {
            "video_fps": 15.0,
            "profiles": {},
            "sessions": {},
            "session_bounds": {},
            "final_profile_ids": [],
            "realtime_detections": [],
            "detection_count": 0,
        }

        try:
            def on_pipeline_event(event: dict[str, Any]) -> None:
                event_type = event.get("type")
                data = event.get("data") or {}
                if event_type == "progress":
                    context["video_fps"] = float(data.get("fps") or context["video_fps"] or 15.0)
                    processing_job_manager.update_progress(job_id, data)
                    return
                if event_type == "detection":
                    enriched = self._handle_detection_event(db, job, context, data)
                    if enriched:
                        processing_job_manager.publish(job_id, {"type": "detection", "data": enriched})

            pipeline_result = video_pipeline_service.process_video(
                job.temp_video_path,
                output_face_dir=output_face_dir,
                target_fps=15.0,
                event_callback=on_pipeline_event,
            )

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
            db.close()
            shutil.rmtree(output_face_dir, ignore_errors=True)

    def _handle_detection_event(
        self,
        db: Session,
        job,
        context: dict[str, Any],
        data: dict[str, Any],
    ) -> dict[str, Any] | None:
        anonymous_code = data.get("anonymous_code")
        if not anonymous_code or str(anonymous_code).startswith("TEMP_"):
            return None

        track_id = int(data.get("track_id") or 0)
        frame_index = int(data.get("frame_index") or 0)
        confidence = float(data.get("confidence") or 0.0)
        bbox = data.get("bbox") or []
        context["realtime_detections"].append({
            "frame_index": frame_index,
            "track_id": track_id,
            "anonymous_code": str(anonymous_code),
            "confidence": confidence,
            "bbox": bbox,
        })

        # Realtime events are only a preview. Official PersonProfile,
        # VisitSession, VisitDetection, and movement data are reconciled
        # from final merged_profiles after the pipeline completes.
        person = db.query(PersonProfile).filter(
            PersonProfile.anonymous_code == str(anonymous_code)
        ).first()
        customer = self._get_customer_for_profile(db, person.id) if person else None

        payload = {
            "frame_index": frame_index,
            "track_id": track_id,
            "anonymous_code": str(anonymous_code),
            "confidence": confidence,
            "bbox": bbox,
            "customer_id": customer.id if customer else None,
            "customer_name": customer.full_name if customer else None,
            "customer_avatar": (customer.avatar_url if customer else None) or (person.face_image_url if person else None),
        }
        return payload

    def _finalize_job_data(
        self,
        db: Session,
        job,
        context: dict[str, Any],
        pipeline_result: dict[str, Any],
    ) -> None:
        merged_profiles = pipeline_result.get("merged_profiles") or []
        profile_confidence = {
            p.get("profile_id"): float(p.get("best_face_confidence") or 0.0)
            for p in merged_profiles
            if p.get("profile_id")
        }
        final_track_to_profile = self._build_final_track_to_profile(pipeline_result, merged_profiles)
        final_profile_ids = [profile.get("profile_id") for profile in merged_profiles if profile.get("profile_id")]
        context["final_profile_ids"] = final_profile_ids
        final_bounds = self._build_final_session_bounds(
            job=job,
            context=context,
            pipeline_result=pipeline_result,
            track_to_profile=final_track_to_profile,
            profile_confidence=profile_confidence,
        )

        for profile in merged_profiles:
            profile_id = profile.get("profile_id")
            if not profile_id:
                continue
            bounds = final_bounds.get(profile_id)
            detected_at = bounds["entry_time"] if bounds else datetime.now()
            person = self._get_or_create_person_profile(
                db=db,
                anonymous_code=profile_id,
                confidence=profile_confidence.get(profile_id, 0.0),
                detected_at=detected_at,
            )
            if not person.face_image_url and profile.get("best_face_image_path"):
                face_url = _upload_face_to_supabase(profile["best_face_image_path"], profile_id)
                if face_url:
                    person.face_image_url = face_url

            context["profiles"][profile_id] = person.id

            if not bounds:
                bounds = {
                    "entry_time": detected_at,
                    "exit_time": detected_at,
                    "confidence_sum": profile_confidence.get(profile_id, 0.0),
                    "confidence_count": 1 if profile_confidence.get(profile_id, 0.0) else 0,
                }

            session = self._get_or_create_job_session(db, job, context, person, bounds["entry_time"])
            entry_time = bounds["entry_time"]
            exit_time = bounds["exit_time"]
            duration_seconds = max(0, int((exit_time - entry_time).total_seconds()))
            session.entry_time = entry_time
            session.exit_time = exit_time
            session.duration_seconds = duration_seconds
            context["session_bounds"][person.id] = bounds

            person.first_seen_at = min(filter(None, [person.first_seen_at, entry_time]), default=entry_time)
            person.last_seen_at = max(filter(None, [person.last_seen_at, exit_time]), default=exit_time)
            person.total_visits = int(person.total_visits or 0) + 1
            if bounds["confidence_count"]:
                avg = bounds["confidence_sum"] / bounds["confidence_count"]
                person.confidence_avg = avg if person.confidence_avg is None else (person.confidence_avg + avg) / 2

        self._save_final_visit_detections(db, job, context, pipeline_result, final_track_to_profile)
        self._save_movement_and_zone_data(db, context, pipeline_result)
        db.commit()

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
        bounds_by_profile: dict[str, dict[str, Any]] = {}
        debug_person_records = pipeline_result.get("debug_person_records") or []

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
        debug_person_records = pipeline_result.get("debug_person_records") or []
        if not debug_person_records:
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

    def _save_movement_and_zone_data(
        self,
        db: Session,
        context: dict[str, Any],
        pipeline_result: dict[str, Any],
    ) -> None:
        debug_person_records = pipeline_result.get("debug_person_records") or []
        if not debug_person_records:
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

    def _build_complete_result(
        self,
        db: Session,
        job,
        context: dict[str, Any],
        pipeline_result: dict[str, Any],
        processing_time_ms: int,
    ) -> dict[str, Any]:
        detected_persons = []
        confidences = []
        people_by_code = {
            person.anonymous_code: person
            for person in db.query(PersonProfile)
            .filter(PersonProfile.anonymous_code.in_(context.get("final_profile_ids") or []))
            .all()
        }

        for index, profile_id in enumerate(context.get("final_profile_ids") or [], start=1):
            person = people_by_code.get(profile_id)
            if not person:
                continue
            customer = self._get_customer_for_profile(db, person.id)
            confidence = float(person.confidence_avg or 0.0)
            confidences.append(confidence)
            detected_persons.append({
                "id": index,
                "anonymous_id": person.anonymous_code,
                "person_type": "identified" if customer else "anonymous",
                "confidence": confidence,
                "first_detected_at": self._format_first_detected(job, person.id, context),
                "appearances": 1,
                "zone": None,
                "thumbnail_url": (customer.avatar_url if customer else None) or person.face_image_url,
                "customer_id": customer.id if customer else None,
                "customer_name": customer.full_name if customer else None,
            })

        total = len(detected_persons)
        identified = len([p for p in detected_persons if p["person_type"] == "identified"])
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        duration = self._job_duration_seconds(context)

        return {
            "video_id": int(time.time() * 1000),
            "video_name": job.file_name,
            "duration": duration,
            "processed_at": datetime.now().isoformat(),
            "stats": {
                "total_customers": total,
                "new_customers": total - identified,
                "returning_customers": identified,
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
        person = db.query(PersonProfile).filter(PersonProfile.anonymous_code == anonymous_code).first()
        if person:
            if person.first_seen_at is None or detected_at < person.first_seen_at:
                person.first_seen_at = detected_at
            if person.last_seen_at is None or detected_at > person.last_seen_at:
                person.last_seen_at = detected_at
            if confidence:
                person.confidence_avg = confidence if person.confidence_avg is None else (person.confidence_avg + confidence) / 2
            db.flush()
            return person

        person = PersonProfile(
            anonymous_code=anonymous_code,
            person_type="anonymous",
            first_seen_at=detected_at,
            last_seen_at=detected_at,
            total_visits=0,
            confidence_avg=confidence,
        )
        db.add(person)
        db.flush()
        return person

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
