from fastapi import APIRouter, UploadFile, File, Depends
from app.schemas.video_schema import VideoAnalysisResponse
from app.services import video_service
from app.core.dependencies import RequirePermission
from app.schemas.response_schema import StandardResponse

router = APIRouter(prefix="/api/videos", tags=["Video Processing"])

# PB01: Upload video để hệ thống phân tích khách hàng
@router.post("/upload", response_model=StandardResponse[VideoAnalysisResponse])
async def upload_video_for_analysis(
    file: UploadFile = File(...),
    # 1. MIDDLEWARE KIỂM TRA QUYỀN: Chỉ ai có mã quyền mới được đi qua
    current_user = Depends(RequirePermission("camera.manage")) 
):
    """
    API Nhận video từ Client, xử lý qua AI Pipeline và trả về kết quả thống kê.
    Video không được lưu trữ trên server (Chạy qua RAM/TempFile).
    """
    # 2. Xử lý logic AI (Lấy file tải lên xử lý qua hàm đã viết ở BE-08)
    result = await video_service.process_temporary_video(file)
    
    # 3. CHUẨN HÓA RESPONSE: Bọc dữ liệu kết quả AI vào trong chuẩn chung của hệ thống
    return StandardResponse(
        status="success",
        message="Phân tích video thành công. File tạm đã được tự động hủy.",
        data=result
    )