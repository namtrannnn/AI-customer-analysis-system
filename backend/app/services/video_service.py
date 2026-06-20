import tempfile
from fastapi import UploadFile, HTTPException
from app.schemas.video_schema import VideoAnalysisResponse
from app.services.ai.video_pipeline_service import video_pipeline_service

async def process_temporary_video(file: UploadFile) -> VideoAnalysisResponse:
    # Validate định dạng
    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Sai định dạng. File tải lên bắt buộc phải là video.")

    # Validate dung lượng (Tối ưu hóa: Đọc Header thay vì đọc Data)
    MAX_SIZE = 50 * 1024 * 1024 # 50 MB
    
    if file.size and file.size > MAX_SIZE:
        raise HTTPException(status_code=413, detail="File quá lớn. Vui lòng upload video dưới 50MB.")

    # Đọc nội dung file vào memory SAU KHI đã chắc chắn file an toàn
    video_bytes = await file.read()
    
    # Kiểm tra dung lượng (Ví dụ: chặn file > 50MB)
    if len(video_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File quá lớn. Vui lòng upload video dưới 50MB.")

    # Tạo file tạm thời (Sẽ TỰ ĐỘNG XÓA khi ra khỏi khối lệnh with)
    with tempfile.NamedTemporaryFile(delete=True, suffix=".mp4") as temp_video:
        # Ghi byte vào file tạm
        temp_video.write(video_bytes)
        temp_video.flush() # Đảm bảo data đã ghi xuống file tạm để AI có thể đọc

        pipeline_result = video_pipeline_service.process_video(temp_video.name)
        total_customers = len(pipeline_result.detected_customers)

        if total_customers == 0:
            message = (
                "Không phát hiện người trong video theo cấu hình hiện tại."
            )
        else:
            message = (
                "Phân tích video thành công. Đã chạy pipeline trích frame, "
                "phát hiện người và phát hiện khuôn mặt. Phân loại khách cũ/"
                "mới hiện tạm gán là mới cho đến khi tích hợp matching."
            )

        return VideoAnalysisResponse(
            total_customers=total_customers,
            new_customers=total_customers,
            returning_customers=0,
            detected_customers=[
                {
                    "anonymous_id": customer.anonymous_id,
                    "customer_type": customer.customer_type,
                    "confidence": customer.confidence,
                }
                for customer in pipeline_result.detected_customers
            ],
            message=message,
        )
        
    # KHI CODE CHẠY ĐẾN ĐÂY: File temp_video đã hoàn toàn bị xóa khỏi hệ thống.
