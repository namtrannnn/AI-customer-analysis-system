from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional
import time
import uuid


class ProcessingStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(slots=True)
class FramePacket:
    session_id: str
    job_id: str
    frame_index: int
    total_frames: int
    timestamp_seconds: float
    image: Any = None
    image_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass(slots=True)
class DetectionResult:
    detection_id: str
    session_id: str
    job_id: str
    frame_index: int
    timestamp_seconds: float
    track_id: int
    anonymous_code: Optional[str]
    bbox: List[float]
    display_stage: str
    status: str
    observation_count: int = 0
    confidence: Optional[float] = None
    operation: str = "upsert"

    @classmethod
    def create(cls, **kwargs: Any) -> "DetectionResult":
        kwargs.setdefault("detection_id", str(uuid.uuid4()))
        return cls(**kwargs)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class FrameResultEvent:
    session_id: str
    job_id: str
    frame_index: int
    processed_frames: int
    total_frames: int
    timestamp_seconds: float
    progress_percent: float
    processing_fps: float
    detections: List[DetectionResult]
    annotated_frame_path: Optional[str] = None
    event_type: str = "frame_result"

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["type"] = data.pop("event_type")
        data["persons"] = [item.to_dict() for item in self.detections]
        data.pop("detections", None)
        return data


@dataclass(slots=True)
class PipelineCompletedEvent:
    session_id: str
    job_id: str
    status: str
    total_frames: int
    processed_frames: int
    processing_fps: float
    result: Dict[str, Any]
    event_type: str = "pipeline_result"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.event_type,
            "session_id": self.session_id,
            "job_id": self.job_id,
            "status": self.status,
            "progress_percent": 100.0,
            "total_frames": self.total_frames,
            "processed_frames": self.processed_frames,
            "processing_fps": self.processing_fps,
            **self.result,
        }
