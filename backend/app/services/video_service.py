import tempfile
import os
from fastapi import UploadFile, HTTPException
from app.schemas.video_schema import VideoAnalysisResponse

async def process_temporary_video(file: UploadFile) -> VideoAnalysisResponse:
    # Validate định dạng
    if not file.content_type.startswith("video/"):
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

        video_path = temp_video.name
        
        # =====================================================================
        # TẠI ĐÂY LÀ NƠI GỌI AI PIPELINE (AI-06 Video Processing Pipeline)
        # OpenCV (cv2.VideoCapture) có thể đọc trực tiếp từ video_path này.
        # Ví dụ: ai_results = ai_pipeline_service.process_video(video_path)
        # =====================================================================
        
        # MOCK DATA: Trả về kết quả giả lập theo Schema đã định nghĩa
        # (Sau này sẽ thay bằng kết quả thực tế từ AI)
        mock_result = {
            "total_customers": 2,
            "new_customers": 1,
            "returning_customers": 1,
            "detected_customers": [
                {"anonymous_id": "ANO_001", "customer_type": "new", "confidence": 0.95},
                {"anonymous_id": "ANO_002", "customer_type": "returning", "confidence": 0.88}
            ],
            "message": "Phân tích video thành công. File tạm đã được hủy."
        }
        
        return VideoAnalysisResponse(**mock_result)
        
    # KHI CODE CHẠY ĐẾN ĐÂY: File temp_video đã hoàn toàn bị xóa khỏi hệ thống.