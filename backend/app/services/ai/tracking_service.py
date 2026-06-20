import os

import numpy as np
from typing import List, Dict
from ultralytics import YOLO

class TrackingService:
    """
    AI-09 Multi Object Tracking Service
    Sử dụng thuật toán ByteTrack được tích hợp sẵn trong YOLOv8.
    Có khả năng gán ID cố định cho một người xuyên suốt video, dự đoán hướng đi 
    ngay cả khi người đó bị che khuất trong vài frame (Occlusion).
    """

    def __init__(self, model_path: str = "yolov8s.pt", tracker_type: str = "bytetrack.yaml"):
        # Tải model YOLOv8
        self.model = YOLO(model_path)
        self.tracker_type = tracker_type

    def track_persons_in_frame(
        self, 
        frame: np.ndarray, 
        frame_index: int, 
        img_path: str, 
        conf_threshold: float = 0.4
    ) -> List[Dict]:
        """
        Quét frame và trả về danh sách người kèm theo ID duy nhất (track_id).
        """
        
        # Tham số persist=True là BẮT BUỘC để mô hình nhớ được ID của frame trước đó
        results = self.model.track(
            frame, 
            classes=[0], # Chỉ lấy class Person
            conf=conf_threshold, 
            tracker=self.tracker_type, 
            persist=True, 
            verbose=False
        )

        tracked_persons = []
        
        # Kiểm tra xem có bắt được người nào không và người đó đã được gán ID chưa
        if results[0].boxes is not None and results[0].boxes.id is not None:
            
            # Lấy tọa độ, ID và độ tự tin
            boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
            track_ids = results[0].boxes.id.cpu().numpy().astype(int)
            confs = results[0].boxes.conf.cpu().numpy()

            for box, track_id, conf in zip(boxes, track_ids, confs):
                x1, y1, x2, y2 = box
                
                tracked_persons.append({
                    "track_id": int(track_id), # QUAN TRỌNG NHẤT: ID do AI gán
                    "bbox": [int(x1), int(y1), int(x2), int(y2)],
                    "confidence": round(float(conf), 2),
                    "frame_index": frame_index,
                    "img_path": img_path
                })
                
        return tracked_persons

# Khởi tạo instance
# 1. Lấy đường dẫn thư mục hiện tại (chứa tracking_service.py)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Tạo đường dẫn tuyệt đối cho file YAML và file YOLO
YOLO_MODEL_PATH = os.path.join(CURRENT_DIR, "models", "yolov8s.pt") # 

# 3. Truyền đường dẫn tuyệt đối vào Service
tracker_service = TrackingService(
    model_path=YOLO_MODEL_PATH
)