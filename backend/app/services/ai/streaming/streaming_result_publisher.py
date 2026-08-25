from __future__ import annotations

from collections import defaultdict
from threading import RLock
from typing import Any, Callable, Dict, List, Optional
import json


Subscriber = Callable[[Dict[str, Any], Any], None]


class StreamingResultPublisher:
    """AI-06: publisher trung gian cho callback, WebSocket hoặc SSE."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Subscriber]] = defaultdict(list)
        self._lock = RLock()

    def subscribe(self, session_id: str, subscriber: Subscriber) -> None:
        with self._lock:
            self._subscribers[str(session_id)].append(subscriber)

    def unsubscribe(self, session_id: str, subscriber: Subscriber) -> None:
        with self._lock:
            values = self._subscribers.get(str(session_id), [])
            if subscriber in values:
                values.remove(subscriber)

    def publish(self, session_id: str, payload: Dict[str, Any], annotated_frame: Any = None) -> None:
        with self._lock:
            subscribers = list(self._subscribers.get(str(session_id), []))
        errors = []
        for subscriber in subscribers:
            try:
                subscriber(payload, annotated_frame)
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {exc}")
        if errors:
            payload.setdefault("publisher_errors", errors)

    @staticmethod
    def to_sse(payload: Dict[str, Any], event: Optional[str] = None) -> str:
        event_name = event or str(payload.get("type") or "message")
        return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
