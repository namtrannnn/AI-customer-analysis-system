from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.database.session import SessionLocal, engine
from app.models.realtime_camera_event import RealtimeCameraEvent


IMMUTABLE_REALTIME_EVENT_TYPES = {
    "session_state_change",
    "track_start",
    "track_end",
    "roi_enter",
    "roi_exit",
}


@dataclass(frozen=True)
class RealtimeEventPersistenceContext:
    stream_session_id: str
    camera_id: int
    source_type: str


class RealtimeCameraEventSinkService:
    def ensure_storage(self) -> None:
        RealtimeCameraEvent.__table__.create(bind=engine, checkfirst=True)

    def persist_events(
        self,
        context: RealtimeEventPersistenceContext,
        events: list[dict[str, Any]],
    ) -> int:
        records = [
            self._build_record(context, event)
            for event in events
            if event.get("event_type") in IMMUTABLE_REALTIME_EVENT_TYPES
        ]

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
        context: RealtimeEventPersistenceContext,
        event: dict[str, Any],
    ) -> RealtimeCameraEvent:
        payload = dict(event.get("payload") or {})
        event_timestamp = self._normalize_timestamp(event.get("event_timestamp"))
        track_id = self._coerce_optional_int(payload.get("track_id"))
        roi_id = self._coerce_optional_str(payload.get("roi_id"))

        return RealtimeCameraEvent(
            event_key=self._build_event_key(
                stream_session_id=context.stream_session_id,
                event_type=str(event["event_type"]),
                event_timestamp=event_timestamp,
                payload=payload,
            ),
            stream_session_id=context.stream_session_id,
            camera_id=context.camera_id,
            source_type=context.source_type,
            event_type=str(event["event_type"]),
            event_timestamp=event_timestamp,
            track_id=track_id,
            roi_id=roi_id,
            payload=self._json_safe_value(payload),
        )

    def _build_event_key(
        self,
        stream_session_id: str,
        event_type: str,
        event_timestamp: datetime,
        payload: dict[str, Any],
    ) -> str:
        raw_key = json.dumps(
            {
                "stream_session_id": stream_session_id,
                "event_type": event_type,
                "event_timestamp": event_timestamp.isoformat(),
                "payload": self._json_safe_value(payload),
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

    def _coerce_optional_int(self, raw_value: Any) -> int | None:
        if raw_value is None:
            return None

        try:
            return int(raw_value)
        except (TypeError, ValueError):
            return None

    def _coerce_optional_str(self, raw_value: Any) -> str | None:
        if raw_value is None:
            return None

        value = str(raw_value).strip()
        return value or None

    def _json_safe_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                str(key): self._json_safe_value(item)
                for key, item in value.items()
            }

        if isinstance(value, list):
            return [self._json_safe_value(item) for item in value]

        if isinstance(value, tuple):
            return [self._json_safe_value(item) for item in value]

        if isinstance(value, datetime):
            return value.isoformat()

        return value


realtime_camera_event_sink_service = RealtimeCameraEventSinkService()
