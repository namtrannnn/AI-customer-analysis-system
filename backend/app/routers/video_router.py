import asyncio
import os
import tempfile

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, WebSocket, WebSocketDisconnect
from app.schemas.video_schema import VideoAnalysisResponse
from app.schemas.processing_job_schema import (
    ProcessingJobCreateResponse,
    ProcessingJobStatusResponse,
)
from app.services import video_service
from app.services.processing_job_manager import processing_job_manager
from app.services.streaming_video_service import (
    MAX_VIDEO_SIZE,
    streaming_video_service,
    validate_video_upload,
)
from app.core.dependencies import RequirePermission
from app.schemas.response_schema import StandardResponse
from app.database.session import get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/videos", tags=["Video Processing"])


@router.post("/jobs", response_model=StandardResponse[ProcessingJobCreateResponse])
async def create_processing_job(
    file: UploadFile = File(...),
    current_user=Depends(RequirePermission("camera.manage")),
):
    """
    Tao processing job tam thoi trong memory va chay AI pipeline o background.
    """
    validate_video_upload(file)

    video_bytes = await file.read()
    if len(video_bytes) > MAX_VIDEO_SIZE:
        raise HTTPException(status_code=413, detail="File qua lon. Vui long upload video duoi 50MB.")

    suffix = os.path.splitext(file.filename or "upload.mp4")[1] or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_video:
        temp_video.write(video_bytes)
        temp_video.flush()
        os.fsync(temp_video.fileno())
        temp_video_path = temp_video.name

    processing_job_manager.bind_loop()
    job = await processing_job_manager.create_job(
        file_name=file.filename or "upload.mp4",
        temp_video_path=temp_video_path,
    )
    asyncio.create_task(streaming_video_service.start_job(job.job_id))

    return StandardResponse(
        status="success",
        message="Processing job created",
        data=ProcessingJobCreateResponse(job_id=job.job_id, status=job.status),
    )


@router.get("/jobs/{job_id}", response_model=StandardResponse[ProcessingJobStatusResponse])
async def get_processing_job_status(
    job_id: str,
    current_user=Depends(RequirePermission("camera.manage")),
):
    job = processing_job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Khong tim thay processing job.")

    return StandardResponse(
        status="success",
        message="Processing job status",
        data=ProcessingJobStatusResponse(**job.snapshot()),
    )


@router.websocket("/jobs/{job_id}/stream")
async def stream_processing_job(websocket: WebSocket, job_id: str):
    await websocket.accept()
    queue = await processing_job_manager.subscribe(job_id)
    if queue is None:
        await websocket.send_json({"type": "error", "message": "Khong tim thay processing job."})
        await websocket.close(code=1008)
        return

    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event)
            if event.get("type") in {"complete", "error"}:
                break
    except WebSocketDisconnect:
        pass
    finally:
        processing_job_manager.unsubscribe(job_id, queue)

@router.post("/upload", response_model=StandardResponse[VideoAnalysisResponse])
async def upload_video_for_analysis(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user = Depends(RequirePermission("camera.manage")),
):
    """
    API nhận video, chạy AI pipeline nhận diện + tracking, trả về kết quả.
    Tự động lưu tracking vào DB nếu đã có zones.
    """
    result = await video_service.process_temporary_video(file, db=db)

    return StandardResponse(
        status="success",
        message=result.message,
        data=result,
    )
