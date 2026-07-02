from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


# ─── Point (tọa độ tương đối 0..1) ───────────────────────────────────────────
class PointSchema(BaseModel):
    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)


ZoneType = Literal[
    "entrance",      # Lối vào
    "checkout",      # Quầy thanh toán
    "display",       # Khu trưng bày
    "fitting_room",  # Phòng thử đồ
    "promotion",     # Khu khuyến mãi
    "other",         # Khác
]


# ─── Zone Create ──────────────────────────────────────────────────────────────
class ZoneCreate(BaseModel):
    zone_name: str = Field(..., min_length=1, max_length=100)
    zone_type: ZoneType = "other"
    description: str | None = None
    polygon: list[PointSchema] = Field(..., min_length=3)
    color: str = Field(default="#3b82f6", max_length=20)


# ─── Zone Update (PATCH — tất cả optional) ───────────────────────────────────
class ZoneUpdate(BaseModel):
    zone_name: str | None = Field(default=None, min_length=1, max_length=100)
    zone_type: ZoneType | None = None
    description: str | None = None
    polygon: list[PointSchema] | None = Field(default=None, min_length=3)
    color: str | None = Field(default=None, max_length=20)


# ─── Zone Response ────────────────────────────────────────────────────────────
class ZoneResponse(BaseModel):
    id: int
    zone_name: str
    zone_type: str
    description: str | None
    polygon: list[PointSchema]
    color: str
    total_visits: int
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


# ─── Track point ──────────────────────────────────────────────────────────────
class TrackPointResponse(BaseModel):
    x: float
    y: float
    zone_id: int | None
    tracked_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ─── Movement Track Response ──────────────────────────────────────────────────
class MovementTrackResponse(BaseModel):
    id: int
    person_profile_id: int
    anonymous_id: str
    visit_session_id: int
    color: str
    entry_time: datetime | None
    exit_time: datetime | None
    duration_seconds: int | None
    zones_visited: list[int]
    points: list[TrackPointResponse]
    customer_id: int | None = None
    customer_name: str | None = None
    customer_avatar: str | None = None

    model_config = ConfigDict(from_attributes=True)


# ─── Zone Visit Response ──────────────────────────────────────────────────────
class ZoneVisitResponse(BaseModel):
    id: int
    zone_id: int
    zone_name: str
    person_profile_id: int
    anonymous_id: str
    enter_time: datetime
    leave_time: datetime | None
    duration_seconds: int | None

    model_config = ConfigDict(from_attributes=True)
