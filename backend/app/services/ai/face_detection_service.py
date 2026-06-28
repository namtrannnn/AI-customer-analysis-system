import cv2
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Tọa độ 5 điểm mốc chuẩn (Landmarks) cho khuôn mặt kích thước 112x112
REFERENCE_FACIAL_POINTS = np.array([
    [38.2946, 51.6963],  # Mắt trái
    [73.5318, 51.5014],  # Mắt phải
    [56.0252, 71.7366],  # Chóp mũi
    [41.5493, 92.3655],  # Mép miệng trái
    [70.7299, 92.2041],  # Mép miệng phải
], dtype=np.float32)


def align_face_global(
    image: np.ndarray,
    face_data: np.ndarray,
    offset_x: int,
    offset_y: int,
) -> Optional[np.ndarray]:
    """
    Căn chỉnh khuôn mặt trên hệ tọa độ toàn cục.
    offset_x, offset_y là tọa độ x1, y1 của crop đang đưa vào YuNet.
    """
    local_landmarks = face_data[4:14].reshape((5, 2)).astype(np.float32)
    global_landmarks = local_landmarks + np.array([offset_x, offset_y], dtype=np.float32)

    M, _ = cv2.estimateAffinePartial2D(
        global_landmarks,
        REFERENCE_FACIAL_POINTS,
        method=cv2.LMEDS,
    )

    if M is None:
        return None

    return cv2.warpAffine(image, M, (112, 112), borderValue=(0, 0, 0))


def is_occluded_by_hat_or_shadow(face_crop: np.ndarray) -> bool:
    """
    Bộ lọc tùy chọn để phát hiện nón/bóng đổ vùng mắt.
    Hiện chưa bật mặc định vì có thể loại nhầm trong camera ánh sáng yếu.
    """
    if face_crop is None or face_crop.size == 0:
        return True

    gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)

    eye_zone = gray[40:60, 20:92]
    cheek_zone = gray[75:95, 20:92]

    mean_eye = float(np.mean(eye_zone))
    mean_cheek = float(np.mean(cheek_zone))

    if mean_eye < mean_cheek * 0.65:
        return True

    forehead_zone = gray[0:38, 15:97]
    laplacian_var = cv2.Laplacian(forehead_zone, cv2.CV_64F).var()

    if laplacian_var > 280.0:
        return True

    return False


@dataclass
class PersonDetectionInput:
    frame_index: int
    image_path: str
    person_index: int
    bbox: List[float]  # xyxy trên frame gốc
    confidence: Optional[float] = None


@dataclass
class DetectedFace:
    frame_index: int
    image_path: str
    person_index: Optional[int]
    face_image_path: str
    bbox: List[float]  # xyxy trên frame gốc
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
    Face detector an toàn cho case 2 người đứng sát nhau theo chiều trên/dưới.

    Vấn đề cũ:
    - Crop person được padding top/bottom.
    - Khi 2 người đứng sát nhau, crop của người dưới có thể chứa mặt người phía trên.
    - Code cũ chọn face có confidence cao nhất trong crop => dễ cắt nhầm mặt.

    Cách sửa:
    - Giữ lại original person bbox trước khi padding.
    - Mỗi face YuNet phát hiện được sẽ được quy đổi về tọa độ global.
    - Chỉ nhận face nếu tâm mặt, landmark và phần lớn bbox mặt nằm trong original person bbox.
    - Chọn best face bằng score có ràng buộc vị trí đầu/người, không chọn thuần confidence.
    """

    def __init__(
        self,
        yunet_model_path: Optional[str] = None,
        yunet_score_threshold: float = 0.65,
        yunet_nms_threshold: float = 0.3,

        # Padding vẫn cần để lấy đủ đầu/mặt, nhưng sẽ không dùng vùng padding để "nhận chủ mặt".
        person_pad_x_ratio: float = 0.15,
        person_pad_top_ratio: float = 0.18,
        person_pad_bottom_ratio: float = 0.05,

        # Gate chống cắt nhầm mặt người khác.
        min_face_inside_person_ratio: float = 0.80,
        min_landmark_inside_person_ratio: float = 0.60,

        # Với bbox người đứng, mặt hợp lệ thường nằm ở phần trên của bbox.
        # Cho phép hơi âm để không loại mặt sát mép trên do detector person cắt thiếu đầu.
        min_face_center_y_ratio: float = -0.04,
        max_face_center_y_ratio: float = 0.50,

        # Không cho mặt quá lệch ngang khỏi bbox người.
        min_face_center_x_ratio: float = -0.10,
        max_face_center_x_ratio: float = 1.10,

        min_face_size: int = 18,
        reject_black_ratio: float = 0.15,
        debug_reject: bool = False,
    ) -> None:
        self.yunet_score_threshold = yunet_score_threshold
        self.yunet_model_path = self._resolve_yunet_model_path(yunet_model_path)
        self.yunet_detector = self._load_yunet_detector(yunet_nms_threshold)

        self.person_pad_x_ratio = person_pad_x_ratio
        self.person_pad_top_ratio = person_pad_top_ratio
        self.person_pad_bottom_ratio = person_pad_bottom_ratio

        self.min_face_inside_person_ratio = min_face_inside_person_ratio
        self.min_landmark_inside_person_ratio = min_landmark_inside_person_ratio
        self.min_face_center_y_ratio = min_face_center_y_ratio
        self.max_face_center_y_ratio = max_face_center_y_ratio
        self.min_face_center_x_ratio = min_face_center_x_ratio
        self.max_face_center_x_ratio = max_face_center_x_ratio

        self.min_face_size = min_face_size
        self.reject_black_ratio = reject_black_ratio
        self.debug_reject = debug_reject

    def detect_faces_from_person_detections(
        self,
        person_detections: List[PersonDetectionInput],
        output_dir: str,
        image_extension: str = "jpg",
        jpeg_quality: int = 90,
        max_faces_per_person: Optional[int] = 1,
        min_quality_score: float = 0.0,
    ) -> FaceDetectionResult:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        detected_faces: List[DetectedFace] = []

        if self.yunet_detector is None:
            print("Lỗi: Không tải được mô hình YuNet ONNX.")
            return FaceDetectionResult(output_dir=str(output_path), detected_count=0, faces=[])

        image_cache: Dict[str, Any] = {}

        for person in person_detections:
            if person.image_path not in image_cache:
                image_cache[person.image_path] = cv2.imread(person.image_path)

            frame = image_cache[person.image_path]
            if frame is None:
                continue

            img_h, img_w = frame.shape[:2]

            # BBox gốc của person: dùng để xác định mặt nào thật sự thuộc person này.
            ox1, oy1, ox2, oy2 = self._clip_box_xyxy(person.bbox, img_w, img_h)
            person_w = ox2 - ox1
            person_h = oy2 - oy1
            if person_w <= 0 or person_h <= 0:
                continue

            # Crop đã padding: chỉ dùng để YuNet có thêm ngữ cảnh tìm mặt.
            px1, py1, px2, py2 = self._build_padded_person_box(
                ox1, oy1, ox2, oy2, img_w, img_h
            )

            person_crop = frame[py1:py2, px1:px2]
            if person_crop.size == 0:
                continue

            crop_h, crop_w = person_crop.shape[:2]
            self.yunet_detector.setInputSize((crop_w, crop_h))

            _, faces = self.yunet_detector.detect(person_crop)
            if faces is None or len(faces) == 0:
                continue

            faces = np.asarray(faces)
            faces = faces[np.isfinite(faces).all(axis=1)]
            if len(faces) == 0:
                continue

            accepted: List[Tuple[float, np.ndarray, Dict[str, float]]] = []

            for face in faces:
                ok, info = self._validate_face_belongs_to_person(
                    face=face,
                    crop_offset_x=px1,
                    crop_offset_y=py1,
                    original_person_box=(ox1, oy1, ox2, oy2),
                    crop_shape=(crop_h, crop_w),
                )

                if not ok:
                    if self.debug_reject:
                        print(
                            f"[FaceReject] frame={person.frame_index} "
                            f"person={person.person_index} reason={info.get('reason')} "
                            f"conf={info.get('conf', 0):.3f} "
                            f"inside={info.get('inside_ratio', 0):.2f} "
                            f"cy_rel={info.get('cy_rel', 0):.2f}"
                        )
                    continue

                conf = info["conf"]
                if conf < min_quality_score:
                    continue

                # Score chọn mặt:
                # - confidence vẫn quan trọng
                # - ưu tiên face nằm nhiều trong person bbox
                # - phạt nếu tâm mặt xa vùng đầu dự kiến
                # - phạt nếu lệch ngang khỏi tâm người
                score = self._score_face_candidate(
                    conf=conf,
                    inside_ratio=info["inside_ratio"],
                    landmark_inside_ratio=info["landmark_inside_ratio"],
                    cx_rel=info["cx_rel"],
                    cy_rel=info["cy_rel"],
                )
                accepted.append((score, face, info))

            if not accepted:
                continue

            accepted.sort(key=lambda item: item[0], reverse=True)
            selected = accepted[:1 if max_faces_per_person in (None, 1) else max_faces_per_person]

            for face_rank, (score, best_face, info) in enumerate(selected):
                fx, fy, fw, fh = map(int, best_face[:4])
                conf = float(best_face[-1])

                face_crop = align_face_global(frame, best_face, px1, py1)

                if face_crop is None:
                    # Fallback vẫn crop từ frame gốc theo global bbox, không crop từ person_crop.
                    gx1, gy1, gx2, gy2 = self._face_global_box(best_face, px1, py1, img_w, img_h)
                    fallback = frame[gy1:gy2, gx1:gx2]
                    if fallback.size == 0:
                        continue
                    face_crop = cv2.resize(fallback, (112, 112))

                if self._black_pixel_ratio(face_crop) > self.reject_black_ratio:
                    continue

                gx1, gy1, gx2, gy2 = self._face_global_box(best_face, px1, py1, img_w, img_h)

                suffix = "" if face_rank == 0 else f"_{face_rank}"
                face_filename = (
                    f"face_frame_{person.frame_index:04d}_"
                    f"person_{person.person_index}{suffix}.{image_extension}"
                )
                face_image_path = output_path / face_filename

                write_params = []
                if image_extension.lower() in {"jpg", "jpeg"}:
                    write_params = [cv2.IMWRITE_JPEG_QUALITY, int(jpeg_quality)]

                cv2.imwrite(str(face_image_path), face_crop, write_params)

                detected_faces.append(
                    DetectedFace(
                        frame_index=person.frame_index,
                        image_path=person.image_path,
                        person_index=person.person_index,
                        face_image_path=str(face_image_path),
                        bbox=[float(gx1), float(gy1), float(gx2), float(gy2)],
                        confidence=round(conf, 3),
                        quality_score=round(score, 3),
                        width=int(fw),
                        height=int(fh),
                    )
                )

        return FaceDetectionResult(
            output_dir=str(output_path),
            detected_count=len(detected_faces),
            faces=detected_faces,
        )

    def create_temp_face_dir(self) -> tempfile.TemporaryDirectory:
        return tempfile.TemporaryDirectory(prefix="faces_")

    def _build_padded_person_box(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        img_w: int,
        img_h: int,
    ) -> Tuple[int, int, int, int]:
        box_w = x2 - x1
        box_h = y2 - y1

        pad_x = int(box_w * self.person_pad_x_ratio)
        pad_top = int(box_h * self.person_pad_top_ratio)
        pad_bottom = int(box_h * self.person_pad_bottom_ratio)

        return (
            max(0, x1 - pad_x),
            max(0, y1 - pad_top),
            min(img_w, x2 + pad_x),
            min(img_h, y2 + pad_bottom),
        )

    def _validate_face_belongs_to_person(
        self,
        face: np.ndarray,
        crop_offset_x: int,
        crop_offset_y: int,
        original_person_box: Tuple[int, int, int, int],
        crop_shape: Tuple[int, int],
    ) -> Tuple[bool, Dict[str, float]]:
        crop_h, crop_w = crop_shape
        ox1, oy1, ox2, oy2 = original_person_box
        person_w = max(1, ox2 - ox1)
        person_h = max(1, oy2 - oy1)

        fx, fy, fw, fh = [float(v) for v in face[:4]]
        conf = float(face[-1])

        info: Dict[str, float] = {"conf": conf}

        if fw < self.min_face_size or fh < self.min_face_size:
            info["reason"] = "face_too_small"
            return False, info

        # YuNet bbox trong crop -> global bbox.
        gx1 = crop_offset_x + fx
        gy1 = crop_offset_y + fy
        gx2 = gx1 + fw
        gy2 = gy1 + fh

        # Không nhận face YuNet nằm quá thấp trong padded crop.
        # Rule này giữ lại logic chặn ngực/bụng nhưng nới hơn một chút.
        if fy > crop_h * 0.50:
            info["reason"] = "too_low_in_crop"
            return False, info

        cx = (gx1 + gx2) * 0.5
        cy = (gy1 + gy2) * 0.5
        cx_rel = (cx - ox1) / person_w
        cy_rel = (cy - oy1) / person_h

        info["cx_rel"] = float(cx_rel)
        info["cy_rel"] = float(cy_rel)

        if not (self.min_face_center_x_ratio <= cx_rel <= self.max_face_center_x_ratio):
            info["reason"] = "face_center_x_outside_person"
            return False, info

        if not (self.min_face_center_y_ratio <= cy_rel <= self.max_face_center_y_ratio):
            info["reason"] = "face_center_y_not_in_head_region"
            return False, info

        face_area = max(1.0, fw * fh)
        inside_area = self._intersection_area(
            (gx1, gy1, gx2, gy2),
            (ox1, oy1, ox2, oy2),
        )
        inside_ratio = inside_area / face_area
        info["inside_ratio"] = float(inside_ratio)

        if inside_ratio < self.min_face_inside_person_ratio:
            info["reason"] = "face_bbox_not_inside_person"
            return False, info

        landmarks = face[4:14].reshape((5, 2)).astype(np.float32)
        global_landmarks = landmarks + np.array([crop_offset_x, crop_offset_y], dtype=np.float32)

        landmark_inside_count = 0
        for lx, ly in global_landmarks:
            if ox1 <= lx <= ox2 and oy1 <= ly <= oy2:
                landmark_inside_count += 1

        landmark_inside_ratio = landmark_inside_count / 5.0
        info["landmark_inside_ratio"] = float(landmark_inside_ratio)

        if landmark_inside_ratio < self.min_landmark_inside_person_ratio:
            info["reason"] = "landmarks_not_inside_person"
            return False, info

        if not self._landmarks_are_reasonable(global_landmarks):
            info["reason"] = "bad_landmark_geometry"
            return False, info

        return True, info

    def _score_face_candidate(
        self,
        conf: float,
        inside_ratio: float,
        landmark_inside_ratio: float,
        cx_rel: float,
        cy_rel: float,
    ) -> float:
        # Vùng đầu dự kiến. 0.18 hợp với người đứng trong bbox toàn thân/bán thân.
        expected_cy = 0.18
        head_penalty = min(1.0, abs(cy_rel - expected_cy) / 0.35)

        # Tâm mặt thường quanh tâm ngang của bbox người, nhưng camera chéo nên phạt nhẹ.
        center_x_penalty = min(1.0, abs(cx_rel - 0.5) / 0.65)

        return (
            conf * 0.58
            + inside_ratio * 0.20
            + landmark_inside_ratio * 0.14
            + (1.0 - head_penalty) * 0.06
            + (1.0 - center_x_penalty) * 0.02
        )

    @staticmethod
    def _landmarks_are_reasonable(global_landmarks: np.ndarray) -> bool:
        left_eye, right_eye, nose, left_mouth, right_mouth = global_landmarks

        # Mắt phải nên nằm bên phải mắt trái trong ảnh thường.
        if right_eye[0] <= left_eye[0]:
            return False

        eye_y = (left_eye[1] + right_eye[1]) * 0.5
        mouth_y = (left_mouth[1] + right_mouth[1]) * 0.5

        # Mũi và miệng phải nằm dưới vùng mắt tương đối.
        if nose[1] <= eye_y - 3:
            return False
        if mouth_y <= nose[1] - 3:
            return False

        eye_dist = float(np.linalg.norm(right_eye - left_eye))
        mouth_dist = float(np.linalg.norm(right_mouth - left_mouth))

        if eye_dist < 4 or mouth_dist < 3:
            return False

        return True

    @staticmethod
    def _face_global_box(
        face: np.ndarray,
        offset_x: int,
        offset_y: int,
        img_w: int,
        img_h: int,
    ) -> Tuple[int, int, int, int]:
        fx, fy, fw, fh = [float(v) for v in face[:4]]
        gx1 = int(round(offset_x + fx))
        gy1 = int(round(offset_y + fy))
        gx2 = int(round(gx1 + fw))
        gy2 = int(round(gy1 + fh))
        return (
            max(0, min(img_w, gx1)),
            max(0, min(img_h, gy1)),
            max(0, min(img_w, gx2)),
            max(0, min(img_h, gy2)),
        )

    @staticmethod
    def _clip_box_xyxy(box: List[float], img_w: int, img_h: int) -> Tuple[int, int, int, int]:
        x1, y1, x2, y2 = [int(round(float(v))) for v in box]
        x1 = max(0, min(img_w, x1))
        y1 = max(0, min(img_h, y1))
        x2 = max(0, min(img_w, x2))
        y2 = max(0, min(img_h, y2))
        if x2 < x1:
            x1, x2 = x2, x1
        if y2 < y1:
            y1, y2 = y2, y1
        return x1, y1, x2, y2

    @staticmethod
    def _intersection_area(
        a: Tuple[float, float, float, float],
        b: Tuple[float, float, float, float],
    ) -> float:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)
        return max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)

    @staticmethod
    def _black_pixel_ratio(face_crop: np.ndarray) -> float:
        if face_crop is None or face_crop.size == 0:
            return 1.0
        gray_face = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        black_pixels = int(np.sum(gray_face == 0))
        return black_pixels / float(gray_face.shape[0] * gray_face.shape[1])

    def _resolve_yunet_model_path(self, model_path: Optional[str]) -> Optional[Path]:
        if model_path:
            return Path(model_path).resolve()
        default_path = Path(__file__).resolve().parent / "models" / "face_detection_yunet_2023mar.onnx"
        return default_path if default_path.exists() else None

    def _load_yunet_detector(self, nms_threshold: float) -> Optional[Any]:
        if self.yunet_model_path is None:
            return None
        try:
            return cv2.FaceDetectorYN_create(
                model=str(self.yunet_model_path),
                config="",
                input_size=(320, 320),
                score_threshold=self.yunet_score_threshold,
                nms_threshold=nms_threshold,
                top_k=5000,
            )
        except cv2.error as e:
            print(f"Lỗi cấu hình OpenCV khi tải YuNet: {e}")
            return None

    def save_detection_visualization(
        self,
        image_path: str,
        faces: List[DetectedFace],
        output_path: str,
    ) -> None:
        image = cv2.imread(str(image_path))
        if image is None:
            return

        for face in faces:
            x1, y1, x2, y2 = [int(value) for value in face.bbox]
            label = f"Face {face.confidence:.2f}" if face.confidence else "Face"
            cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                image,
                label,
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), image)
