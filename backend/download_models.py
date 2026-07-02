import os
import urllib.request

# Danh sách các mô hình cần tải: { Tên file : Link tải chuẩn }
MODELS_TO_DOWNLOAD = {
    # 1. AI-04: Trích xuất khuôn mặt (SFace)
    "face_recognition_sface_2021dec.onnx": "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
    
    # 2. AI-03: Cắt khuôn mặt (YuNet 2023)
    "face_detection_yunet_2023mar.onnx": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    
    # 3. AI-02 & AI-09: Phát hiện người & Tracking (YOLOv8m)
    "yolov8m.pt": "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8m.pt"
}

def download_all_models():
    # Lấy đường dẫn thư mục hiện tại và tự động chọc vào đúng thư mục models
    current_dir = os.path.dirname(os.path.abspath(__file__))
    models_dir = os.path.join(current_dir, "app", "services", "ai", "models")
    
    # Tạo thư mục nếu chưa có
    os.makedirs(models_dir, exist_ok=True)
    print(f"Thư mục chứa mô hình: {models_dir}\n")

    for filename, url in MODELS_TO_DOWNLOAD.items():
        file_path = os.path.join(models_dir, filename)
        
        # Nếu file đã tồn tại và có dung lượng lớn hơn 0, bỏ qua không tải lại
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            print(f"Đã có sẵn: {filename}")
            continue

        print(f"Đang tải {filename}... Vui lòng đợi!")
        try:
            # Tải file về và lưu đúng vị trí
            urllib.request.urlretrieve(url, file_path)
            print(f"Tải thành công: {filename}\n")
        except Exception as e:
            print(f"Lỗi khi tải {filename}: {e}\n")
            
            # Xóa file rác nếu bị lỗi giữa chừng
            if os.path.exists(file_path):
                os.remove(file_path)

if __name__ == "__main__":
    print("="*50)
    print("BẮT ĐẦU ĐỒNG BỘ MÔ HÌNH AI CHO HỆ THỐNG")
    print("="*50)
    download_all_models()
    print("="*50)
    print("HOÀN TẤT! Hệ thống đã sẵn sàng chạy.")