from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.database.session import SessionLocal, engine
from app.models.realtime_camera_track_point import RealtimeCameraTrackPoint


@dataclass(frozen=True)
class RealtimeTrackPointPersistenceContext:
    stream_session_id: str
    camera_id: int
    source_type: str


class RealtimeCameraTrackPointSinkService:
    def ensure_storage(self) -> None:
        RealtimeCameraTrackPoint.__table__.create(bind=engine, checkfirst=True)

    def persist_points(
        self,
        context: RealtimeTrackPointPersistenceContext,
        points: list[dict[str, Any]],
    ) -> int:
        records = [self._build_record(context, point) for point in points]

        if not records:
            return 0

        db = SessionLocal()
        try:
            db.add_all(records)
            db.commit()
            return len(records)
        except IntegrityError:
            db.rollback()
            inserted_count = 0

            for record in records:
                try:
                    db.add(record)
                    db.commit()
                    inserted_count += 1
                except IntegrityError:
                    db.rollback()

            return inserted_count
        finally:
            db.close()

    def _build_record(
        self,
        context: RealtimeTrackPointPersistenceContext,
        point: dict[str, Any],
    ) -> RealtimeCameraTrackPoint:
        track_id = int(point["track_id"])
        tracked_at = self._normalize_timestamp(point.get("tracked_at"))
        position_x = float(point["x"])
        position_y = float(point["y"])
        active_roi_ids = self._json_safe_list(point.get("active_roi_ids") or [])

        return RealtimeCameraTrackPoint(
            point_key=self._build_point_key(
                stream_session_id=context.stream_session_id,
                track_id=track_id,
                tracked_at=tracked_at,
                position_x=position_x,
                position_y=position_y,
            ),
            stream_session_id=context.stream_session_id,
            camera_id=context.camera_id,
            source_type=context.source_type,
            track_id=track_id,
            tracked_at=tracked_at,
            position_x=position_x,
            position_y=position_y,
            active_roi_ids=active_roi_ids,
        )

    def _build_point_key(
        self,
        stream_session_id: str,
        track_id: int,
        tracked_at: datetime,
        position_x: float,
        position_y: float,
    ) -> str:
        raw_key = json.dumps(
            {
                "stream_session_id": stream_session_id,
                "track_id": track_id,
                "tracked_at": tracked_at.isoformat(),
                "position_x": position_x,
                "position_y": position_y,
            },
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
        )
        return hashlib.sha1(raw_key.encode("utf-8")).hexdigest()

    def _normalize_timestamp(self, raw_value: Any) -> datetime:
        if isinstance(raw_value, datetime):
            return raw_value

        if raw_value is None:
            return datetime.utcnow()

        return datetime.fromisoformat(str(raw_value).replace("Z", "+00:00"))

    def _json_safe_list(self, values: list[Any]) -> list[Any]:
        return [str(value) for value in values]


realtime_camera_track_point_sink_service = RealtimeCameraTrackPointSinkService()
