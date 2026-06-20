import cv2
import math
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class PersonDetectionInput:
    frame_index: int
    image_path: str
    person_index: int
    bbox: List[float]
    confidence: Optional[float] = None


@dataclass(frozen=True)
class FaceCandidate:
    bbox: Tuple[int, int, int, int]
    confidence: Optional[float]
    detector: str


@dataclass
class DetectedFace:
    frame_index: int
    image_path: str
    person_index: Optional[int]
    face_image_path: str
    bbox: List[float]
    confidence: Optional[float]
    quality_score: float
    width: int
    height: int


@dataclass
class FaceDetectionResult:
    output_dir: str
    detected_count: int
    faces: List[DetectedFace]


class FaceDetectionService:
    """
    AI-03 Face Detection Service

    Workflow:
    - Nhận image_path và bbox người từ AI-02.
    - Tìm kiếm khuôn mặt trong vùng quan tâm thay vì toàn bộ ảnh.
    - Ưu tiên sử dụng YuNet khi mô hình ONNX có sẵn cục bộ.
    - Fallback sang Haar cascades khi YuNet không khả dụng hoặc bỏ lỡ khuôn mặt.
    """

    def __init__(
        self,
        scale_factor: float = 1.1,
        min_neighbors: int = 5,
        min_face_size: Tuple[int, int] = (40, 40),
        yunet_model_path: Optional[str] = None,
        yunet_score_threshold: float = 0.8,
        yunet_nms_threshold: float = 0.3,
        yunet_top_k: int = 5000,
        yunet_min_input_size: int = 320,
        yunet_max_input_size: int = 960,
        yunet_max_upscale_factor: float = 3.0,
    ):
        if scale_factor <= 1.0:
            raise ValueError("scale_factor must be greater than 1.0")

        if min_neighbors < 0:
            raise ValueError("min_neighbors must be greater than or equal to 0")

        if len(min_face_size) != 2 or min_face_size[0] <= 0 or min_face_size[1] <= 0:
            raise ValueError("min_face_size must contain two positive integers")

        self.scale_factor = scale_factor
        self.min_neighbors = min_neighbors
        self.min_face_size = min_face_size
        self.yunet_score_threshold = yunet_score_threshold
        self.yunet_nms_threshold = yunet_nms_threshold
        self.yunet_top_k = yunet_top_k
        self.yunet_min_input_size = yunet_min_input_size
        self.yunet_max_input_size = yunet_max_input_size
        self.yunet_max_upscale_factor = yunet_max_upscale_factor
        self.haar_clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

        self.frontal_face_cascade = self._load_cascade("haarcascade_frontalface_default.xml")
        self.yunet_model_path = self._resolve_yunet_model_path(yunet_model_path)
        self.yunet_detector = self._load_yunet_detector()

    def detect_faces_from_person_detections(
        self,
        person_detections: List[PersonDetectionInput | dict],
        output_dir: str,
        image_extension: str = "jpg",
        jpeg_quality: int = 90,
        max_faces_per_person: Optional[int] = 1,
    ) -> FaceDetectionResult:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        self._validate_face_limits(max_faces_per_person=max_faces_per_person)
        self._validate_image_options(
            image_extension=image_extension,
            jpeg_quality=jpeg_quality,
        )

        if max_faces_per_person == 0:
            return FaceDetectionResult(
                output_dir=str(output_path),
                detected_count=0,
                faces=[],
            )

        normalized_person_detections = self._normalize_person_detection_inputs(
            person_detections
        )

        detected_faces: List[DetectedFace] = []
        image_cache: Dict[str, Optional[object]] = {}
        used_faces_by_image: Dict[str, List[Tuple[int, int, int, int]]] = {}

        for person_detection in normalized_person_detections:
            image_path = Path(person_detection.image_path)
            cache_key = str(image_path)

            if cache_key not in image_cache:
                if not image_path.exists():
                    image_cache[cache_key] = None
                else:
                    image_cache[cache_key] = cv2.imread(str(image_path))

            image = image_cache[cache_key]

            if image is None:
                continue

            image_height, image_width = image.shape[:2]

            clipped_person_bbox = self._clip_xyxy_bbox(
                bbox=person_detection.bbox,
                image_width=image_width,
                image_height=image_height,
            )

            if clipped_person_bbox is None:
                continue

            face_search_bbox = self._build_face_search_bbox(
                person_bbox=clipped_person_bbox,
                image_width=image_width,
                image_height=image_height,
            )

            if face_search_bbox is None:
                continue

            sx1, sy1, sx2, sy2 = face_search_bbox
            search_crop = image[sy1:sy2, sx1:sx2]

            if search_crop.size == 0:
                continue

            face_candidates = self._detect_faces_in_image(search_crop)

            if not face_candidates:
                continue

            global_candidates = self._to_global_candidates(
                face_candidates=face_candidates,
                offset_x=sx1,
                offset_y=sy1,
            )

            global_candidates = self._filter_candidates_for_person(
                face_candidates=global_candidates,
                person_bbox=clipped_person_bbox,
            )

            if not global_candidates:
                continue

            global_candidates = self._sort_face_candidates_by_quality(
                face_candidates=global_candidates,
                image_width=image_width,
                image_height=image_height,
                person_bbox=clipped_person_bbox,
            )

            used_faces = used_faces_by_image.setdefault(cache_key, [])
            selected_candidates: List[FaceCandidate] = []

            for candidate in global_candidates:
                if self._overlaps_with_used_faces(candidate.bbox, used_faces):
                    continue

                selected_candidates.append(candidate)
                used_faces.append(candidate.bbox)

                if max_faces_per_person is not None and len(selected_candidates) >= max_faces_per_person:
                    break

            for face_order, candidate in enumerate(selected_candidates):
                global_x1, global_y1, global_x2, global_y2 = candidate.bbox

                face_crop = image[global_y1:global_y2, global_x1:global_x2]

                if face_crop.size == 0:
                    continue

                face_width = global_x2 - global_x1
                face_height = global_y2 - global_y1

                quality_score = self._calculate_quality_score(
                    face_width=face_width,
                    face_height=face_height,
                    image_width=image_width,
                    image_height=image_height,
                    face_crop=face_crop,
                )

                face_filename = (
                    f"face_frame_{person_detection.frame_index:06d}_"
                    f"person_{person_detection.person_index}_"
                    f"{face_order}.{image_extension}"
                )

                face_image_path = output_path / face_filename

                self._save_face_crop(
                    image_path=face_image_path,
                    face_crop=face_crop,
                    image_extension=image_extension,
                    jpeg_quality=jpeg_quality,
                )

                detected_faces.append(
                    DetectedFace(
                        frame_index=person_detection.frame_index,
                        image_path=str(image_path),
                        person_index=person_detection.person_index,
                        face_image_path=str(face_image_path),
                        bbox=[
                            float(global_x1),
                            float(global_y1),
                            float(global_x2),
                            float(global_y2),
                        ],
                        confidence=(
                            round(candidate.confidence, 3)
                            if candidate.confidence is not None
                            else None
                        ),
                        quality_score=round(quality_score, 3),
                        width=int(face_width),
                        height=int(face_height),
                    )
                )

        return FaceDetectionResult(
            output_dir=str(output_path),
            detected_count=len(detected_faces),
            faces=detected_faces,
        )

    def detect_faces_in_frame(
        self,
        image_path: str,
        output_dir: str,
        frame_index: int = 0,
        image_extension: str = "jpg",
        jpeg_quality: int = 90,
        max_faces: Optional[int] = None,
    ) -> FaceDetectionResult:
        """
        Phát hiện khuôn mặt trong một khung hình.
        """

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        self._validate_face_limits(max_faces=max_faces)
        self._validate_image_options(
            image_extension=image_extension,
            jpeg_quality=jpeg_quality,
        )

        if max_faces == 0:
            return FaceDetectionResult(
                output_dir=str(output_path),
                detected_count=0,
                faces=[],
            )

        frame_path = Path(image_path)

        if not frame_path.exists():
            raise FileNotFoundError(f"Không tìm thấy ảnh: {image_path}")

        image = cv2.imread(str(frame_path))

        if image is None:
            raise ValueError(f"Không thể đọc tệp ảnh: {image_path}")

        image_height, image_width = image.shape[:2]
        face_candidates = self._detect_faces_in_image(image)

        face_candidates = self._sort_face_candidates_by_quality(
            face_candidates=face_candidates,
            image_width=image_width,
            image_height=image_height,
            person_bbox=None,
        )

        if max_faces is not None:
            face_candidates = face_candidates[:max_faces]

        detected_faces: List[DetectedFace] = []

        for face_order, candidate in enumerate(face_candidates):
            x1, y1, x2, y2 = candidate.bbox

            face_crop = image[y1:y2, x1:x2]

            if face_crop.size == 0:
                continue

            face_width = x2 - x1
            face_height = y2 - y1

            quality_score = self._calculate_quality_score(
                face_width=face_width,
                face_height=face_height,
                image_width=image_width,
                image_height=image_height,
                face_crop=face_crop,
            )

            face_filename = (
                f"face_frame_{frame_index:06d}_"
                f"{face_order}.{image_extension}"
            )

            face_image_path = output_path / face_filename

            self._save_face_crop(
                image_path=face_image_path,
                face_crop=face_crop,
                image_extension=image_extension,
                jpeg_quality=jpeg_quality,
            )

            detected_faces.append(
                DetectedFace(
                    frame_index=frame_index,
                    image_path=str(frame_path),
                    person_index=None,
                    face_image_path=str(face_image_path),
                    bbox=[
                        float(x1),
                        float(y1),
                        float(x2),
                        float(y2),
                    ],
                    confidence=(
                        round(candidate.confidence, 3)
                        if candidate.confidence is not None
                        else None
                    ),
                    quality_score=round(quality_score, 3),
                    width=int(face_width),
                    height=int(face_height),
                )
            )

        return FaceDetectionResult(
            output_dir=str(output_path),
            detected_count=len(detected_faces),
            faces=detected_faces,
        )

    def create_temp_face_dir(self) -> tempfile.TemporaryDirectory:
        return tempfile.TemporaryDirectory(prefix="faces_")

    def _detect_faces_in_image(self, image) -> List[FaceCandidate]:
        yunet_candidates = self._detect_faces_with_yunet(image)

        if self.yunet_detector is not None and yunet_candidates:
            return yunet_candidates

        return self._detect_faces_with_haar(image)

    def _normalize_person_detection_inputs(
        self,
        person_detections: List[PersonDetectionInput | dict],
    ) -> List[PersonDetectionInput]:
        normalized_inputs: List[PersonDetectionInput] = []

        for detection in person_detections:
            if isinstance(detection, PersonDetectionInput):
                normalized_inputs.append(detection)
                continue

            if not isinstance(detection, dict):
                continue

            image_path = detection.get("image_path") or detection.get("img_path") or ""
            bbox = detection.get("bbox")

            if not image_path or not bbox:
                continue

            normalized_inputs.append(
                PersonDetectionInput(
                    frame_index=int(detection.get("frame_index", 0)),
                    image_path=str(image_path),
                    person_index=int(detection.get("person_index", 0)),
                    bbox=list(bbox),
                    confidence=(
                        float(detection["confidence"])
                        if detection.get("confidence") is not None
                        else None
                    ),
                )
            )

        return normalized_inputs

    def _detect_faces_with_yunet(self, image) -> List[FaceCandidate]:
        if self.yunet_detector is None:
            return []

        image_height, image_width = image.shape[:2]

        if image_width < 40 or image_height < 40:
            return []

        scale_candidates = [1.0]
        min_side = min(image_width, image_height)

        if min_side < self.yunet_min_input_size:
            upscale_factor = min(
                self.yunet_min_input_size / max(min_side, 1),
                self.yunet_max_upscale_factor,
            )
            if upscale_factor > 1.05:
                scale_candidates.append(upscale_factor)

        if min_side < self.yunet_min_input_size * 0.75:
            stronger_upscale_factor = min(
                self.yunet_max_input_size / max(min_side, 1),
                self.yunet_max_upscale_factor,
            )
            if stronger_upscale_factor > scale_candidates[-1] + 0.1:
                scale_candidates.append(stronger_upscale_factor)

        candidates: List[FaceCandidate] = []

        for scale_factor in scale_candidates:
            candidates.extend(
                self._run_yunet_detection(
                    image=image,
                    scale_factor=scale_factor,
                )
            )

        return self._merge_overlapping_candidates(candidates, iou_threshold=0.25)

    def _run_yunet_detection(
        self,
        image,
        scale_factor: float,
    ) -> List[FaceCandidate]:
        image_height, image_width = image.shape[:2]

        if scale_factor > 1.0:
            resized_image = cv2.resize(
                image,
                dsize=None,
                fx=scale_factor,
                fy=scale_factor,
                interpolation=cv2.INTER_CUBIC,
            )
        else:
            resized_image = image

        try:
            self.yunet_detector.setInputSize(
                (resized_image.shape[1], resized_image.shape[0])
            )
            _, faces = self.yunet_detector.detect(resized_image)
        except cv2.error:
            return []

        if faces is None:
            return []

        candidates: List[FaceCandidate] = []

        for face in faces:
            x, y, width, height = face[:4]
            confidence = float(face[-1])
            bbox = self._clip_xyxy_bbox(
                bbox=[
                    float(x / scale_factor),
                    float(y / scale_factor),
                    float((x + width) / scale_factor),
                    float((y + height) / scale_factor),
                ],
                image_width=image_width,
                image_height=image_height,
            )

            if bbox is None:
                continue

            candidates.append(
                FaceCandidate(
                    bbox=bbox,
                    confidence=confidence,
                    detector=(
                        "yunet_upscaled"
                        if scale_factor > 1.0
                        else "yunet"
                    ),
                )
            )

        return candidates

    def _detect_faces_with_haar(self, image) -> List[FaceCandidate]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        enhanced = self.haar_clahe.apply(gray)
        image_height, image_width = enhanced.shape[:2]

        raw_candidates: List[FaceCandidate] = []

        frontal_faces = self.frontal_face_cascade.detectMultiScale(
            enhanced,
            scaleFactor=self.scale_factor,
            minNeighbors=self.min_neighbors,
            minSize=self.min_face_size,
        )

        for x, y, width, height in frontal_faces:
            bbox = self._clip_xyxy_bbox(
                bbox=[float(x), float(y), float(x + width), float(y + height)],
                image_width=image_width,
                image_height=image_height,
            )

            if bbox is None:
                continue

            raw_candidates.append(
                FaceCandidate(
                    bbox=bbox,
                    confidence=0.55,
                    detector="haar_frontal",
                )
            )

        return self._merge_overlapping_candidates(raw_candidates)

    def _to_global_candidates(
        self,
        face_candidates: List[FaceCandidate],
        offset_x: int,
        offset_y: int,
    ) -> List[FaceCandidate]:
        results: List[FaceCandidate] = []

        for candidate in face_candidates:
            x1, y1, x2, y2 = candidate.bbox

            results.append(
                FaceCandidate(
                    bbox=(
                        offset_x + x1,
                        offset_y + y1,
                        offset_x + x2,
                        offset_y + y2,
                    ),
                    confidence=candidate.confidence,
                    detector=candidate.detector,
                )
            )

        return results

    def _build_face_search_bbox(
        self,
        person_bbox: Tuple[int, int, int, int],
        image_width: int,
        image_height: int,
    ) -> Optional[Tuple[int, int, int, int]]:
        px1, py1, px2, py2 = person_bbox
        person_width = px2 - px1
        person_height = py2 - py1

        if person_width <= 0 or person_height <= 0:
            return None

        return self._clip_xyxy_bbox(
            bbox=[
                px1 - person_width * 0.18,
                py1 - person_height * 0.16,
                px2 + person_width * 0.18,
                py1 + person_height * 0.62,
            ],
            image_width=image_width,
            image_height=image_height,
        )

    def _filter_candidates_for_person(
        self,
        face_candidates: List[FaceCandidate],
        person_bbox: Tuple[int, int, int, int],
    ) -> List[FaceCandidate]:
        px1, py1, px2, py2 = person_bbox
        person_width = max(px2 - px1, 1)
        person_height = max(py2 - py1, 1)
        filtered_candidates: List[FaceCandidate] = []

        for candidate in face_candidates:
            x1, y1, x2, y2 = candidate.bbox
            face_width = x2 - x1
            face_height = y2 - y1

            if face_width <= 0 or face_height <= 0:
                continue

            face_center_x = x1 + face_width / 2
            face_center_y = y1 + face_height / 2

            if not (px1 - person_width * 0.10 <= face_center_x <= px2 + person_width * 0.10):
                continue

            if not (py1 - person_height * 0.15 <= face_center_y <= py1 + person_height * 0.66):
                continue

            relative_top = (y1 - py1) / person_height
            relative_bottom = (y2 - py1) / person_height
            relative_height = face_height / person_height
            aspect_ratio = face_width / max(face_height, 1)

            if relative_top > 0.62:
                continue

            if relative_bottom > 0.82:
                continue

            if relative_height < 0.05 or relative_height > 0.45:
                continue

            if aspect_ratio < 0.5 or aspect_ratio > 1.7:
                continue

            filtered_candidates.append(candidate)

        return filtered_candidates

    def _sort_face_candidates_by_quality(
        self,
        face_candidates: List[FaceCandidate],
        image_width: int,
        image_height: int,
        person_bbox: Optional[Tuple[int, int, int, int]],
    ) -> List[FaceCandidate]:
        def score(candidate: FaceCandidate) -> float:
            x1, y1, x2, y2 = candidate.bbox
            face_width = x2 - x1
            face_height = y2 - y1
            face_area = face_width * face_height
            confidence_score = candidate.confidence if candidate.confidence is not None else 0.4

            if person_bbox is not None:
                px1, py1, px2, py2 = person_bbox
                person_width = max(px2 - px1, 1)
                person_height = max(py2 - py1, 1)
                person_area = max(person_width * person_height, 1)

                face_center_x = x1 + face_width / 2
                face_center_y = y1 + face_height / 2

                target_x = px1 + person_width / 2
                target_y = py1 + person_height * 0.22

                distance = math.sqrt(
                    (face_center_x - target_x) ** 2
                    + (face_center_y - target_y) ** 2
                )

                position_score = 1 / (1 + distance / max(person_width, person_height, 1))
                size_score = min((face_height / person_height) / 0.25, 1.0)
                area_score = min(face_area / person_area * 12, 1.0)

                return confidence_score * 3.0 + position_score * 2.0 + size_score + area_score

            image_center_x = image_width / 2
            image_center_y = image_height / 2
            face_center_x = x1 + face_width / 2
            face_center_y = y1 + face_height / 2

            distance = math.sqrt(
                (face_center_x - image_center_x) ** 2
                + (face_center_y - image_center_y) ** 2
            )
            center_score = 1 / (1 + distance)
            area_score = face_area / max(image_width * image_height, 1)

            return confidence_score * 3.0 + area_score * 20 + center_score

        return sorted(face_candidates, key=score, reverse=True)

    def _merge_overlapping_candidates(
        self,
        face_candidates: List[FaceCandidate],
        iou_threshold: float = 0.35,
    ) -> List[FaceCandidate]:
        sorted_candidates = sorted(
            face_candidates,
            key=lambda candidate: (
                candidate.confidence if candidate.confidence is not None else 0.0,
                (candidate.bbox[2] - candidate.bbox[0]) * (candidate.bbox[3] - candidate.bbox[1]),
            ),
            reverse=True,
        )

        merged_candidates: List[FaceCandidate] = []

        for candidate in sorted_candidates:
            if any(self._calculate_iou(candidate.bbox, kept.bbox) >= iou_threshold for kept in merged_candidates):
                continue

            merged_candidates.append(candidate)

        return merged_candidates

    def _overlaps_with_used_faces(
        self,
        bbox: Tuple[int, int, int, int],
        used_faces: List[Tuple[int, int, int, int]],
        iou_threshold: float = 0.5,
    ) -> bool:
        for used_bbox in used_faces:
            if self._calculate_iou(bbox, used_bbox) >= iou_threshold:
                return True

        return False

    def _calculate_quality_score(
        self,
        face_width: int,
        face_height: int,
        image_width: int,
        image_height: int,
        face_crop,
    ) -> float:
        image_area = max(image_width * image_height, 1)
        face_area = face_width * face_height

        size_score = min(face_area / image_area * 20, 1.0)

        gray_face = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        blur_value = cv2.Laplacian(gray_face, cv2.CV_64F).var()

        blur_score = min(blur_value / 500, 1.0)

        quality_score = size_score * 0.6 + blur_score * 0.4

        return max(0.0, min(quality_score, 1.0))

    def _clip_xyxy_bbox(
        self,
        bbox: List[float],
        image_width: int,
        image_height: int,
    ) -> Optional[Tuple[int, int, int, int]]:
        if len(bbox) != 4:
            return None

        x1, y1, x2, y2 = bbox

        x1 = max(0, int(round(x1)))
        y1 = max(0, int(round(y1)))
        x2 = min(image_width, int(round(x2)))
        y2 = min(image_height, int(round(y2)))

        if x2 <= x1 or y2 <= y1:
            return None

        return x1, y1, x2, y2

    def _calculate_iou(
        self,
        first_bbox: Tuple[int, int, int, int],
        second_bbox: Tuple[int, int, int, int],
    ) -> float:
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

    def _load_cascade(self, cascade_name: str) -> cv2.CascadeClassifier:
        cascade_path = Path(cv2.data.haarcascades) / cascade_name

        if not cascade_path.exists():
            raise FileNotFoundError(f"Khuôn mặt không tìm thấy: {cascade_path}")

        cascade = cv2.CascadeClassifier(str(cascade_path))

        if cascade.empty():
            raise ValueError(f"Không thể tải bộ phát hiện khuôn mặt: {cascade_path}")

        return cascade

    def _resolve_yunet_model_path(self, yunet_model_path: Optional[str]) -> Optional[Path]:
        candidate_paths: List[Path] = []

        if yunet_model_path:
            candidate_paths.append(Path(yunet_model_path))
        else:
            candidate_paths.append(
                Path(__file__).resolve().parent / "models" / "face_detection_yunet_2023mar.onnx"
            )

        for candidate_path in candidate_paths:
            resolved_path = candidate_path.expanduser().resolve()

            if resolved_path.exists() and resolved_path.is_file():
                return resolved_path

        return None

    def _load_yunet_detector(self):
        if self.yunet_model_path is None:
            return None

        if not hasattr(cv2, "FaceDetectorYN_create"):
            return None

        try:
            return cv2.FaceDetectorYN_create(
                str(self.yunet_model_path),
                "",
                (320, 320),
                self.yunet_score_threshold,
                self.yunet_nms_threshold,
                self.yunet_top_k,
            )
        except cv2.error:
            return None

    def _validate_image_options(
        self,
        image_extension: str,
        jpeg_quality: int,
    ) -> None:
        normalized_extension = image_extension.lower().replace(".", "")

        if normalized_extension not in ["jpg", "jpeg", "png"]:
            raise ValueError("Không hỗ trợ định dạng ảnh. Sử dụng jpg, jpeg, hoặc png.")

        if normalized_extension in ["jpg", "jpeg"] and not 1 <= jpeg_quality <= 100:
            raise ValueError("jpeg_quality phải là một giá trị từ 1 đến 100")

    def _validate_face_limits(
        self,
        max_faces_per_person: Optional[int] = None,
        max_faces: Optional[int] = None,
    ) -> None:
        if max_faces_per_person is not None and max_faces_per_person < 0:
            raise ValueError("max_faces_per_person phải là một giá trị lớn hơn hoặc bằng 0")

        if max_faces is not None and max_faces < 0:
            raise ValueError("max_faces phải là một giá trị lớn hơn hoặc bằng 0")

    def _save_face_crop(
        self,
        image_path: Path,
        face_crop,
        image_extension: str,
        jpeg_quality: int,
    ) -> None:
        image_extension = image_extension.lower().replace(".", "")

        if image_extension in ["jpg", "jpeg"]:
            saved = cv2.imwrite(
                str(image_path),
                face_crop,
                [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality],
            )
        elif image_extension == "png":
            saved = cv2.imwrite(str(image_path), face_crop)
        else:
            raise ValueError("Không hỗ trợ định dạng ảnh. Sử dụng jpg, jpeg, hoặc png.")

        if not saved:
            raise ValueError(f"Lưu ảnh khuôn mặt thất bại: {image_path}")
