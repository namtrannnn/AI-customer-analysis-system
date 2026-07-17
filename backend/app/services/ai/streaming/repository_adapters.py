from __future__ import annotations

from typing import Any

from .streaming_dtos import DetectionResult
from .streaming_video_pipeline_service import ProcessingJobState


class DetectionRepositoryAdapter:
    """
    Adapter mẫu cho BE-05.
    Thay phần thân save_detection bằng SQLAlchemy repository thực tế của dự án.
    """

    def __init__(self, repository: Any) -> None:
        self.repository = repository

    def __call__(self, detection: DetectionResult) -> None:
        self.repository.upsert_detection(
            detection_id=detection.detection_id,
            processing_session_id=detection.session_id,
            processing_job_id=detection.job_id,
            frame_index=detection.frame_index,
            timestamp_seconds=detection.timestamp_seconds,
            track_id=detection.track_id,
            anonymous_code=detection.anonymous_code,
            bbox=detection.bbox,
            display_stage=detection.display_stage,
            status=detection.status,
            confidence=detection.confidence,
            observation_count=detection.observation_count,
        )


class ProcessingJobRepositoryAdapter:
    """Adapter mẫu cho BE-01/BE-02/BE-03."""

    def __init__(self, repository: Any) -> None:
        self.repository = repository

    def __call__(self, state: ProcessingJobState) -> None:
        self.repository.upsert_job(
            job_id=state.job_id,
            processing_session_id=state.session_id,
            video_path=state.video_path,
            status=state.status.value,
            processed_frames=state.processed_frames,
            total_frames=state.total_frames,
            progress_percent=state.progress_percent,
            processing_fps=state.processing_fps,
            error=state.error,
            result=state.result,
            started_at=state.started_at,
            completed_at=state.completed_at,
        )
