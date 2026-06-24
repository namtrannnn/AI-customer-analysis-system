import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, WebSocketException
from sqlalchemy.orm import Session

from app.core.dependencies import RequirePermission, authenticate_websocket_user
from app.database.session import get_db
from app.schemas.camera_session_schema import (
    CameraSessionCreateRequest,
    CameraSessionResponse,
    CameraSessionRoiUpdateRequest,
)
from app.schemas.response_schema import StandardResponse
from app.services.realtime_camera_session_service import (
    FramePacket,
    realtime_camera_session_service,
)
from app.utils.response import success_response


router = APIRouter(prefix="/api/camera-sessions", tags=["Camera Sessions"])


@router.post("", response_model=StandardResponse[CameraSessionResponse])
async def create_camera_session(
    payload: CameraSessionCreateRequest,
    current_user=Depends(RequirePermission("camera.manage")),
):
    session = await realtime_camera_session_service.create_session(payload)
    return success_response(
        data=session,
        message="Tao camera session realtime thanh cong.",
    )


@router.post("/{stream_session_id}/start", response_model=StandardResponse[CameraSessionResponse])
async def start_camera_session(
    stream_session_id: str,
    current_user=Depends(RequirePermission("camera.manage")),
):
    session = await realtime_camera_session_service.start_session(stream_session_id)
    return success_response(
        data=session,
        message="Da start camera session realtime.",
    )


@router.post("/{stream_session_id}/stop", response_model=StandardResponse[CameraSessionResponse])
async def stop_camera_session(
    stream_session_id: str,
    current_user=Depends(RequirePermission("camera.manage")),
):
    session = await realtime_camera_session_service.stop_session(stream_session_id)
    return success_response(
        data=session,
        message="Da stop camera session realtime.",
    )


@router.get("/{stream_session_id}", response_model=StandardResponse[CameraSessionResponse])
async def get_camera_session(
    stream_session_id: str,
    current_user=Depends(RequirePermission("camera.view")),
):
    session = realtime_camera_session_service.get_session(stream_session_id)
    return success_response(
        data=session,
        message="Lay trang thai camera session realtime thanh cong.",
    )


@router.patch("/{stream_session_id}/roi", response_model=StandardResponse[CameraSessionResponse])
async def update_camera_session_roi(
    stream_session_id: str,
    payload: CameraSessionRoiUpdateRequest,
    current_user=Depends(RequirePermission("camera.manage")),
):
    session = await realtime_camera_session_service.update_session_roi(
        stream_session_id,
        [roi.model_dump() for roi in payload.roi_config],
    )
    return success_response(
        data=session,
        message="Cap nhat ROI runtime thanh cong.",
    )


@router.websocket("/{stream_session_id}/ingest")
async def camera_session_ingest_ws(
    websocket: WebSocket,
    stream_session_id: str,
    db: Session = Depends(get_db),
):
    try:
        authenticate_websocket_user(
            websocket=websocket,
            db=db,
            required_permission="camera.manage",
        )
    except WebSocketException as exc:
        await websocket.close(code=exc.code, reason=exc.reason)
        return

    await websocket.accept()
    pending_metadata: dict = {}

    try:
        while True:
            message = await websocket.receive()

            if message.get("type") == "websocket.disconnect":
                break

            if message.get("text") is not None:
                try:
                    pending_metadata = json.loads(message["text"])
                except json.JSONDecodeError:
                    pending_metadata = {}
                continue

            frame_bytes = message.get("bytes")
            if frame_bytes is None:
                continue

            frame_id = pending_metadata.get("frame_id")
            if frame_id is None:
                frame_id = realtime_camera_session_service.next_frame_id(stream_session_id)

            packet = FramePacket(
                session_id=stream_session_id,
                frame_id=int(frame_id),
                timestamp=_parse_timestamp(pending_metadata.get("timestamp")),
                frame_bytes=frame_bytes,
                width=pending_metadata.get("width"),
                height=pending_metadata.get("height"),
            )

            pending_metadata = {}
            await realtime_camera_session_service.ingest_frame_packet(stream_session_id, packet)
    except WebSocketDisconnect:
        return


@router.websocket("/{stream_session_id}/events")
async def camera_session_events_ws(
    websocket: WebSocket,
    stream_session_id: str,
    db: Session = Depends(get_db),
):
    try:
        authenticate_websocket_user(
            websocket=websocket,
            db=db,
            required_permission="camera.view",
        )
    except WebSocketException as exc:
        await websocket.close(code=exc.code, reason=exc.reason)
        return

    await websocket.accept()
    await realtime_camera_session_service.register_event_subscriber(stream_session_id, websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        realtime_camera_session_service.unregister_event_subscriber(stream_session_id, websocket)


@router.websocket("/{stream_session_id}/debug-frame")
async def camera_session_debug_frame_ws(
    websocket: WebSocket,
    stream_session_id: str,
    db: Session = Depends(get_db),
):
    try:
        authenticate_websocket_user(
            websocket=websocket,
            db=db,
            required_permission="camera.view",
        )
    except WebSocketException as exc:
        await websocket.close(code=exc.code, reason=exc.reason)
        return

    await websocket.accept()
    realtime_camera_session_service.register_debug_subscriber(stream_session_id, websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        realtime_camera_session_service.unregister_debug_subscriber(stream_session_id, websocket)


def _parse_timestamp(raw_timestamp) -> datetime:
    if not raw_timestamp:
        return datetime.now(timezone.utc)

    try:
        parsed = datetime.fromisoformat(str(raw_timestamp).replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)
