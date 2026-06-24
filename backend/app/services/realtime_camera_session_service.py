from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, WebSocket

from app.schemas.camera_session_schema import (
    CameraSessionCreateRequest,
    CameraSessionResponse,
    CameraSessionStatus,
    CameraSessionWebSocketEndpoints,
)
from app.services.ai.realtime_analytics_engine import RealtimeAnalyticsEngine
from app.services.realtime_camera_event_sink_service import (
    RealtimeEventPersistenceContext,
    realtime_camera_event_sink_service,
)
from app.services.realtime_camera_track_point_sink_service import (
    RealtimeTrackPointPersistenceContext,
    realtime_camera_track_point_sink_service,
)


@dataclass
class FramePacket:
    session_id: str
    frame_id: int | None
    timestamp: datetime
    frame_bytes: bytes
    decoded_frame: Any | None = None
    width: int | None = None
    height: int | None = None


@dataclass
class SessionRuntime:
    stream_session_id: str
    camera_id: int
    source_type: str
    status: CameraSessionStatus
    target_fps: float
    debug_enabled: bool
    debug_interval_ms: int
    roi_config: list[dict[str, Any]]
    latest_frame_packet: FramePacket | None = None
    worker_task: asyncio.Task | None = None
    last_processed_frame_id: int | None = None
    last_processed_timestamp: datetime | None = None
    current_tracks: dict[int, dict[str, Any]] = field(default_factory=dict)
    current_count: int = 0
    active_rois: dict[int, list[str]] = field(default_factory=dict)
    path_buffer_by_track: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    debug_last_published_at: float = 0.0
    subscribers_events: set[WebSocket] = field(default_factory=set)
    subscribers_debug: set[WebSocket] = field(default_factory=set)
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    last_ingested_at: datetime | None = None
    last_ingest_monotonic: float | None = None
    terminal_state_at: datetime | None = None
    failure_reason: str | None = None
    ingest_sequence: int = 0
    event_log: list[dict[str, Any]] = field(default_factory=list)
    frame_update_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    engine: RealtimeAnalyticsEngine | None = None
    max_path_buffer_points: int = 500


class RealtimeCameraSessionService:
    def __init__(
        self,
        ingest_idle_timeout_seconds: float = 5.0,
        terminal_retention_seconds: float = 300.0,
        cleanup_interval_seconds: float = 30.0,
        path_point_batch_size: int = 24,
    ):
        self._runtimes: dict[str, SessionRuntime] = {}
        self._service_lock = asyncio.Lock()
        self._ingest_idle_timeout_seconds = ingest_idle_timeout_seconds
        self._terminal_retention_seconds = terminal_retention_seconds
        self._cleanup_interval_seconds = cleanup_interval_seconds
        self._path_point_batch_size = path_point_batch_size
        self._cleanup_task: asyncio.Task | None = None
        self._event_sink = realtime_camera_event_sink_service
        self._track_point_sink = realtime_camera_track_point_sink_service

    async def create_session(self, payload: CameraSessionCreateRequest) -> CameraSessionResponse:
        async with self._service_lock:
            stream_session_id = uuid4().hex
            runtime = SessionRuntime(
                stream_session_id=stream_session_id,
                camera_id=payload.camera_id,
                source_type=payload.source_type.value,
                status=CameraSessionStatus.CREATED,
                target_fps=payload.target_fps,
                debug_enabled=payload.debug_enabled,
                debug_interval_ms=payload.debug_interval_ms,
                roi_config=[roi.model_dump() for roi in payload.roi_config],
            )
            self._runtimes[stream_session_id] = runtime

        return self._build_session_response(runtime)

    async def start_session(self, stream_session_id: str) -> CameraSessionResponse:
        runtime = self._get_runtime(stream_session_id)

        if runtime.status == CameraSessionStatus.RUNNING:
            return self._build_session_response(runtime)

        if runtime.status != CameraSessionStatus.CREATED:
            raise HTTPException(
                status_code=409,
                detail="Chi co the start session o trang thai CREATED.",
            )

        runtime.status = CameraSessionStatus.RUNNING
        runtime.started_at = datetime.now(timezone.utc)
        runtime.stopped_at = None
        runtime.terminal_state_at = None
        runtime.failure_reason = None
        runtime.latest_frame_packet = None
        runtime.last_processed_frame_id = None
        runtime.last_processed_timestamp = None
        runtime.last_ingested_at = None
        runtime.last_ingest_monotonic = time.monotonic()
        runtime.current_tracks = {}
        runtime.current_count = 0
        runtime.active_rois = {}
        runtime.path_buffer_by_track = {}
        runtime.event_log = []
        runtime.debug_last_published_at = 0.0
        runtime.engine = RealtimeAnalyticsEngine()
        runtime.worker_task = asyncio.create_task(
            self._run_session_worker(runtime),
            name=f"camera-session-{runtime.stream_session_id}",
        )

        session_event = self._build_envelope(
            event_type="session_state_change",
            session_id=runtime.stream_session_id,
            payload={"session_state": runtime.status.value},
        )
        await self._record_immutable_events(runtime, [session_event])
        await self._broadcast_event(runtime, session_event)

        return self._build_session_response(runtime)

    async def stop_session(self, stream_session_id: str) -> CameraSessionResponse:
        runtime = self._get_runtime(stream_session_id)

        if runtime.status in {CameraSessionStatus.STOPPED, CameraSessionStatus.FAILED}:
            return self._build_session_response(runtime)

        runtime.status = CameraSessionStatus.STOPPED
        runtime.stopped_at = datetime.now(timezone.utc)
        runtime.terminal_state_at = runtime.stopped_at

        await self._finalize_open_tracks(runtime)

        if runtime.worker_task is not None:
            runtime.worker_task.cancel()
            try:
                await runtime.worker_task
            except asyncio.CancelledError:
                pass
            finally:
                runtime.worker_task = None

        session_event = self._build_envelope(
            event_type="session_state_change",
            session_id=runtime.stream_session_id,
            payload={"session_state": runtime.status.value},
        )
        await self._record_immutable_events(runtime, [session_event])
        await self._broadcast_event(runtime, session_event)

        return self._build_session_response(runtime)

    def get_session(self, stream_session_id: str) -> CameraSessionResponse:
        runtime = self._get_runtime(stream_session_id)
        return self._build_session_response(runtime)

    async def update_session_roi(
        self,
        stream_session_id: str,
        roi_config: list[dict[str, Any]],
    ) -> CameraSessionResponse:
        runtime = self._get_runtime(stream_session_id)
        runtime.roi_config = roi_config
        return self._build_session_response(runtime)

    async def register_event_subscriber(self, stream_session_id: str, websocket: WebSocket) -> None:
        runtime = self._get_runtime(stream_session_id)
        runtime.subscribers_events.add(websocket)

        await self._broadcast_event(
            runtime,
            self._build_state_snapshot(runtime, [], []),
            target={websocket},
        )

    def unregister_event_subscriber(self, stream_session_id: str, websocket: WebSocket) -> None:
        runtime = self._runtimes.get(stream_session_id)
        if runtime:
            runtime.subscribers_events.discard(websocket)

    def register_debug_subscriber(self, stream_session_id: str, websocket: WebSocket) -> None:
        runtime = self._get_runtime(stream_session_id)
        runtime.subscribers_debug.add(websocket)

    def unregister_debug_subscriber(self, stream_session_id: str, websocket: WebSocket) -> None:
        runtime = self._runtimes.get(stream_session_id)
        if runtime:
            runtime.subscribers_debug.discard(websocket)

    async def ingest_frame_packet(self, stream_session_id: str, packet: FramePacket) -> bool:
        runtime = self._runtimes.get(stream_session_id)

        if runtime is None:
            return False

        if runtime.status != CameraSessionStatus.RUNNING:
            return False

        if runtime.frame_update_lock.locked():
            return False

        async with runtime.frame_update_lock:
            latest = runtime.latest_frame_packet

            if latest and not self._is_newer_packet(incoming=packet, current=latest):
                return False

            runtime.latest_frame_packet = packet
            runtime.last_ingested_at = datetime.now(timezone.utc)
            runtime.last_ingest_monotonic = time.monotonic()
            return True

    def next_frame_id(self, stream_session_id: str) -> int:
        runtime = self._get_runtime(stream_session_id)
        runtime.ingest_sequence += 1
        return runtime.ingest_sequence

    async def start_background_tasks(self) -> None:
        await asyncio.to_thread(self._event_sink.ensure_storage)
        await asyncio.to_thread(self._track_point_sink.ensure_storage)

        if self._cleanup_task is not None and not self._cleanup_task.done():
            return

        self._cleanup_task = asyncio.create_task(
            self._cleanup_loop(),
            name="realtime-camera-session-cleanup",
        )

    async def stop_background_tasks(self) -> None:
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            finally:
                self._cleanup_task = None

        runtimes = list(self._runtimes.values())
        for runtime in runtimes:
            if runtime.worker_task is not None:
                runtime.worker_task.cancel()
                try:
                    await runtime.worker_task
                except asyncio.CancelledError:
                    pass
                finally:
                    runtime.worker_task = None

            await self._flush_path_points(runtime, force=True)
            await self._close_runtime_connections(runtime)

    async def _run_session_worker(self, runtime: SessionRuntime) -> None:
        interval_seconds = 1.0 / runtime.target_fps

        try:
            while runtime.status == CameraSessionStatus.RUNNING:
                cycle_started_at = time.monotonic()

                if self._has_ingest_timed_out(runtime):
                    await self._fail_runtime(
                        runtime,
                        failure_reason=(
                            "Khong nhan duoc frame moi trong gioi han ingest timeout."
                        ),
                    )
                    break

                packet = runtime.latest_frame_packet

                if packet and self._should_process_packet(runtime, packet):
                    result = runtime.engine.process_frame(runtime=runtime, frame_packet=packet)
                    runtime.last_processed_frame_id = packet.frame_id
                    runtime.last_processed_timestamp = packet.timestamp
                    runtime.current_tracks = result["current_tracks"]
                    runtime.current_count = result["current_count"]
                    runtime.active_rois = {
                        track_id: track_info.get("active_roi_ids", [])
                        for track_id, track_info in runtime.current_tracks.items()
                    }

                    emitted_events = result["emitted_events"]
                    await self._record_immutable_events(runtime, emitted_events)

                    for event in emitted_events:
                        await self._broadcast_event(runtime, event)

                    track_events = [event for event in emitted_events if event["event_type"].startswith("track_")]
                    roi_events = [event for event in emitted_events if event["event_type"].startswith("roi_")]
                    ended_track_ids = [
                        int(event["payload"]["track_id"])
                        for event in track_events
                        if event["event_type"] == "track_end" and event["payload"].get("track_id") is not None
                    ]

                    await self._broadcast_event(
                        runtime,
                        self._build_state_snapshot(runtime, track_events, roi_events),
                    )

                    await self._flush_path_points(runtime, track_ids=ended_track_ids)
                    await self._flush_path_points(runtime)

                    if self._should_publish_debug_frame(runtime):
                        debug_frame = runtime.engine.build_debug_frame(
                            frame=result["decoded_frame"],
                            current_tracks=runtime.current_tracks,
                            roi_config=runtime.roi_config,
                            current_count=runtime.current_count,
                        )

                        if debug_frame is not None:
                            runtime.debug_last_published_at = time.monotonic()
                            await self._broadcast_debug_frame(runtime, debug_frame)

                elapsed = time.monotonic() - cycle_started_at
                await asyncio.sleep(max(0.0, interval_seconds - elapsed))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._fail_runtime(runtime, failure_reason=str(exc))

    async def _finalize_open_tracks(self, runtime: SessionRuntime) -> None:
        now = datetime.now(timezone.utc)
        terminal_events: list[dict[str, Any]] = []

        for track_id, track_info in list(runtime.current_tracks.items()):
            for roi_id in track_info.get("active_roi_ids", []):
                terminal_events.append(
                    self._build_envelope(
                        event_type="roi_exit",
                        session_id=runtime.stream_session_id,
                        event_timestamp=now,
                        payload={
                            "track_id": track_id,
                            "roi_id": roi_id,
                        },
                    )
                )

            terminal_events.append(
                self._build_envelope(
                    event_type="track_end",
                    session_id=runtime.stream_session_id,
                    event_timestamp=now,
                    payload={"track_id": track_id},
                )
            )

        await self._record_immutable_events(runtime, terminal_events)
        await self._flush_path_points(runtime, force=True)

        runtime.current_tracks = {}
        runtime.current_count = 0
        runtime.active_rois = {}

        for event in terminal_events:
            await self._broadcast_event(runtime, event)

    def _should_process_packet(self, runtime: SessionRuntime, packet: FramePacket) -> bool:
        if runtime.last_processed_timestamp is None:
            return True

        if packet.timestamp > runtime.last_processed_timestamp:
            return True

        if packet.timestamp == runtime.last_processed_timestamp:
            current_frame_id = runtime.last_processed_frame_id or -1
            incoming_frame_id = packet.frame_id if packet.frame_id is not None else current_frame_id
            return incoming_frame_id > current_frame_id

        return False

    def _should_publish_debug_frame(self, runtime: SessionRuntime) -> bool:
        if not runtime.debug_enabled:
            return False

        if not runtime.subscribers_debug:
            return False

        interval_seconds = runtime.debug_interval_ms / 1000.0
        return (time.monotonic() - runtime.debug_last_published_at) >= interval_seconds

    def _append_immutable_events(self, runtime: SessionRuntime, events: list[dict[str, Any]]) -> None:
        runtime.event_log.extend(events)

    async def _record_immutable_events(
        self,
        runtime: SessionRuntime,
        events: list[dict[str, Any]],
    ) -> None:
        if not events:
            return

        self._append_immutable_events(runtime, events)
        context = RealtimeEventPersistenceContext(
            stream_session_id=runtime.stream_session_id,
            camera_id=runtime.camera_id,
            source_type=runtime.source_type,
        )

        try:
            await asyncio.to_thread(self._event_sink.persist_events, context, events)
        except Exception as exc:
            raise RuntimeError(
                "Khong the persist immutable realtime events."
            ) from exc

    async def _flush_path_points(
        self,
        runtime: SessionRuntime,
        track_ids: list[int] | None = None,
        force: bool = False,
    ) -> int:
        candidate_track_ids = (
            sorted(set(track_ids))
            if track_ids is not None
            else sorted(runtime.path_buffer_by_track.keys())
        )

        points_to_flush: list[dict[str, Any]] = []
        flushed_track_ids: list[int] = []

        for track_id in candidate_track_ids:
            buffered_points = runtime.path_buffer_by_track.get(track_id, [])
            if not buffered_points:
                continue

            if not force and track_ids is None and len(buffered_points) < self._path_point_batch_size:
                continue

            points_to_flush.extend(buffered_points)
            flushed_track_ids.append(track_id)

        if not points_to_flush:
            return 0

        context = RealtimeTrackPointPersistenceContext(
            stream_session_id=runtime.stream_session_id,
            camera_id=runtime.camera_id,
            source_type=runtime.source_type,
        )

        try:
            inserted_count = await asyncio.to_thread(
                self._track_point_sink.persist_points,
                context,
                points_to_flush,
            )
        except Exception:
            return 0

        for track_id in flushed_track_ids:
            runtime.path_buffer_by_track.pop(track_id, None)

        return inserted_count

    def _has_ingest_timed_out(self, runtime: SessionRuntime) -> bool:
        if runtime.status != CameraSessionStatus.RUNNING:
            return False

        if runtime.last_ingest_monotonic is None:
            return False

        return (time.monotonic() - runtime.last_ingest_monotonic) >= self._ingest_idle_timeout_seconds

    async def _fail_runtime(self, runtime: SessionRuntime, failure_reason: str) -> None:
        if runtime.status == CameraSessionStatus.FAILED:
            return

        runtime.status = CameraSessionStatus.FAILED
        runtime.failure_reason = failure_reason
        runtime.stopped_at = datetime.now(timezone.utc)
        runtime.terminal_state_at = runtime.stopped_at

        await self._finalize_open_tracks(runtime)

        session_event = self._build_envelope(
            event_type="session_state_change",
            session_id=runtime.stream_session_id,
            payload={
                "session_state": runtime.status.value,
                "failure_reason": runtime.failure_reason,
            },
        )

        try:
            await self._record_immutable_events(runtime, [session_event])
        except Exception:
            pass

        await self._broadcast_event(runtime, session_event)

    async def _cleanup_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._cleanup_interval_seconds)
                await self._cleanup_terminal_runtimes()
        except asyncio.CancelledError:
            raise

    async def _cleanup_terminal_runtimes(self) -> None:
        now = datetime.now(timezone.utc)
        expired_runtime_ids: list[str] = []

        async with self._service_lock:
            for stream_session_id, runtime in self._runtimes.items():
                if runtime.status not in {
                    CameraSessionStatus.STOPPED,
                    CameraSessionStatus.FAILED,
                }:
                    continue

                terminal_state_at = runtime.terminal_state_at or runtime.stopped_at
                if terminal_state_at is None:
                    continue

                elapsed = (now - terminal_state_at).total_seconds()
                if elapsed >= self._terminal_retention_seconds:
                    expired_runtime_ids.append(stream_session_id)

            expired_runtimes = [
                self._runtimes.pop(stream_session_id)
                for stream_session_id in expired_runtime_ids
            ]

        for runtime in expired_runtimes:
            await self._flush_path_points(runtime, force=True)
            await self._close_runtime_connections(runtime)

    async def _close_runtime_connections(self, runtime: SessionRuntime) -> None:
        for websocket in list(runtime.subscribers_events):
            try:
                await websocket.close(code=1000)
            except Exception:
                pass
        runtime.subscribers_events.clear()

        for websocket in list(runtime.subscribers_debug):
            try:
                await websocket.close(code=1000)
            except Exception:
                pass
        runtime.subscribers_debug.clear()

    async def _broadcast_event(
        self,
        runtime: SessionRuntime,
        event: dict[str, Any],
        target: set[WebSocket] | None = None,
    ) -> None:
        subscribers = target or set(runtime.subscribers_events)

        for websocket in list(subscribers):
            try:
                await asyncio.wait_for(
                    websocket.send_text(json.dumps(event, default=self._json_default)),
                    timeout=0.25,
                )
            except Exception:
                runtime.subscribers_events.discard(websocket)

    async def _broadcast_debug_frame(self, runtime: SessionRuntime, frame_bytes: bytes) -> None:
        for websocket in list(runtime.subscribers_debug):
            try:
                await asyncio.wait_for(
                    websocket.send_bytes(frame_bytes),
                    timeout=0.25,
                )
            except Exception:
                runtime.subscribers_debug.discard(websocket)

    def _build_state_snapshot(
        self,
        runtime: SessionRuntime,
        track_events: list[dict[str, Any]],
        roi_events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        track_snapshots = []

        for track_info in runtime.current_tracks.values():
            last_seen_at = track_info.get("last_seen_at")
            track_snapshots.append({
                "track_id": track_info["track_id"],
                "bbox": track_info["bbox"],
                "centroid": track_info["centroid"],
                "confidence": track_info.get("confidence"),
                "active_roi_ids": track_info.get("active_roi_ids", []),
                "last_seen_at": last_seen_at.isoformat() if last_seen_at else None,
            })

        return self._build_envelope(
            event_type="state_snapshot",
            session_id=runtime.stream_session_id,
            payload={
                "session_state": runtime.status.value,
                "current_count": runtime.current_count,
                "tracks": track_snapshots,
                "roi_events": [self._serialize_event(item) for item in roi_events],
                "track_events": [self._serialize_event(item) for item in track_events],
            },
        )

    def _build_envelope(
        self,
        event_type: str,
        session_id: str,
        payload: dict[str, Any],
        event_timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        return {
            "event_type": event_type,
            "event_timestamp": (event_timestamp or datetime.now(timezone.utc)).isoformat(),
            "session_id": session_id,
            "payload": payload,
        }

    def _serialize_event(self, event: dict[str, Any]) -> dict[str, Any]:
        return {
            "event_type": event["event_type"],
            "event_timestamp": self._json_default(event["event_timestamp"]),
            "session_id": event["session_id"],
            "payload": event["payload"],
        }

    def _build_session_response(self, runtime: SessionRuntime) -> CameraSessionResponse:
        return CameraSessionResponse(
            stream_session_id=runtime.stream_session_id,
            camera_id=runtime.camera_id,
            source_type=runtime.source_type,
            status=runtime.status,
            target_fps=runtime.target_fps,
            debug_enabled=runtime.debug_enabled,
            debug_interval_ms=runtime.debug_interval_ms,
            roi_count=len(runtime.roi_config),
            current_count=runtime.current_count,
            active_track_count=len(runtime.current_tracks),
            started_at=runtime.started_at,
            stopped_at=runtime.stopped_at,
            failure_reason=runtime.failure_reason,
            ws_endpoints=CameraSessionWebSocketEndpoints(
                ingest=f"/api/camera-sessions/{runtime.stream_session_id}/ingest",
                events=f"/api/camera-sessions/{runtime.stream_session_id}/events",
                debug_frame=f"/api/camera-sessions/{runtime.stream_session_id}/debug-frame",
            ),
        )

    def _get_runtime(self, stream_session_id: str) -> SessionRuntime:
        runtime = self._runtimes.get(stream_session_id)

        if runtime is None:
            raise HTTPException(status_code=404, detail="Khong tim thay camera session.")

        return runtime

    def _is_newer_packet(self, incoming: FramePacket, current: FramePacket) -> bool:
        if incoming.timestamp > current.timestamp:
            return True

        if incoming.timestamp == current.timestamp:
            incoming_frame_id = incoming.frame_id if incoming.frame_id is not None else -1
            current_frame_id = current.frame_id if current.frame_id is not None else -1
            return incoming_frame_id > current_frame_id

        return False

    def _json_default(self, value):
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)


realtime_camera_session_service = RealtimeCameraSessionService()
