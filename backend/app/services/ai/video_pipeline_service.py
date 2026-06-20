import cv2
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from app.services.ai.face_detection_service import FaceDetectionService
from app.services.ai.frame_extractor_service import FrameExtractorService
from app.services.ai.person_detection_service import person_detector


@dataclass
class DetectedCustomerSummary:
    anonymous_id: str
    customer_type: str
    confidence: float
    observation_count: int
    face_detected: bool


@dataclass
class VideoPipelineResult:
    total_frames: int
    sampled_frames: int
    raw_person_detections: int
    raw_face_detections: int
    detected_customers: List[DetectedCustomerSummary]


class VideoProcessingPipelineService:
    """
    AI-06 Video Processing Pipeline

    Pipeline hiện tại nối các bước:
    - AI-01: trích frame từ video tạm.
    - AI-02: phát hiện người trên từng frame.
    - AI-03: tìm khuôn mặt trong vùng người đã phát hiện.

    Lưu ý:
    - Chưa tích hợp embedding/matching nên tạm thời gán tất cả là `new`.
    - Việc gom người duy nhất đang dùng heuristic theo bbox giữa các frame đã sample.
    """

    def __init__(
        self,
        frame_extractor: Optional[FrameExtractorService] = None,
        face_detector: Optional[FaceDetectionService] = None,
        person_match_threshold: float = 0.45,
        max_frame_gap: int = 2,
    ):
        self.frame_extractor = frame_extractor or FrameExtractorService()
        self.face_detector = face_detector or FaceDetectionService()
        self.person_detector = person_detector
        self.person_match_threshold = person_match_threshold
        self.max_frame_gap = max_frame_gap

    def process_video(
        self,
        video_path: str,
        frame_interval: Optional[int] = None,
        target_fps: Optional[float] = 1.0,
        max_frames: Optional[int] = None,
        max_faces_per_person: Optional[int] = 1,
    ) -> VideoPipelineResult:
        with (
            self.frame_extractor.create_temp_frame_dir() as frame_dir,
            self.face_detector.create_temp_face_dir() as face_dir,
        ):
            frame_result = self.frame_extractor.extract_frames(
                video_path=video_path,
                output_dir=frame_dir,
                frame_interval=frame_interval,
                target_fps=target_fps,
                max_frames=max_frames,
            )

            all_person_detections: List[dict] = []
            frame_timestamps: Dict[int, float] = {
                frame.frame_index: frame.timestamp_seconds
                for frame in frame_result.frames
            }

            for frame in frame_result.frames:
                image = cv2.imread(frame.image_path)

                if image is None:
                    continue

                person_detections = self.person_detector.detect_persons(
                    frame=image,
                    frame_index=frame.frame_index,
                    image_path=frame.image_path,
                )
                all_person_detections.extend(person_detections)

            face_result = self.face_detector.detect_faces_from_person_detections(
                person_detections=all_person_detections,
                output_dir=face_dir,
                max_faces_per_person=max_faces_per_person,
            )

            face_lookup = {
                (face.frame_index, face.person_index): face
                for face in face_result.faces
                if face.person_index is not None
            }

            detected_customers = self._aggregate_detected_customers(
                person_detections=all_person_detections,
                face_lookup=face_lookup,
                frame_timestamps=frame_timestamps,
            )

            return VideoPipelineResult(
                total_frames=frame_result.total_frames,
                sampled_frames=frame_result.extracted_count,
                raw_person_detections=len(all_person_detections),
                raw_face_detections=face_result.detected_count,
                detected_customers=detected_customers,
            )

    def _aggregate_detected_customers(
        self,
        person_detections: List[dict],
        face_lookup: Dict[Tuple[int, int], object],
        frame_timestamps: Dict[int, float],
    ) -> List[DetectedCustomerSummary]:
        clusters: List[dict] = []

        sorted_detections = sorted(
            person_detections,
            key=lambda detection: (
                int(detection.get("frame_index", 0)),
                int(detection.get("person_index", 0)),
            ),
        )

        for detection in sorted_detections:
            frame_index = int(detection.get("frame_index", 0))
            person_index = int(detection.get("person_index", 0))
            bbox = detection.get("bbox")

            if not bbox or len(bbox) != 4:
                continue

            best_match_index = self._find_matching_cluster(
                bbox=bbox,
                frame_index=frame_index,
                clusters=clusters,
            )

            if best_match_index is None:
                clusters.append(
                    {
                        "confidence_sum": float(detection.get("confidence", 0.0)),
                        "observation_count": 1,
                        "last_bbox": bbox,
                        "last_frame_index": frame_index,
                        "last_seen_at": frame_timestamps.get(frame_index, 0.0),
                        "face_detected": (frame_index, person_index) in face_lookup,
                    }
                )
                continue

            cluster = clusters[best_match_index]
            cluster["confidence_sum"] += float(detection.get("confidence", 0.0))
            cluster["observation_count"] += 1
            cluster["last_bbox"] = bbox
            cluster["last_frame_index"] = frame_index
            cluster["last_seen_at"] = frame_timestamps.get(frame_index, 0.0)
            cluster["face_detected"] = (
                cluster["face_detected"]
                or (frame_index, person_index) in face_lookup
            )

        detected_customers: List[DetectedCustomerSummary] = []

        for index, cluster in enumerate(clusters, start=1):
            average_confidence = (
                cluster["confidence_sum"] / cluster["observation_count"]
                if cluster["observation_count"] > 0
                else 0.0
            )

            detected_customers.append(
                DetectedCustomerSummary(
                    anonymous_id=f"ANO_{index:03d}",
                    customer_type="new",
                    confidence=round(average_confidence, 3),
                    observation_count=cluster["observation_count"],
                    face_detected=bool(cluster["face_detected"]),
                )
            )

        return detected_customers

    def _find_matching_cluster(
        self,
        bbox: List[float],
        frame_index: int,
        clusters: List[dict],
    ) -> Optional[int]:
        best_match_index: Optional[int] = None
        best_score = 0.0

        for index, cluster in enumerate(clusters):
            previous_frame_index = int(cluster["last_frame_index"])
            frame_gap = frame_index - previous_frame_index

            if frame_gap < 0 or frame_gap > self.max_frame_gap:
                continue

            score = self._calculate_match_score(
                current_bbox=bbox,
                previous_bbox=cluster["last_bbox"],
                frame_gap=frame_gap,
            )

            if score >= self.person_match_threshold and score > best_score:
                best_score = score
                best_match_index = index

        return best_match_index

    def _calculate_match_score(
        self,
        current_bbox: List[float],
        previous_bbox: List[float],
        frame_gap: int,
    ) -> float:
        iou_score = self._calculate_iou(current_bbox, previous_bbox)
        center_distance_score = 1.0 - min(
            self._calculate_center_distance_ratio(current_bbox, previous_bbox),
            1.0,
        )
        size_similarity_score = self._calculate_size_similarity(
            current_bbox,
            previous_bbox,
        )
        frame_gap_penalty = max(0.0, 1.0 - frame_gap * 0.15)

        return (
            iou_score * 0.5
            + center_distance_score * 0.3
            + size_similarity_score * 0.2
        ) * frame_gap_penalty

    def _calculate_iou(self, first_bbox: List[float], second_bbox: List[float]) -> float:
        ax1, ay1, ax2, ay2 = first_bbox
        bx1, by1, bx2, by2 = second_bbox

        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)

        if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
            return 0.0

        intersection = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
        first_area = max((ax2 - ax1) * (ay2 - ay1), 1.0)
        second_area = max((bx2 - bx1) * (by2 - by1), 1.0)

        return intersection / max(first_area + second_area - intersection, 1.0)

    def _calculate_center_distance_ratio(
        self,
        first_bbox: List[float],
        second_bbox: List[float],
    ) -> float:
        first_center_x = (first_bbox[0] + first_bbox[2]) / 2
        first_center_y = (first_bbox[1] + first_bbox[3]) / 2
        second_center_x = (second_bbox[0] + second_bbox[2]) / 2
        second_center_y = (second_bbox[1] + second_bbox[3]) / 2

        center_distance = (
            (first_center_x - second_center_x) ** 2
            + (first_center_y - second_center_y) ** 2
        ) ** 0.5

        first_width = max(first_bbox[2] - first_bbox[0], 1.0)
        first_height = max(first_bbox[3] - first_bbox[1], 1.0)
        second_width = max(second_bbox[2] - second_bbox[0], 1.0)
        second_height = max(second_bbox[3] - second_bbox[1], 1.0)
        normalizer = max(
            (first_width + second_width) / 2,
            (first_height + second_height) / 2,
            1.0,
        )

        return center_distance / normalizer

    def _calculate_size_similarity(
        self,
        first_bbox: List[float],
        second_bbox: List[float],
    ) -> float:
        first_area = max(
            (first_bbox[2] - first_bbox[0]) * (first_bbox[3] - first_bbox[1]),
            1.0,
        )
        second_area = max(
            (second_bbox[2] - second_bbox[0]) * (second_bbox[3] - second_bbox[1]),
            1.0,
        )

        return min(first_area, second_area) / max(first_area, second_area)


video_pipeline_service = VideoProcessingPipelineService()
