import cv2
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

# Tọa độ 5 điểm mốc chuẩn (Landmarks) cho khuôn mặt kích thước 112x112
REFERENCE_FACIAL_POINTS = np.array([
    [38.2946, 51.6963],  # Mắt trái
    [73.5318, 51.5014],  # Mắt phải 
    [56.0252, 71.7366],  # Chóp mũi
    [41.5493, 92.3655],  # Mép miệng trái
    [70.7299, 92.2041]   # Mép miệng phải
], dtype=np.float32)

def align_face_global(image: np.ndarray, face_data: np.ndarray, offset_x: int, offset_y: int) -> np.ndarray:
    """
    🚀 CẬP NHẬT: Thực hiện căn chỉnh khuôn mặt trên hệ tọa độ TOÀN CỤC (Global).
    offset_x, offset_y: Tọa độ x1, y1 của khung người để quy đổi landmark cục bộ về frame gốc.
    """
    # Lấy 5 điểm mốc cục bộ và chuyển thành tọa độ Global trên frame gốc
    local_landmarks = face_data[4:14].reshape((5, 2))
    global_landmarks = local_landmarks + np.array([offset_x, offset_y])
    
    # Tính toán ma trận biến đổi Affine dựa trên tọa độ chuẩn toàn cục
    M, _ = cv2.estimateAffinePartial2D(global_landmarks, REFERENCE_FACIAL_POINTS, method=cv2.LMEDS)
    
    if M is None:
        return None

    # Tiến hành xoay và trích xuất trực tiếp trên IMAGE GỐC (Không bị giới hạn bởi hộp người)
    aligned_face = cv2.warpAffine(image, M, (112, 112), borderValue=(0, 0, 0))
    return aligned_face

def is_occluded_by_hat_or_shadow(face_crop: np.ndarray) -> bool:
    """
    Bộ lọc toán học quét ma trận ảnh chuẩn 112x112 để phát hiện nón và bóng đổ vùng mắt.
    Trả về True nếu ảnh bị dính nón/bóng che khuất nặng.
    """
    if face_crop is None or face_crop.size == 0:
        return True

    # 1. Chuyển sang ảnh xám để phân tích cường độ sáng pixel
    gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)

    # 2. PHÂN TÍCH BÓNG ĐỔ VÙNG MẮT (Dải Y từ 40 đến 60, X từ 20 đến 92)
    # Trên ảnh 112x112 chuẩn, đây là vùng chứa đôi mắt và hốc mắt
    eye_zone = gray[40:60, 20:92]
    # Vùng má đứng ngay dưới mắt (Dải Y từ 75 đến 95), nơi nhận sáng tốt hơn khi có vành mũ
    cheek_zone = gray[75:95, 20:92]

    mean_eye = np.mean(eye_zone)
    mean_cheek = np.mean(cheek_zone)

    # Nếu vùng mắt tối hơn vùng má đáng kể (tỷ lệ < 0.65), 
    # chứng tỏ vành mũ đang đổ bóng che khuất hoàn toàn ngũ quan mắt
    if mean_eye < mean_cheek * 0.65:
        return True

    # 3. PHÂN TÍCH NHIỄU TEXTURE VÀNH MŨ (Dải Y từ 0 đến 38 - Vùng trán)
    # Trán người bình thường sẽ phẳng và mịn, biến thiên góc cạnh rất thấp.
    # Vành mũ lưỡi trai hoặc mũ bucket sẽ tạo ra các đường biên sắc nét hoặc hoa văn vải.
    forehead_zone = gray[0:38, 15:97]
    
    # Tính toán phương sai Laplacian để đo độ sắc nét/nhiễu biên vùng trán
    laplacian_var = cv2.Laplacian(forehead_zone, cv2.CV_64F).var()
    
    # Nếu phương sai quá cao (> 280), chứng tỏ vùng trán chứa cấu trúc góc cạnh của mũ
    if laplacian_var > 280.0:
        return True

    return False

# ==========================================
# CÁC CLASS DỮ LIỆU
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


class FaceDetectionService:
    def __init__(
        self,
        yunet_model_path: Optional[str] = None,
        yunet_score_threshold: float = 0.65, # Nâng nhẹ để chặn nhiễu ban đầu
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
        Trích xuất khuôn mặt đã được căn chỉnh trục không gian chuẩn xác.
        """
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
            if frame is None: continue

            img_h, img_w = frame.shape[:2]
            x1, y1, x2, y2 = [int(v) for v in person.bbox]

            box_w = x2 - x1
            box_h = y2 - y1

            pad_x = int(box_w * 0.15)
            pad_top = int(box_h * 0.18)
            pad_bottom = int(box_h * 0.05)

            x1 = max(0, x1 - pad_x)
            y1 = max(0, y1 - pad_top)
            x2 = min(img_w, x2 + pad_x)
            y2 = min(img_h, y2 + pad_bottom)

            person_crop = frame[y1:y2, x1:x2]
            if person_crop.size == 0: continue

            crop_h, crop_w = person_crop.shape[:2]
            self.yunet_detector.setInputSize((crop_w, crop_h))
            
            _, faces = self.yunet_detector.detect(person_crop)
            if faces is None or len(faces) == 0: continue

            best_face = max(faces, key=lambda f: f[-1])
            fx, fy, fw, fh = [int(v) for v in best_face[:4]]
            conf = float(best_face[-1])

            # Chặn ảnh rác ở vùng ngực/bụng
            if fy > (crop_h * 0.40): continue  

            # 🚀 1. GỌI HÀM CĂN CHỈNH TOÀN CỤC (GLOBAL ALIGNMENT)
            # Truyền frame gốc và tọa độ offset (x1, y1) để lấy trọn vẹn pixel xung quanh đầu
            face_crop = align_face_global(frame, best_face, x1, y1)

            # Fallback phòng hờ lỗi toán học hình học
            if face_crop is None:
                face_crop = person_crop[fy:fy+fh, fx:fx+fw]
                if face_crop.size == 0: continue
                face_crop = cv2.resize(face_crop, (112, 112))
            
            
            # 🚀 2. BỘ LỌC ĐẾM ĐIỂM ĐEN CHỐNG ẢNH KHUYẾT MẢNH (Black Pixel Filter)
            # Chuyển ảnh 112x112 sang ảnh xám để đếm số lượng pixel mang giá trị bằng 0 (Đen tuyệt đối)
            gray_face = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
            black_pixels = np.sum(gray_face == 0)
            black_ratio = black_pixels / (112 * 112)
            
            # Nếu dải đen do khuyết ảnh chiếm quá 15% diện tích, loại bỏ ngay lập tức
            if black_ratio > 0.15:
                continue

            # Tính tọa độ Global để vẽ BBox phục vụ việc hiển thị Video trực quan ở AI-06
            global_fx1 = x1 + fx
            global_fy1 = y1 + fy
            global_fx2 = global_fx1 + fw
            global_fy2 = global_fy1 + fh

            # Lưu file ảnh sạch sẽ
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
        return tempfile.TemporaryDirectory(prefix="faces_")

    def _resolve_yunet_model_path(self, model_path: Optional[str]) -> Optional[Path]:
        if model_path: return Path(model_path).resolve()
        default_path = Path(__file__).resolve().parent / "models" / "face_detection_yunet_2023mar.onnx"
        return default_path if default_path.exists() else None

    def _load_yunet_detector(self, nms_threshold: float) -> Optional[Any]:
        if self.yunet_model_path is None: return None
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
        image = cv2.imread(str(image_path))
        if image is None: return
        for face in faces:
            x1, y1, x2, y2 = [int(value) for value in face.bbox]
            label = f"Face {face.confidence:.2f}" if face.confidence else "Face"
            cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(image, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), image)