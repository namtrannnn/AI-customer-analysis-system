from fastapi import APIRouter, UploadFile, File, Depends
from app.schemas.video_schema import VideoAnalysisResponse
from app.services import video_service
from app.core.dependencies import RequirePermission
from app.schemas.response_schema import StandardResponse
from app.database.session import get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/videos", tags=["Video Processing"])

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