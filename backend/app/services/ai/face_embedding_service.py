from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Any

import cv2
import numpy as np


@dataclass
class FaceEmbeddingResult:
    face_image_path: str
    person_index: Optional[int]
    frame_index: Optional[int]
    embedding: List[float]
    dimension: int
    model_name: str
    aligned: bool = False
    align_score: Optional[float] = None


class FaceEmbeddingService:
    """
    AI-04 Face Embedding service with landmark alignment.

    Compatible with the existing pipeline API:
        FaceEmbeddingService(model_path=..., model_name=..., input_size=(112, 112))
        extract_embeddings_from_detected_faces(detected_faces)

    Why this version exists:
    - ArcFace/SFace embeddings are much more stable when the input face is aligned
      by 5 landmarks before resizing to 112x112.
    - The previous pipeline usually embedded a raw face crop. With yaw/pose changes,
      two visually similar faces can produce low cosine similarity.

    This service re-detects landmarks inside the saved face crop using YuNet,
    aligns the crop to the ArcFace 112x112 template, then runs the existing DNN
    embedding model. If YuNet landmarks are unavailable, it falls back to the old
    resize-based behavior instead of failing.
    """

    # InsightFace/ArcFace canonical 5-point template for 112x112.
    _ARC_FACE_TEMPLATE = np.array(
        [
            [38.2946, 51.6963],  # left eye
            [73.5318, 51.5014],  # right eye
            [56.0252, 71.7366],  # nose
            [41.5493, 92.3655],  # left mouth
            [70.7299, 92.2041],  # right mouth
        ],
        dtype=np.float32,
    )

    def __init__(
        self,
        model_path: Optional[str] = None,
        model_name: str = "face_recognition_sface_2021dec.onnx",
        input_size: Tuple[int, int] = (112, 112),
        yunet_model_path: Optional[str] = None,
        enable_alignment: bool = True,
        align_score_threshold: float = 0.45,
    ) -> None:
        self.input_size = tuple(input_size)
        self.model_name = model_name
        self.enable_alignment = bool(enable_alignment)
        self.align_score_threshold = float(align_score_threshold)

        self.model_path = self._resolve_model_path(model_path, model_name)
        self.net = None
        if self.model_path and os.path.exists(self.model_path):
            self.net = cv2.dnn.readNetFromONNX(self.model_path)
        else:
            print(
                f"[FaceEmbeddingService] WARNING: embedding model not found: "
                f"model_path={model_path}, model_name={model_name}"
            )

        self.yunet_model_path = self._resolve_yunet_path(yunet_model_path)
        self.landmark_detector = None
        if self.enable_alignment and self.yunet_model_path and os.path.exists(self.yunet_model_path):
            try:
                self.landmark_detector = cv2.FaceDetectorYN_create(
                    self.yunet_model_path,
                    "",
                    (112, 112),
                    score_threshold=max(0.1, min(0.99, self.align_score_threshold)),
                    nms_threshold=0.3,
                    top_k=5000,
                )
            except Exception as exc:
                print(f"[FaceEmbeddingService] WARNING: cannot create YuNet aligner: {exc}")
                self.landmark_detector = None
        elif self.enable_alignment:
            print(
                f"[FaceEmbeddingService] WARNING: YuNet model not found for alignment: "
                f"{self.yunet_model_path}. Fallback to resize embedding."
            )

        print(
            "FACE_EMBEDDING_VERSION = aligned_face_gallery_v1 | "
            f"model={Path(self.model_path).name if self.model_path else model_name} | "
            f"alignment={'on' if self.landmark_detector is not None else 'fallback_resize'}"
        )

    def extract_embedding(self, face_image_path: str) -> Optional[FaceEmbeddingResult]:
        results = self.extract_embeddings_from_detected_faces([face_image_path])
        return results[0] if results else None

    def extract_embeddings_from_detected_faces(self, detected_faces: List[Any]) -> List[FaceEmbeddingResult]:
        results: List[FaceEmbeddingResult] = []
        if self.net is None:
            return results

        for face in detected_faces:
            face_path = self._get_attr(face, "face_image_path", None) or (face if isinstance(face, str) else None)
            if not face_path or not os.path.exists(str(face_path)):
                continue

            image = cv2.imread(str(face_path))
            if image is None or image.size == 0:
                continue

            aligned_img, aligned, align_score = self._align_or_resize(image)
            embedding = self._forward_embedding(aligned_img)
            if embedding is None:
                continue

            results.append(
                FaceEmbeddingResult(
                    face_image_path=str(face_path),
                    person_index=self._get_attr(face, "person_index", None),
                    frame_index=self._get_attr(face, "frame_index", None),
                    embedding=embedding.astype(np.float32).tolist(),
                    dimension=int(embedding.shape[0]),
                    model_name=self.model_name,
                    aligned=bool(aligned),
                    align_score=align_score,
                )
            )

        return results

    def _forward_embedding(self, aligned_img: np.ndarray) -> Optional[np.ndarray]:
        if aligned_img is None or aligned_img.size == 0 or self.net is None:
            return None

        # Preserve the existing ArcFace/SFace-style preprocessing used in the project:
        # scale=1/128, mean=127.5. Keep BGR order to avoid changing model behavior
        # beyond the alignment improvement.
        blob = cv2.dnn.blobFromImage(
            aligned_img,
            scalefactor=1.0 / 128.0,
            size=self.input_size,
            mean=(127.5, 127.5, 127.5),
            swapRB=False,
            crop=False,
        )
        self.net.setInput(blob)
        vector = self.net.forward().reshape(-1).astype(np.float32)
        norm = np.linalg.norm(vector)
        if not np.isfinite(norm) or norm <= 1e-12:
            return None
        return vector / norm

    def _align_or_resize(self, image: np.ndarray) -> Tuple[np.ndarray, bool, Optional[float]]:
        if self.landmark_detector is None:
            return cv2.resize(image, self.input_size), False, None

        h, w = image.shape[:2]
        if h < 20 or w < 20:
            return cv2.resize(image, self.input_size), False, None

        try:
            self.landmark_detector.setInputSize((w, h))
            _, faces = self.landmark_detector.detect(image)
        except Exception:
            faces = None

        if faces is None or len(faces) == 0:
            return cv2.resize(image, self.input_size), False, None

        # Pick the highest-score face in the face crop.
        best = max(faces, key=lambda row: float(row[-1]))
        score = float(best[-1])
        if score < self.align_score_threshold:
            return cv2.resize(image, self.input_size), False, score

        # YuNet landmark order is commonly:
        # right_eye, left_eye, nose, right_mouth, left_mouth.
        # ArcFace template expects: left_eye, right_eye, nose, left_mouth, right_mouth.
        pts = best[4:14].reshape(5, 2).astype(np.float32)
        right_eye, left_eye, nose, right_mouth, left_mouth = pts
        src = np.array([left_eye, right_eye, nose, left_mouth, right_mouth], dtype=np.float32)

        dst = self._scaled_template(self.input_size)
        matrix, _ = cv2.estimateAffinePartial2D(src, dst, method=cv2.LMEDS)
        if matrix is None:
            return cv2.resize(image, self.input_size), False, score

        aligned = cv2.warpAffine(
            image,
            matrix,
            self.input_size,
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        return aligned, True, score

    @classmethod
    def _scaled_template(cls, input_size: Tuple[int, int]) -> np.ndarray:
        width, height = input_size
        template = cls._ARC_FACE_TEMPLATE.copy()
        template[:, 0] *= float(width) / 112.0
        template[:, 1] *= float(height) / 112.0
        return template.astype(np.float32)

    @staticmethod
    def _get_attr(obj: Any, name: str, default=None):
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    @staticmethod
    def _resolve_model_path(model_path: Optional[str], model_name: str) -> Optional[str]:
        candidates = []
        if model_path:
            candidates.append(Path(model_path))
        current_dir = Path(__file__).resolve().parent
        candidates.extend(
            [
                current_dir / "models" / model_name,
                current_dir / "models" / "face_recognition_sface_2021dec.onnx",
                current_dir / "models" / "arcface.onnx",
                Path.cwd() / "models" / model_name,
                Path.cwd() / "app" / "services" / "ai" / "models" / model_name,
                Path.cwd() / "app" / "services" / "ai" / "models" / "face_recognition_sface_2021dec.onnx",
                Path.cwd() / "app" / "services" / "ai" / "models" / "arcface.onnx",
            ]
        )
        for path in candidates:
            if path and path.exists():
                return str(path)
        return str(candidates[0]) if candidates else None

    @staticmethod
    def _resolve_yunet_path(yunet_model_path: Optional[str]) -> Optional[str]:
        candidates = []
        if yunet_model_path:
            candidates.append(Path(yunet_model_path))
        current_dir = Path(__file__).resolve().parent
        name = "face_detection_yunet_2023mar.onnx"
        candidates.extend(
            [
                current_dir / "models" / name,
                Path.cwd() / "models" / name,
                Path.cwd() / "app" / "services" / "ai" / "models" / name,
            ]
        )
        for path in candidates:
            if path and path.exists():
                return str(path)
        return str(candidates[0]) if candidates else None


# Backward-compatible singleton, in case some code imports face_embedder directly.
try:
    face_embedder = FaceEmbeddingService()
except Exception:
    face_embedder = None
