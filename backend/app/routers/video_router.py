import asyncio
import os
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect

from app.core.dependencies import RequirePermission
from app.schemas.processing_job_schema import (
    ProcessingJobCreateResponse,
    ProcessingJobStatusResponse,
)
from app.schemas.response_schema import StandardResponse
from app.services.processing_job_manager import processing_job_manager
from app.services.streaming_video_service import (
    MAX_VIDEO_SIZE,
    streaming_video_service,
    validate_video_upload,
)

router = APIRouter(prefix="/api/videos", tags=["Video Processing"])


@router.post("/jobs", response_model=StandardResponse[ProcessingJobCreateResponse])
async def create_processing_job(
    file: UploadFile = File(...),
    current_user=Depends(RequirePermission("camera.manage")),
):
    """
    Tạo processing job tạm thời trong memory và chạy AI pipeline ở background.
    """
    # BE-02: Nhận video upload, validate, ghi ra file tạm rồi tạo job.
    # Request trả về ngay job_id; AI pipeline chạy tiếp ở background.
    validate_video_upload(file)

    video_bytes = await file.read()
    if len(video_bytes) > MAX_VIDEO_SIZE:
        raise HTTPException(status_code=413, detail="File quá lớn. Vui lòng upload video dưới 50MB.")

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
    # BE-03: Lấy snapshot hiện tại của job trong memory để FE polling trạng thái.
    job = processing_job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Không tìm thấy processing job.")

    return StandardResponse(
        status="success",
        message="Processing job status",
        data=ProcessingJobStatusResponse(**job.snapshot()),
    )


@router.websocket("/jobs/{job_id}/stream")
async def stream_processing_job(websocket: WebSocket, job_id: str):
    await websocket.accept()
    # BE-04: Mỗi WebSocket client được gắn một queue riêng để nhận event realtime.
    queue = await processing_job_manager.subscribe(job_id)
    if queue is None:
        await websocket.send_json({"type": "error", "message": "Không tìm thấy processing job."})
        await websocket.close(code=1008)
        return

    try:
        while True:
            # Event có thể là progress, detection, complete hoặc error.
            # Khi complete/error thì đóng stream vì job đã kết thúc.
            event = await queue.get()
            await websocket.send_json(event)
            if event.get("type") in {"complete", "error"}:
                break
    except WebSocketDisconnect:
        pass
    finally:
        processing_job_manager.unsubscribe(job_id, queue)
