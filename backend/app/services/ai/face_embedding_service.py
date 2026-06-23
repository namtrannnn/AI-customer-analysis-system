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
    AI-04 Face Embedding Service - Tối ưu hóa riêng cho SFace (OpenCV Zoo)
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        model_name: str = "face_recognition_sface_2021dec",
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
        Trích xuất vector đặc trưng từ ảnh khuôn mặt bằng mô hình SFace.
        """
        if self.net is None:
            print("Loi: Chua tai duoc mo hinh SFace Embedding. Khong the trich xuat Vector.")
            return None

        path = Path(image_path)
        if not path.exists():
            return None

        # Đọc ảnh khuôn mặt
        image = cv2.imread(str(path))
        if image is None or image.size == 0:
            return None

        # 1. Tiền xử lý ảnh cho SFACE:
        # SFace của OpenCV Zoo chạy trực tiếp trên kênh màu BGR nguyên bản.
        # Không cần swapRB sang RGB, không cần trừ mean hay chia scale thủ công!
        blob = cv2.dnn.blobFromImage(
            image,
            scalefactor=1.0,
            size=self.input_size,
            mean=(0, 0, 0),
            swapRB=False,
            crop=False
        )

        # 2. Lan truyền tiến (Forward pass)
        self.net.setInput(blob)
        try:
            raw_embedding = self.net.forward()
        except cv2.error as e:
            print(f"Loi gieo tin hieu qua mang SFace: {e}")
            return None

        # 3. Chuẩn hóa L2 (L2 Normalization) để tính Cosine chuẩn xác
        normalized_embedding = self._l2_normalize(raw_embedding.flatten())

        return [float(val) for val in normalized_embedding]

    def _l2_normalize(self, x: np.ndarray, axis: int = -1, epsilon: float = 1e-10) -> np.ndarray:
        norm = np.linalg.norm(x, axis=axis, keepdims=True)
        return x / (norm + epsilon)

    def _resolve_model_path(self, model_path: Optional[str]) -> Optional[Path]:
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

        print(f"Canh bao: Khong tim thay mo hinh SFace tai {candidate_paths[0]}")
        return None

    def _load_model(self):
        if self.model_path is None:
            return None
        try:
            net = cv2.dnn.readNetFromONNX(str(self.model_path))
            return net
        except cv2.error as e:
            print(f"Loi khi nap mo hinh SFace ONNX: {e}")
            return None