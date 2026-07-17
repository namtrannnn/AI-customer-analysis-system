from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from threading import RLock
from typing import Any, Deque, Dict, List, Optional, Tuple

import numpy as np


@dataclass(slots=True)
class FaceEvidence:
    frame_index: int
    embedding: np.ndarray
    face_confidence: float
    quality_score: float
    candidate_profile_id: Optional[str] = None
    candidate_similarity: float = 0.0


class MultiFrameFaceMatchingService:
    """
    AI-04: gom bằng chứng mặt qua nhiều frame/track.

    Service không tự thay OnlineIdentityService. Nó tạo consensus trước khi cho phép
    relink track mới sang profile cũ, giúp track ID đổi nhưng Person Profile vẫn giữ.
    """

    def __init__(
        self,
        max_samples_per_track: int = 8,
        min_samples_for_consensus: int = 3,
        min_average_similarity: float = 0.78,
        min_vote_ratio: float = 0.67,
        min_face_confidence: float = 0.65,
    ) -> None:
        self.max_samples_per_track = max(3, int(max_samples_per_track))
        self.min_samples_for_consensus = max(2, int(min_samples_for_consensus))
        self.min_average_similarity = float(min_average_similarity)
        self.min_vote_ratio = float(min_vote_ratio)
        self.min_face_confidence = float(min_face_confidence)
        self._track_evidence: Dict[int, Deque[FaceEvidence]] = defaultdict(
            lambda: deque(maxlen=self.max_samples_per_track)
        )
        self._profile_centroids: Dict[str, np.ndarray] = {}
        self._track_to_profile: Dict[int, str] = {}
        self._lock = RLock()

    @staticmethod
    def _normalize(value: Any) -> np.ndarray:
        vector = np.asarray(value, dtype=np.float32).reshape(-1)
        norm = float(np.linalg.norm(vector))
        if norm <= 1e-12:
            raise ValueError("zero embedding")
        return vector / norm

    def update_profile_embedding(self, profile_id: str, embedding: Any, momentum: float = 0.85) -> None:
        vector = self._normalize(embedding)
        with self._lock:
            old = self._profile_centroids.get(profile_id)
            if old is None:
                self._profile_centroids[profile_id] = vector
            else:
                merged = momentum * old + (1.0 - momentum) * vector
                self._profile_centroids[profile_id] = self._normalize(merged)

    def add_track_sample(
        self,
        *,
        track_id: int,
        frame_index: int,
        embedding: Any,
        face_confidence: float,
        quality_score: float = 0.0,
    ) -> Optional[Dict[str, Any]]:
        if float(face_confidence) < self.min_face_confidence:
            return None

        vector = self._normalize(embedding)
        candidate_id = None
        candidate_similarity = -1.0

        with self._lock:
            for profile_id, centroid in self._profile_centroids.items():
                similarity = float(np.dot(vector, centroid))
                if similarity > candidate_similarity:
                    candidate_id = profile_id
                    candidate_similarity = similarity

            evidence = FaceEvidence(
                frame_index=int(frame_index),
                embedding=vector,
                face_confidence=float(face_confidence),
                quality_score=float(quality_score),
                candidate_profile_id=candidate_id,
                candidate_similarity=max(0.0, candidate_similarity),
            )
            self._track_evidence[int(track_id)].append(evidence)
            return self._consensus_locked(int(track_id))

    def _consensus_locked(self, track_id: int) -> Optional[Dict[str, Any]]:
        samples = list(self._track_evidence.get(track_id, []))
        if len(samples) < self.min_samples_for_consensus:
            return None

        votes: Dict[str, List[float]] = defaultdict(list)
        for sample in samples:
            if sample.candidate_profile_id:
                votes[sample.candidate_profile_id].append(sample.candidate_similarity)
        if not votes:
            return None

        profile_id, similarities = max(
            votes.items(),
            key=lambda item: (len(item[1]), sum(item[1]) / len(item[1])),
        )
        vote_ratio = len(similarities) / len(samples)
        average_similarity = sum(similarities) / len(similarities)

        if (
            len(similarities) >= self.min_samples_for_consensus
            and vote_ratio >= self.min_vote_ratio
            and average_similarity >= self.min_average_similarity
        ):
            self._track_to_profile[track_id] = profile_id
            return {
                "track_id": track_id,
                "profile_id": profile_id,
                "sample_count": len(samples),
                "vote_count": len(similarities),
                "vote_ratio": vote_ratio,
                "average_similarity": average_similarity,
                "decision": "RELINK",
            }
        return None

    def bind_track(self, track_id: int, profile_id: str) -> None:
        with self._lock:
            self._track_to_profile[int(track_id)] = str(profile_id)

    def get_profile_for_track(self, track_id: int) -> Optional[str]:
        with self._lock:
            return self._track_to_profile.get(int(track_id))

    def clear_track(self, track_id: int) -> None:
        with self._lock:
            self._track_evidence.pop(int(track_id), None)
