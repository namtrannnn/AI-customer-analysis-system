import numpy as np
from ultralytics import YOLO


class PersonDetectionService:
    def __init__(
        self,
        model_path: str = "yolov8s.pt",
        default_imgsz: int = 1280,
        default_iou_threshold: float = 0.45,
        min_person_width: int = 40,
        min_person_height: int = 80,
        duplicate_iou_threshold: float = 0.85,
        containment_threshold: float = 0.9,
    ):
        """
        Load mô hình YOLOv8 một lần và sử dụng cho cả pipeline.
        """

        self.model = YOLO(model_path)
        self.default_imgsz = default_imgsz
        self.default_iou_threshold = default_iou_threshold
        self.min_person_width = min_person_width
        self.min_person_height = min_person_height
        self.duplicate_iou_threshold = duplicate_iou_threshold
        self.containment_threshold = containment_threshold

    def detect_persons(
        self,
        frame: np.ndarray,
        conf_threshold: float = 0.3,
        frame_index: int = 0,
        image_path: str = "",
        imgsz: int | None = None,
        iou_threshold: float | None = None,
        min_person_width: int | None = None,
        min_person_height: int | None = None,
    ) -> list[dict]:
        """
        Phát hiện người từ một Frame và trả về danh sách bbox người phát hiện sau làm sạch.
        """

        if frame is None or frame.size == 0:
            return []

        image_height, image_width = frame.shape[:2]

        results = self.model(
            frame,
            classes=[0],
            conf=conf_threshold,
            iou=self.default_iou_threshold if iou_threshold is None else iou_threshold,
            verbose=False,
            imgsz=self.default_imgsz if imgsz is None else imgsz,
        )

        detected_persons: list[dict] = []
        boxes = results[0].boxes

        if boxes is None:
            return detected_persons

        normalized_detections = []

        for box in boxes:
            # Lấy tọa độ bounding box [x_min, y_min, x_max, y_max] và ép về số thực
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(float)
            confidence = float(box.conf[0].cpu().numpy())

            clipped_bbox = self._clip_bbox(
                bbox=[x1, y1, x2, y2],
                image_width=image_width,
                image_height=image_height,
            )

            if clipped_bbox is None:
                continue

            nx1, ny1, nx2, ny2 = clipped_bbox
            width = nx2 - nx1
            height = ny2 - ny1

            effective_min_width = (
                self.min_person_width
                if min_person_width is None
                else min_person_width
            )
            effective_min_height = (
                self.min_person_height
                if min_person_height is None
                else min_person_height
            )

            if width < effective_min_width or height < effective_min_height:
                continue

            normalized_detections.append(
                {
                    "bbox": [nx1, ny1, nx2, ny2],
                    "confidence": round(confidence, 2),
                    "area": width * height,
                }
            )

        cleaned_detections = self._remove_duplicate_boxes(normalized_detections)

        cleaned_detections.sort(
            key=lambda detection: (
                detection["bbox"][1],
                detection["bbox"][0],
            )
        )

        for index, detection in enumerate(cleaned_detections, start=1):
            detected_persons.append(
                {
                    "person_index": index,
                    "bbox": detection["bbox"],
                    "confidence": detection["confidence"],
                    "frame_index": frame_index,
                    "image_path": image_path,
                    "img_path": image_path,
                }
            )

        return detected_persons

    def _clip_bbox(
        self,
        bbox: list[float],
        image_width: int,
        image_height: int,
    ) -> list[int] | None:
        if len(bbox) != 4:
            return None

        x1, y1, x2, y2 = bbox
        x1 = max(0, int(round(x1)))
        y1 = max(0, int(round(y1)))
        x2 = min(image_width, int(round(x2)))
        y2 = min(image_height, int(round(y2)))

        if x2 <= x1 or y2 <= y1:
            return None

        return [x1, y1, x2, y2]

    def _remove_duplicate_boxes(self, detections: list[dict]) -> list[dict]:
        sorted_detections = sorted(
            detections,
            key=lambda detection: (
                detection["confidence"],
                detection["area"],
            ),
            reverse=True,
        )

        kept_detections: list[dict] = []

        for detection in sorted_detections:
            bbox = detection["bbox"]

            if any(
                self._calculate_iou(bbox, kept["bbox"]) >= self.duplicate_iou_threshold
                or self._containment_ratio(bbox, kept["bbox"]) >= self.containment_threshold
                for kept in kept_detections
            ):
                continue

            kept_detections.append(detection)

        return kept_detections

    def _calculate_iou(self, first_bbox: list[int], second_bbox: list[int]) -> float:
        ax1, ay1, ax2, ay2 = first_bbox
        bx1, by1, bx2, by2 = second_bbox

        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)

        if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
            return 0.0

        intersection = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
        first_area = max((ax2 - ax1) * (ay2 - ay1), 1)
        second_area = max((bx2 - bx1) * (by2 - by1), 1)

        return intersection / max(first_area + second_area - intersection, 1)

    def _containment_ratio(self, first_bbox: list[int], second_bbox: list[int]) -> float:
        ax1, ay1, ax2, ay2 = first_bbox
        bx1, by1, bx2, by2 = second_bbox

        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)

        if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
            return 0.0

        intersection = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
        first_area = max((ax2 - ax1) * (ay2 - ay1), 1)
        second_area = max((bx2 - bx1) * (by2 - by1), 1)
        smaller_area = min(first_area, second_area)

        return intersection / smaller_area

## Khởi tạo sẵn một instance (Singleton) để import và dùng chung ở các file khác
person_detector = PersonDetectionService()
