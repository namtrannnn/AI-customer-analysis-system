from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional


class CameraCreate(BaseModel):
    camera_name: str = Field(..., min_length=1, max_length=100)
    camera_position: str | None = Field(default=None, max_length=100)
    nvr_name: str | None = Field(default=None, max_length=100)
    nvr_model: str | None = Field(default=None, max_length=100)
    channel_no: int | None = Field(default=None, ge=1)
    rtsp_url: str | None = None
    preview_url: str | None = None
    transport: str = Field(default="tcp")
    mode: str = Field(default="anonymous")
    status: str = Field(default="active")

    @field_validator("transport")
    @classmethod
    def validate_transport(cls, v: str) -> str:
        if v not in ("tcp", "udp"):
            raise ValueError("transport phải là 'tcp' hoặc 'udp'")
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v not in ("anonymous", "identified"):
            raise ValueError("mode phải là 'anonymous' hoặc 'identified'")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in ("active", "inactive", "maintenance", "error"):
            raise ValueError("status không hợp lệ")
        return v


class CameraUpdate(BaseModel):
    camera_name: str | None = Field(default=None, min_length=1, max_length=100)
    camera_position: str | None = None
    nvr_name: str | None = None
    nvr_model: str | None = None
    channel_no: int | None = None
    rtsp_url: str | None = None
    preview_url: str | None = None
    transport: str | None = None
    mode: str | None = None
    status: str | None = None

    @field_validator("transport")
    @classmethod
    def validate_transport(cls, v: str | None) -> str | None:
        if v is not None and v not in ("tcp", "udp"):
            raise ValueError("transport phải là 'tcp' hoặc 'udp'")
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str | None) -> str | None:
        if v is not None and v not in ("anonymous", "identified"):
            raise ValueError("mode phải là 'anonymous' hoặc 'identified'")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in ("active", "inactive", "maintenance", "error"):
            raise ValueError("status không hợp lệ")
        return v


class CameraResponse(BaseModel):
    id: int
    camera_name: str
    camera_position: str | None
    nvr_name: str | None
    nvr_model: str | None
    channel_no: int | None
    # rtsp_url KHÔNG trả ra FE — bảo mật credential
    preview_url: str | None
    transport: str
    mode: str
    status: str
    last_connection_status: str | None
    last_connected_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
