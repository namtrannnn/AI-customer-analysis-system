import os
from typing import Dict, List

import numpy as np
from ultralytics import YOLO


class TrackingService:
    """
    AI-09 Multi Object Tracking Service.
    """

    def __init__(self, model_path: str = "yolov8m.pt", tracker_type: str = "bytetrack.yaml"):
        self.model = YOLO(model_path)
        self.tracker_type = tracker_type
        self._buffer_patched = False

    def reset(self) -> None:
        predictor = getattr(self.model, "predictor", None)
        trackers = getattr(predictor, "trackers", None) if predictor else None

        if trackers:
            for tracker in trackers:
                reset = getattr(tracker, "reset", None)
                if callable(reset):
                    reset()

        try:
            from ultralytics.trackers.basetrack import BaseTrack

            BaseTrack.reset_id()
        except Exception:
            pass

        self._buffer_patched = False
        print("[AI-09 Tracking] Reset tracker state for new video")

    def track_persons_in_frame(
        self,
        frame: np.ndarray,
        frame_index: int,
        img_path: str,
        conf_threshold: float = 0.4,
    ) -> List[Dict]:
        results = self.model.track(
            frame,
            classes=[0],
            conf=conf_threshold,
            tracker=self.tracker_type,
            persist=True,
            verbose=False,
        )

        self._patch_tracker_buffer()

        tracked_persons = []

        if results[0].boxes is not None and results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
            track_ids = results[0].boxes.id.cpu().numpy().astype(int)
            confs = results[0].boxes.conf.cpu().numpy()

            for box, track_id, conf in zip(boxes, track_ids, confs):
                x1, y1, x2, y2 = box
                tracked_persons.append(
                    {
                        "track_id": int(track_id),
                        "bbox": [int(x1), int(y1), int(x2), int(y2)],
                        "confidence": round(float(conf), 2),
                        "frame_index": frame_index,
                        "img_path": img_path,
                    }
                )

        return tracked_persons

    def _patch_tracker_buffer(self) -> None:
        if self._buffer_patched:
            return

        predictor = getattr(self.model, "predictor", None)
        trackers = getattr(predictor, "trackers", None) if predictor else None
        if not trackers:
            return
        
        for tracker in trackers:
            if hasattr(tracker, "track_buffer"):
                tracker.track_buffer = 150 # Tăng track buffer để nhớ người lâu hơn khi bị che khuất
            if hasattr(tracker, "max_time_lost"):
                tracker.max_time_lost = 150

        self._buffer_patched = True
        print("\n[AI-09 Tracking] Track Buffer = 150 frames\n")

# ==========================================
# KHỞI TẠO SINGLETON SERVICE
# ==========================================

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
YOLO_MODEL_PATH = os.path.join(CURRENT_DIR, "models", "yolov8m.pt")

tracker_service = TrackingService(
    model_path=YOLO_MODEL_PATH,
    tracker_type="bytetrack.yaml",
)
