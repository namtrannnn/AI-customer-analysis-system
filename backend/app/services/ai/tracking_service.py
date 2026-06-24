import os
import numpy as np
from typing import List, Dict
from ultralytics import YOLO

class TrackingService:
    """
    AI-09 Multi Object Tracking Service
    Dùng BoTrack (IoU + appearance) để giảm ID swap khi người đứng gần nhau.
    Fallback về ByteTrack nếu BoTrack không khả dụng.
    """

    def __init__(self, model_path: str = "yolov8m.pt", tracker_type: str = "bytetrack.yaml"):
        self.model = YOLO(model_path)
        self.tracker_type = tracker_type
        self._buffer_patched = False

    def track_persons_in_frame(
        self,
        frame: np.ndarray,
        frame_index: int,
        img_path: str,
        conf_threshold: float = 0.4,
    ) -> List[Dict]:

        try:
            results = self.model.track(
                frame,
                classes=[0],
                conf=conf_threshold,
                tracker=self.tracker_type,
                persist=True,
                verbose=False,
            )
        except Exception:
            # Fallback về bytetrack nếu botrack không có
            results = self.model.track(
                frame,
                classes=[0],
                conf=conf_threshold,
                tracker="bytetrack.yaml",
                persist=True,
                verbose=False,
            )

        # Tăng track buffer để nhớ người lâu hơn khi bị che khuất
        if not self._buffer_patched and hasattr(self.model, "predictor") and self.model.predictor:
            if hasattr(self.model.predictor, "trackers"):
                for t in self.model.predictor.trackers:
                    if hasattr(t, "track_buffer"):
                        t.track_buffer = 150
                    if hasattr(t, "max_time_lost"):
                        t.max_time_lost = 150
                self._buffer_patched = True
                print("\n[AI-09 Tracking] Track Buffer = 150 frames\n")

        tracked_persons = []

        if results[0].boxes is not None and results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
            track_ids = results[0].boxes.id.cpu().numpy().astype(int)
            confs = results[0].boxes.conf.cpu().numpy()

            for box, track_id, conf in zip(boxes, track_ids, confs):
                x1, y1, x2, y2 = box
                tracked_persons.append({
                    "track_id": int(track_id),
                    "bbox": [int(x1), int(y1), int(x2), int(y2)],
                    "confidence": round(float(conf), 2),
                    "frame_index": frame_index,
                    "img_path": img_path,
                })

        return tracked_persons

# ==========================================
# KHỞI TẠO SINGLETON SERVICE
# ==========================================

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
YOLO_MODEL_PATH = os.path.join(CURRENT_DIR, "models", "yolov8m.pt")

tracker_service = TrackingService(
    model_path=YOLO_MODEL_PATH,
    tracker_type="botsort.yaml",
)