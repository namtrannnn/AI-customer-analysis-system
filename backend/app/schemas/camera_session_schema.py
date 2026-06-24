from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class CameraSourceType(str, Enum):
    BROWSER_WEBCAM = "browser_webcam"


class CameraSessionStatus(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class RoiPoint(BaseModel):
    x: float
    y: float


class RoiPolygonConfig(BaseModel):
    zone_key: str = Field(..., min_length=1, max_length=100)
    zone_name: str | None = Field(default=None, max_length=100)
    points: list[RoiPoint] = Field(..., min_length=3)


class CameraSessionCreateRequest(BaseModel):
    camera_id: int = Field(..., gt=0)
    source_type: CameraSourceType = CameraSourceType.BROWSER_WEBCAM
    target_fps: float = Field(default=5.0, ge=1.0, le=10.0)
    debug_enabled: bool = False
    debug_interval_ms: int = Field(default=500, ge=300, le=1000)
    roi_config: list[RoiPolygonConfig] = Field(default_factory=list)


class CameraSessionRoiUpdateRequest(BaseModel):
    roi_config: list[RoiPolygonConfig] = Field(default_factory=list)


class CameraSessionWebSocketEndpoints(BaseModel):
    ingest: str
    events: str
    debug_frame: str


class CameraSessionResponse(BaseModel):
    stream_session_id: str
    camera_id: int
    source_type: CameraSourceType
    status: CameraSessionStatus
    target_fps: float
    debug_enabled: bool
    debug_interval_ms: int
    roi_count: int
    current_count: int
    active_track_count: int
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    failure_reason: str | None = None
    ws_endpoints: CameraSessionWebSocketEndpoints


class TrackSnapshot(BaseModel):
    track_id: int
    bbox: list[int]
    centroid: list[float]
    confidence: float | None = None
    active_roi_ids: list[str] = Field(default_factory=list)
    last_seen_at: datetime


class RealtimeEventEnvelope(BaseModel):
    event_type: str
    event_timestamp: datetime
    session_id: str
    payload: dict


class SessionStatusSnapshot(BaseModel):
    stream_session_id: str
    camera_id: int
    status: CameraSessionStatus
    current_count: int
    tracks: list[TrackSnapshot] = Field(default_factory=list)
    debug_enabled: bool
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    failure_reason: str | None = None

    model_config = ConfigDict(from_attributes=True)
