from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event, Lock, Thread
from typing import Any, Callable, Dict, Optional
import time
import uuid

from .streaming_dtos import (
    DetectionResult,
    FrameResultEvent,
    PipelineCompletedEvent,
    ProcessingStatus,
)
from .streaming_result_publisher import StreamingResultPublisher


@dataclass(slots=True)
class ProcessingJobState:
    session_id: str
    job_id: str
    video_path: str
    status: ProcessingStatus = ProcessingStatus.QUEUED
    processed_frames: int = 0
    total_frames: int = 0
    progress_percent: float = 0.0
    processing_fps: float = 0.0
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


class StreamingVideoPipelineService:
    """
    AI-01: adapter streaming bao quanh video_pipeline_live_stream_service hiện có.

    Không sửa thuật toán matching lõi. Mỗi payload frame của pipeline được chuẩn hóa,
    publish ngay cho UI, đồng thời hook persistence có thể lưu detection theo frame.
    """

    def __init__(
        self,
        pipeline_service: Any,
        publisher: Optional[StreamingResultPublisher] = None,
        detection_sink: Optional[Callable[[DetectionResult], None]] = None,
        job_state_sink: Optional[Callable[[ProcessingJobState], None]] = None,
    ) -> None:
        self.pipeline_service = pipeline_service
        self.publisher = publisher or StreamingResultPublisher()
        self.detection_sink = detection_sink
        self.job_state_sink = job_state_sink
        self._jobs: Dict[str, ProcessingJobState] = {}
        self._lock = Lock()
        self._cancel_events: Dict[str, Event] = {}

    def create_job(self, video_path: str, session_id: Optional[str] = None) -> ProcessingJobState:
        session_id = session_id or str(uuid.uuid4())
        job_id = str(uuid.uuid4())
        state = ProcessingJobState(
            session_id=session_id,
            job_id=job_id,
            video_path=video_path,
        )
        with self._lock:
            self._jobs[job_id] = state
            self._cancel_events[job_id] = Event()
        self._save_state(state)
        return state

    def get_job(self, job_id: str) -> Optional[ProcessingJobState]:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        event = self._cancel_events.get(job_id)
        if event is None:
            return False
        event.set()
        state = self.get_job(job_id)
        if state and state.status in (ProcessingStatus.QUEUED, ProcessingStatus.PROCESSING):
            state.status = ProcessingStatus.CANCELLED
            self._save_state(state)
        return True

    def start_job(self, job_id: str, *, background: bool = True, **pipeline_kwargs: Any):
        state = self.get_job(job_id)
        if state is None:
            raise KeyError(f"unknown job_id: {job_id}")

        if background:
            thread = Thread(
                target=self._run_job,
                args=(state,),
                kwargs=pipeline_kwargs,
                daemon=True,
                name=f"video-job-{job_id[:8]}",
            )
            thread.start()
            return thread
        return self._run_job(state, **pipeline_kwargs)

    def _run_job(self, state: ProcessingJobState, **pipeline_kwargs: Any) -> Dict[str, Any]:
        cancel_event = self._cancel_events[state.job_id]
        state.status = ProcessingStatus.PROCESSING
        state.started_at = time.time()
        started_perf = time.perf_counter()
        self._save_state(state)

        def on_frame(payload: Dict[str, Any], annotated_frame=None) -> None:
            if cancel_event.is_set():
                raise RuntimeError("processing cancelled")

            if payload.get("type") == "pipeline_result":
                return

            frame_index = int(payload.get("frame_index", -1))
            progress = float(payload.get("progress_percent", 0.0) or 0.0)
            persons = payload.get("persons") or []

            state.processed_frames += 1
            state.progress_percent = progress
            elapsed = max(1e-6, time.perf_counter() - started_perf)
            state.processing_fps = state.processed_frames / elapsed

            if progress > 0:
                estimated_total = round(state.processed_frames * 100.0 / progress)
                state.total_frames = max(state.total_frames, estimated_total)

            timestamp_seconds = (
                float(frame_index) / float(pipeline_kwargs.get("target_fps") or 1.0)
                if frame_index >= 0 else 0.0
            )

            detections = []
            for person in persons:
                detection = DetectionResult.create(
                    session_id=state.session_id,
                    job_id=state.job_id,
                    frame_index=frame_index,
                    timestamp_seconds=timestamp_seconds,
                    track_id=int(person.get("track_id", -1)),
                    anonymous_code=person.get("anonymous_code"),
                    bbox=[float(v) for v in (person.get("bbox") or [])[:4]],
                    display_stage=str(person.get("display_stage") or "PENDING"),
                    status=str(person.get("status") or ""),
                    observation_count=int(person.get("observation_count", 0) or 0),
                    confidence=person.get("confidence"),
                )
                detections.append(detection)
                if self.detection_sink is not None:
                    self.detection_sink(detection)

            event = FrameResultEvent(
                session_id=state.session_id,
                job_id=state.job_id,
                frame_index=frame_index,
                processed_frames=state.processed_frames,
                total_frames=state.total_frames,
                timestamp_seconds=timestamp_seconds,
                progress_percent=progress,
                processing_fps=state.processing_fps,
                detections=detections,
                annotated_frame_path=payload.get("annotated_frame_path"),
            )
            self.publisher.publish(state.session_id, event.to_dict(), annotated_frame)
            self._save_state(state)

        try:
            result = self.pipeline_service.process_video(
                video_path=state.video_path,
                stream_callback=on_frame,
                **pipeline_kwargs,
            )
            state.result = result
            state.status = ProcessingStatus.COMPLETED
            state.progress_percent = 100.0
            state.completed_at = time.time()
            elapsed = max(1e-6, time.perf_counter() - started_perf)
            state.processing_fps = state.processed_frames / elapsed
            completed = PipelineCompletedEvent(
                session_id=state.session_id,
                job_id=state.job_id,
                status=state.status.value,
                total_frames=state.total_frames or state.processed_frames,
                processed_frames=state.processed_frames,
                processing_fps=state.processing_fps,
                result=result,
            )
            self.publisher.publish(state.session_id, completed.to_dict(), None)
            self._save_state(state)
            return result
        except Exception as exc:
            state.status = (
                ProcessingStatus.CANCELLED
                if cancel_event.is_set()
                else ProcessingStatus.FAILED
            )
            state.error = f"{type(exc).__name__}: {exc}"
            state.completed_at = time.time()
            self.publisher.publish(
                state.session_id,
                {
                    "type": "pipeline_error",
                    "session_id": state.session_id,
                    "job_id": state.job_id,
                    "status": state.status.value,
                    "error": state.error,
                },
                None,
            )
            self._save_state(state)
            raise

    def _save_state(self, state: ProcessingJobState) -> None:
        if self.job_state_sink is not None:
            self.job_state_sink(state)
