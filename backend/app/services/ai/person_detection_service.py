import numpy as np
from ultralytics import YOLO

class PersonDetectionService:
    def __init__(self, model_path: str = "yolov8s.pt"):
        """
        Khởi tạo service và tải mô hình YOLOv8 vào bộ nhớ.
        Lần chạy đầu tiên, thư viện sẽ tự động tải file yolov8s.pt về máy nếu chưa có.
        """
        # Load mô hình YOLOv8 bản Small (Cân bằng tốt nhất giữa tốc độ và độ chính xác)
        self.model = YOLO(model_path)

    def detect_persons(
            self, 
            frame: np.ndarray, 
            conf_threshold: float = 0.3, 
            frame_index: int = 0, 
            img_path: str = ""
        ) -> list[dict]:
        """
        Nhận vào một frame ảnh (numpy array) và trả về danh sách các người phát hiện được.
        """
        
        # Chạy dự đoán:
        # classes=[0] -> Chỉ lấy class 0 (Person), bỏ qua xe cộ, chó mèo...
        # verbose=False -> Tắt log in ra terminal để tránh rác màn hình console
        results = self.model(
            frame, 
            classes=[0], 
            conf=conf_threshold, 
            verbose=False,
            imgsz=1280
        )

        detected_persons = []
        
        # Kết quả trả về của YOLO luôn là một list (do có thể truyền vào nhiều ảnh cùng lúc).
        # Ở đây ta truyền 1 ảnh nên chỉ lấy results[0]
        boxes = results[0].boxes

            # SỬ DỤNG ENUMERATE ĐỂ LẤY SỐ THỨ TỰ (Bắt đầu từ 1)
        for index, box in enumerate(boxes, start=1):
            # Lấy tọa độ bounding box [x_min, y_min, x_max, y_max] và ép về số nguyên
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
            # Lấy độ tin cậy (Confidence score)
            confidence = float(box.conf[0].cpu().numpy())

            detected_persons.append({
                "person_index": index, # Bổ sung trường này
                "bbox": [int(x1), int(y1), int(x2), int(y2)],
                "confidence": round(confidence, 2),
                "frame_index": frame_index,
                "img_path": img_path
            })

        return detected_persons

# Khởi tạo sẵn một instance (Singleton) để import và dùng chung ở các file khác
person_detector = PersonDetectionService()