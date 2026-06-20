import cv2
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# ==========================================
# CÁC CLASS DỮ LIỆU (GIỮ NGUYÊN ĐỂ BẢO ĐẢM TƯƠNG THÍCH PIPELINE)
# ==========================================

@dataclass
class PersonDetectionInput:
    frame_index: int
    image_path: str
    person_index: int
    bbox: List[float]
    confidence: Optional[float] = None

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

# ==========================================
# DỊCH VỤ LÕI AI-03
# ==========================================

class FaceDetectionService:
    """
    Dịch vụ phát hiện khuôn mặt sử dụng mô hình Deep Learning YuNet.
    Hoạt động bằng cách quét trực tiếp trên các vùng cơ thể (Person Bounding Box).
    """

    def __init__(
        self,
        yunet_model_path: Optional[str] = None,
        yunet_score_threshold: float = 0.6,
        yunet_nms_threshold: float = 0.3,
    ) -> None:
        self.yunet_score_threshold = yunet_score_threshold
        self.yunet_model_path = self._resolve_yunet_model_path(yunet_model_path)
        self.yunet_detector = self._load_yunet_detector(yunet_nms_threshold)

    def detect_faces_from_person_detections(
        self,
        person_detections: List[PersonDetectionInput],
        output_dir: str,
        image_extension: str = "jpg",
        jpeg_quality: int = 90,
        max_faces_per_person: Optional[int] = 1,
        min_quality_score: float = 0.0,
    ) -> FaceDetectionResult:
        """
        Trích xuất khuôn mặt từ danh sách thông tin người được quét bởi AI-02.
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        detected_faces: List[DetectedFace] = []

        if self.yunet_detector is None:
            print("Lỗi: Không tải được mô hình YuNet ONNX. Vui lòng kiểm tra đường dẫn.")
            return FaceDetectionResult(output_dir=str(output_path), detected_count=0, faces=[])

        # Bộ nhớ tạm để tránh đọc lại cùng một frame ảnh nhiều lần từ ổ cứng
        image_cache: Dict[str, Any] = {}

        for person in person_detections:
            # 1. Đọc và lưu trữ frame ảnh vào cache
            if person.image_path not in image_cache:
                image_cache[person.image_path] = cv2.imread(person.image_path)
            
            frame = image_cache[person.image_path]
            if frame is None:
                continue

            # 2. Lấy tọa độ và giới hạn chống tràn viền
            img_h, img_w = frame.shape[:2]
            x1, y1, x2, y2 = [int(v) for v in person.bbox]
            
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(img_w, x2), min(img_h, y2)
            
            person_crop = frame[y1:y2, x1:x2]
            if person_crop.size == 0:
                continue

            # 3. Cấu hình kích thước đầu vào và chạy YuNet
            crop_h, crop_w = person_crop.shape[:2]
            self.yunet_detector.setInputSize((crop_w, crop_h))
            
            _, faces = self.yunet_detector.detect(person_crop)
            if faces is None or len(faces) == 0:
                continue

            # 4. Lọc khuôn mặt có độ tự tin cao nhất (Best Match)
            best_face = max(faces, key=lambda f: f[-1])
            fx, fy, fw, fh = [int(v) for v in best_face[:4]]
            conf = float(best_face[-1])

            # fy là tọa độ Y của khuôn mặt TÍNH TỪ ĐỈNH ĐẦU của khung người xuống.
            # Nếu fy lớn hơn 40% chiều cao cơ thể (crop_h), chứng tỏ AI đang bắt vào NGỰC hoặc BỤNG.
            if fy > (crop_h * 0.40):
                continue  # Vứt bỏ ngay lập tức, đây là ảnh rác!

            # 5. Quy đổi tọa độ về hệ quy chiếu của frame gốc
            global_fx1 = x1 + fx
            global_fy1 = y1 + fy
            global_fx2 = global_fx1 + fw
            global_fy2 = global_fy1 + fh

            face_crop = frame[global_fy1:global_fy2, global_fx1:global_fx2]
            if face_crop.size == 0:
                continue

            # 6. Lưu file và đóng gói kết quả
            face_filename = f"face_frame_{person.frame_index:04d}_person_{person.person_index}.{image_extension}"
            face_image_path = output_path / face_filename
            
            cv2.imwrite(str(face_image_path), face_crop, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])

            detected_faces.append(
                DetectedFace(
                    frame_index=person.frame_index,
                    image_path=person.image_path,
                    person_index=person.person_index,
                    face_image_path=str(face_image_path),
                    bbox=[float(global_fx1), float(global_fy1), float(global_fx2), float(global_fy2)],
                    confidence=round(conf, 3),
                    quality_score=round(conf, 3),
                    width=fw,
                    height=fh,
                )
            )

        return FaceDetectionResult(
            output_dir=str(output_path),
            detected_count=len(detected_faces),
            faces=detected_faces,
        )

    def create_temp_face_dir(self) -> tempfile.TemporaryDirectory:
        """Tạo thư mục tạm thời tự động hủy sau khi sử dụng."""
        return tempfile.TemporaryDirectory(prefix="faces_")

    def _resolve_yunet_model_path(self, model_path: Optional[str]) -> Optional[Path]:
        """Tự động định vị đường dẫn đến file mô hình YuNet."""
        if model_path:
            return Path(model_path).resolve()
            
        default_path = Path(__file__).resolve().parent / "models" / "face_detection_yunet_2023mar.onnx"
        return default_path if default_path.exists() else None

    def _load_yunet_detector(self, nms_threshold: float) -> Optional[Any]:
        """Khởi tạo đối tượng phát hiện khuôn mặt từ thư viện OpenCV."""
        if self.yunet_model_path is None:
            return None
            
        try:
            return cv2.FaceDetectorYN_create(
                model=str(self.yunet_model_path),
                config="",
                input_size=(320, 320),
                score_threshold=self.yunet_score_threshold,
                nms_threshold=nms_threshold,
                top_k=5000
            )
        except cv2.error as e:
            print(f"Lỗi cấu hình OpenCV khi tải YuNet: {e}")
            return None

    def save_detection_visualization(self, image_path: str, faces: List[DetectedFace], output_path: str) -> None:
        """Vẽ khung viền (Bounding Box) lên ảnh gốc để hỗ trợ việc Debug."""
        image = cv2.imread(str(image_path))
        if image is None:
            return
            
        for face in faces:
            x1, y1, x2, y2 = [int(value) for value in face.bbox]
            label = f"Face {face.confidence:.2f}" if face.confidence else "Face"
            
            cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(image, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), image)