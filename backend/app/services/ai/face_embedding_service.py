import cv2
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

from app.services.ai.face_detection_service import DetectedFace

@dataclass
class FaceEmbeddingResult:
    face_image_path: str
    person_index: Optional[int]
    frame_index: int
    embedding: List[float]
    dimension: int
    model_name: str


class FaceEmbeddingService:
    """
    AI-04 Face Embedding Service
    
    Workflow:
    - Nhận danh sách các khuôn mặt đã được crop từ AI-03.
    - Tiền xử lý (Resize, Normalize) để phù hợp với input của mô hình.
    - Đưa qua mô hình FaceNet/ArcFace (ONNX) để trích xuất đặc trưng (Feature Vector).
    - Chuẩn hóa vector (L2 Normalization) để phục vụ thuật toán Cosine Similarity ở AI-05.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        model_name: str = "arcface",
        input_size: tuple[int, int] = (112, 112),
    ):
        self.model_name = model_name
        self.input_size = input_size
        self.model_path = self._resolve_model_path(model_path)
        self.net = self._load_model()

    def extract_embeddings_from_detected_faces(
        self, 
        detected_faces: List['DetectedFace'] 
    ) -> List[FaceEmbeddingResult]:
        """
        Xử lý hàng loạt các khuôn mặt đã nhận diện để lấy vector đặc trưng.
        """
        results: List[FaceEmbeddingResult] = []

        for face in detected_faces:
            embedding = self.extract_single_embedding(face.face_image_path)
            
            if embedding is not None:
                results.append(
                    FaceEmbeddingResult(
                        face_image_path=face.face_image_path,
                        person_index=face.person_index,
                        frame_index=face.frame_index,
                        embedding=embedding,
                        dimension=len(embedding),
                        model_name=self.model_name
                    )
                )

        return results

    def extract_single_embedding(self, image_path: str) -> Optional[List[float]]:
        """
        Trích xuất vector đặc trưng từ một đường dẫn ảnh khuôn mặt duy nhất.
        """
        if self.net is None:
            print("Loi: Chua tai duoc mo hinh Face Embedding. Khong the trich xuat Vector.")
            return None

        path = Path(image_path)
        if not path.exists():
            return None

        # Đọc ảnh khuôn mặt đã được crop
        image = cv2.imread(str(path))
        if image is None or image.size == 0:
            return None

        # 1. Tiền xử lý ảnh (Pre-processing)
        blob = self._preprocess_image(image)

        # 2. Lan truyền tiến (Forward pass) qua mạng Neural
        self.net.setInput(blob)
        try:
            raw_embedding = self.net.forward()
        except cv2.error:
            return None

        # 3. Chuẩn hóa L2 (L2 Normalization)
        # Bắt buộc thực hiện để tính khoảng cách Cosine chính xác
        normalized_embedding = self._l2_normalize(raw_embedding.flatten())

        # Ép kiểu về native float của Python để lưu DB (tránh lỗi JSON Serialize numpy.float32)
        return [float(val) for val in normalized_embedding]

    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Chuyển đổi ảnh thành định dạng blob:
        - Đổi kênh màu từ BGR (OpenCV mặc định) sang RGB.
        - Resize về kích thước chuẩn của Model.
        - Chuẩn hóa giá trị pixel.
        """
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        blob = cv2.dnn.blobFromImage(
            image_rgb,
            scalefactor=1.0 / 128.0,
            size=self.input_size,
            mean=(127.5, 127.5, 127.5),
            swapRB=False,
            crop=False
        )
        return blob

    def _l2_normalize(self, x: np.ndarray, axis: int = -1, epsilon: float = 1e-10) -> np.ndarray:
        """
        Chuẩn hóa vector đặc trưng về độ dài bằng 1.
        """
        norm = np.linalg.norm(x, axis=axis, keepdims=True)
        return x / (norm + epsilon)

    def _resolve_model_path(self, model_path: Optional[str]) -> Optional[Path]:
        """
        Xác định đường dẫn đến file mô hình (.onnx)
        """
        candidate_paths: List[Path] = []

        if model_path:
            candidate_paths.append(Path(model_path))
        else:
            candidate_paths.append(
                Path(__file__).resolve().parent / "models" / f"{self.model_name}.onnx"
            )

        for candidate in candidate_paths:
            resolved = candidate.expanduser().resolve()
            if resolved.exists() and resolved.is_file():
                return resolved

        print(f"Canh bao: Khong tim thay mo hinh Embedding ONNX tai {candidate_paths[0]}")
        return None

    def _load_model(self):
        """
        Tải mô hình vào bộ nhớ thông qua OpenCV DNN module.
        """
        if self.model_path is None:
            return None

        try:
            net = cv2.dnn.readNetFromONNX(str(self.model_path))
            return net
        except cv2.error as e:
            print(f"Loi khi tai mo hinh embedding: {e}")
            return None
        
# Khởi tạo Singleton
face_embedder = FaceEmbeddingService()