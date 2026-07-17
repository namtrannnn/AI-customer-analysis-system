from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


ProcessingJobStatus = Literal["pending", "running", "completed", "failed", "cancelled"]


class StreamProgressPayload(BaseModel):
    # Payload dùng chung cho REST status và WebSocket progress event.
    current_frame: int = 0
    total_frames: int = 0
    fps: float = 0
    progress_percent: int = 0


class StreamDetectionPayload(BaseModel):
    # Detection realtime gửi cho frontend ve bounding box/identity overlay.
    frame_index: int
    track_id: int
    anonymous_code: str
    confidence: float = 0
    bbox: list[float] = Field(default_factory=list)
    customer_id: int | None = None
    customer_name: str | None = None
    customer_avatar: str | None = None


class ProcessingJobCreateResponse(BaseModel):
    # Response tối thiểu của BE-02: FE dùng job_id để polling hoặc connect WebSocket.
    job_id: str
    status: ProcessingJobStatus


class ProcessingJobStatusResponse(BaseModel):
    # Snapshot đầy đủ của BE-03, được tạo từ ProcessingJobState.snapshot().
    job_id: str
    file_name: str | None = None
    status: ProcessingJobStatus
    ai_job_id: str | None = None
    processing_session_id: str | None = None
    progress: StreamProgressPayload | None = None
    error: str | None = None
    result: dict[str, Any] | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
