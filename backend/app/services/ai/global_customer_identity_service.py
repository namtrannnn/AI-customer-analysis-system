from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Optional

import numpy as np
from sqlalchemy.orm import Session

from app.models.face_embedding import FaceEmbedding
from app.models.person_profile import PersonProfile
from app.models.camera import Camera 


@dataclass(slots=True)
class GalleryMatch:
    person_profile_id: Optional[int]
    best_similarity: float
    second_similarity: float
    margin: float
    matched: bool


@dataclass(slots=True)
class SessionIdentityResult:
    session_profile_id: str
    person_profile_id: int
    anonymous_code: str
    customer_type: str
    total_visits: int
    confidence: float
    face_image_path: Optional[str]
    matched_similarity: float
    matched_margin: float
    embedding_saved: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_profile_id": self.session_profile_id,
            "person_profile_id": self.person_profile_id,
            "anonymous_code": self.anonymous_code,
            "customer_type": self.customer_type,
            "total_visits": self.total_visits,
            "confidence": self.confidence,
            "face_image_path": self.face_image_path,
            "matched_similarity": self.matched_similarity,
            "matched_margin": self.matched_margin,
            "embedding_saved": self.embedding_saved,
        }


class GlobalCustomerIdentityService:
    """
    Nhận P_id tạm của một video (P_0001, P_0002...) và ánh xạ sang
    PersonProfile toàn cục bằng FaceEmbedding trong database.

    P_id của pipeline KHÔNG được lưu làm anonymous_code toàn cục.
    """

    def __init__(
        self,
        *,
        match_threshold: float = 0.50,
        min_margin: float = 0.045,
        save_embedding_min_similarity_gap: float = 0.025,
        max_embeddings_per_profile: int = 8,
    ) -> None:
        self.match_threshold = float(match_threshold)
        self.min_margin = float(min_margin)
        self.save_embedding_min_similarity_gap = float(
            save_embedding_min_similarity_gap
        )
        self.max_embeddings_per_profile = max(
            1, int(max_embeddings_per_profile)
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify_pipeline_profiles(
        self,
        *,
        db: Session,
        merged_profiles: Iterable[dict[str, Any]],
        seen_at: Optional[datetime] = None,
        camera_id: Optional[int] = None,
        commit: bool = True,
    ) -> list[SessionIdentityResult]:
        """
        Global one-to-one assignment giữa P_id trong video và PersonProfile DB.

        Quy trình:
        1. Tính toàn bộ similarity giữa các P_id hiện tại và gallery DB.
        2. Khóa các cặp gần tuyệt đối trước.
        3. Với phần còn lại, chỉ nhận mutual-best hoặc trường hợp còn đúng
           một P_id và một DB profile.
        4. Chỉ sau khi assignment hoàn tất mới tạo New Customer.
        """
        now = seen_at or datetime.now()
        profiles = [
            dict(item)
            for item in merged_profiles
            if item.get("profile_id")
        ]
        gallery = self._load_gallery(db)

        prepared: list[dict[str, Any]] = []
        for index, item in enumerate(profiles):
            prepared.append({
                "index": index,
                "item": item,
                "session_pid": str(item["profile_id"]),
                "embedding": self.extract_profile_embedding(item),
                "confidence": self._profile_confidence(item),
                "face_path": self._profile_face_path(item),
            })

        # score_map[(current_index, db_profile_id)] = cosine/profile score
        score_map: dict[tuple[int, int], float] = {}
        for current in prepared:
            embedding = current["embedding"]
            if embedding is None:
                continue

            vector = self._normalize(embedding)
            if vector is None:
                continue

            for db_profile_id, samples in gallery.items():
                similarities = [
                    float(np.dot(vector, sample))
                    for sample in samples
                    if sample is not None
                ]
                if not similarities:
                    continue

                similarities.sort(reverse=True)
                top = similarities[: min(3, len(similarities))]
                score = 0.72 * top[0] + 0.28 * (
                    sum(top) / len(top)
                )
                score_map[(current["index"], int(db_profile_id))] = float(score)

        assigned_current: set[int] = set()
        assigned_db: set[int] = set()
        assignments: dict[int, tuple[int, float, float]] = {}

        def remaining_scores_for_current(
            current_index: int,
        ) -> list[tuple[int, float]]:
            values = [
                (db_id, score)
                for (idx, db_id), score in score_map.items()
                if idx == current_index and db_id not in assigned_db
            ]
            values.sort(key=lambda item: item[1], reverse=True)
            return values

        def remaining_scores_for_db(
            db_profile_id: int,
        ) -> list[tuple[int, float]]:
            values = [
                (idx, score)
                for (idx, db_id), score in score_map.items()
                if db_id == db_profile_id and idx not in assigned_current
            ]
            values.sort(key=lambda item: item[1], reverse=True)
            return values

        # PASS 1: khóa match gần tuyệt đối theo score giảm dần.
        exact_pairs = sorted(
            (
                (score, current_index, db_profile_id)
                for (current_index, db_profile_id), score in score_map.items()
                if score >= 0.995
            ),
            reverse=True,
        )

        for score, current_index, db_profile_id in exact_pairs:
            if (
                current_index in assigned_current
                or db_profile_id in assigned_db
            ):
                continue

            current_rank = remaining_scores_for_current(current_index)
            db_rank = remaining_scores_for_db(db_profile_id)
            if not current_rank or not db_rank:
                continue

            # Chỉ khóa khi hai phía đều xem nhau là ứng viên tốt nhất.
            if (
                current_rank[0][0] != db_profile_id
                or db_rank[0][0] != current_index
            ):
                continue

            second_score = (
                current_rank[1][1]
                if len(current_rank) > 1
                else 0.0
            )
            margin = score - second_score

            assigned_current.add(current_index)
            assigned_db.add(db_profile_id)
            assignments[current_index] = (
                db_profile_id,
                score,
                margin,
            )

        # PASS 2: mutual-best cho các profile còn lại.
        changed = True
        while changed:
            changed = False

            for current in prepared:
                current_index = int(current["index"])
                if current_index in assigned_current:
                    continue

                current_rank = remaining_scores_for_current(current_index)
                if not current_rank:
                    continue

                db_profile_id, best_score = current_rank[0]
                second_score = (
                    current_rank[1][1]
                    if len(current_rank) > 1
                    else 0.0
                )
                margin = best_score - second_score

                db_rank = remaining_scores_for_db(db_profile_id)
                if not db_rank or db_rank[0][0] != current_index:
                    continue

                normal_ok = (
                    best_score >= self.match_threshold
                    and (
                        len(current_rank) == 1
                        or margin >= self.min_margin
                    )
                )

                # Khi assignment trước đã loại hết cạnh tranh và chỉ còn
                # một cặp hợp lý, cho phép score cao nhưng margin ban đầu thấp.
                residual_unique_ok = (
                    len(current_rank) == 1
                    and len(db_rank) == 1
                    and best_score >= 0.90
                )

                if not (normal_ok or residual_unique_ok):
                    continue

                assigned_current.add(current_index)
                assigned_db.add(db_profile_id)
                assignments[current_index] = (
                    db_profile_id,
                    best_score,
                    margin,
                )
                changed = True

        print("\n========== GLOBAL ONE-TO-ONE ASSIGNMENT ==========")
        for current in prepared:
            current_index = int(current["index"])
            session_pid = current["session_pid"]
            assignment = assignments.get(current_index)
            if assignment is None:
                candidates = remaining_scores_for_current(current_index)
                top_text = " | ".join(
                    f"{db_id}:{score:.4f}"
                    for db_id, score in candidates[:3]
                )
                print(
                    f"[GLOBAL_ASSIGN] {session_pid} -> NEW "
                    f"candidates={top_text or 'none'}"
                )
            else:
                db_id, score, margin = assignment
                print(
                    f"[GLOBAL_ASSIGN] {session_pid} -> DB:{db_id} "
                    f"score={score:.4f} margin={margin:.4f}"
                )
        print("==================================================")

        results: list[SessionIdentityResult] = []

        try:
            for current in prepared:
                current_index = int(current["index"])
                session_pid = current["session_pid"]
                embedding = current["embedding"]
                confidence = float(current["confidence"])
                face_path = current["face_path"]

                assignment = assignments.get(current_index)

                if assignment is not None:
                    person_profile_id, similarity, margin = assignment
                    person = db.get(
                        PersonProfile,
                        int(person_profile_id),
                    )
                else:
                    person = None
                    similarity = 0.0
                    margin = 0.0

                if person is None:
                    person = self._create_person_profile(
                        db=db,
                        seen_at=now,
                        confidence=confidence,
                    )
                    customer_type = "new"
                else:
                    self._mark_returning_visit(
                        person=person,
                        seen_at=now,
                        confidence=confidence,
                    )
                    customer_type = "returning"

                embedding_saved = False
                if embedding is not None:
                    embedding_saved = self._save_embedding_if_useful(
                        db=db,
                        person_profile=person,
                        embedding=embedding,
                        image_url=None,
                        quality_score=self._profile_quality(
                            current["item"]
                        ),
                        camera_id=camera_id,
                        captured_at=now,
                    )

                results.append(
                    SessionIdentityResult(
                        session_profile_id=session_pid,
                        person_profile_id=int(person.id),
                        anonymous_code=str(person.anonymous_code),
                        customer_type=customer_type,
                        total_visits=int(person.total_visits or 0),
                        confidence=confidence,
                        face_image_path=face_path,
                        matched_similarity=float(similarity),
                        matched_margin=float(margin),
                        embedding_saved=embedding_saved,
                    )
                )

            if commit:
                db.commit()
                self._refresh_result_totals(db, results)

            return results
        except Exception:
            if commit:
                db.rollback()
            raise

    def match_embedding(
        self,
        embedding: np.ndarray,
        gallery: dict[int, list[np.ndarray]],
        excluded_profile_ids: Optional[set[int]] = None,
    ) -> GalleryMatch:
        vector = self._normalize(embedding)
        if vector is None or not gallery:
            return GalleryMatch(None, 0.0, 0.0, 0.0, False)

        profile_scores: list[tuple[int, float]] = []

        excluded = excluded_profile_ids or set()

        for profile_id, samples in gallery.items():
            if int(profile_id) in excluded:
                continue

            similarities = [
                float(np.dot(vector, sample))
                for sample in samples
                if sample is not None
            ]
            if not similarities:
                continue

            similarities.sort(reverse=True)
            top = similarities[: min(3, len(similarities))]
            # Kết hợp best và trung bình top để giảm match nhầm do một outlier.
            score = 0.72 * top[0] + 0.28 * (
                sum(top) / len(top)
            )
            profile_scores.append((int(profile_id), float(score)))

        if not profile_scores:
            return GalleryMatch(None, 0.0, 0.0, 0.0, False)

        profile_scores.sort(key=lambda item: item[1], reverse=True)
        best_id, best_score = profile_scores[0]
        second_score = (
            profile_scores[1][1]
            if len(profile_scores) > 1
            else 0.0
        )
        margin = best_score - second_score

        matched = (
            best_score >= self.match_threshold
            and (
                len(profile_scores) == 1
                or margin >= self.min_margin
            )
        )

        return GalleryMatch(
            person_profile_id=best_id if matched else None,
            best_similarity=best_score,
            second_similarity=second_score,
            margin=margin,
            matched=matched,
        )

    @classmethod
    def extract_profile_embedding(
        cls,
        profile: dict[str, Any],
    ) -> Optional[np.ndarray]:
        """
        Hỗ trợ nhiều tên key để tương thích các phiên bản pipeline.
        """
        direct_keys = (
            "primary_embedding",
            "best_embedding",
            "embedding",
            "face_embedding",
        )

        for key in direct_keys:
            value = profile.get(key)
            vector = cls._parse_embedding(value)
            if vector is not None:
                return vector

        list_keys = (
            "embeddings",
            "face_embeddings",
            "embedding_samples",
        )
        for key in list_keys:
            values = profile.get(key) or []
            vectors = [
                parsed
                for parsed in (
                    cls._parse_embedding(value)
                    for value in values
                )
                if parsed is not None
            ]
            if vectors:
                centroid = np.mean(
                    np.stack(vectors, axis=0),
                    axis=0,
                )
                return cls._normalize(centroid)

        best_sample = profile.get("best_identity_sample")
        if isinstance(best_sample, dict):
            return cls._parse_embedding(
                best_sample.get("embedding")
            )

        return None

    # ------------------------------------------------------------------
    # Database helpers
    # ------------------------------------------------------------------

    def _load_gallery(
        self,
        db: Session,
    ) -> dict[int, list[np.ndarray]]:
        rows = (
            db.query(FaceEmbedding)
            .filter(FaceEmbedding.embedding.isnot(None))
            .order_by(
                FaceEmbedding.person_profile_id.asc(),
                FaceEmbedding.quality_score.desc(),
                FaceEmbedding.captured_at.desc(),
            )
            .all()
        )

        gallery: dict[int, list[np.ndarray]] = {}

        for row in rows:
            profile_id = int(row.person_profile_id)
            samples = gallery.setdefault(profile_id, [])
            if len(samples) >= self.max_embeddings_per_profile:
                continue

            vector = self._parse_embedding(row.embedding)
            if vector is not None:
                samples.append(vector)

        return gallery

    def _create_person_profile(
        self,
        *,
        db: Session,
        seen_at: datetime,
        confidence: float,
    ) -> PersonProfile:
        # anonymous_code không được null, nên dùng mã tạm unique trước flush.
        temp_code = f"ANON_TMP_{uuid.uuid4().hex}"
        person = PersonProfile(
            anonymous_code=temp_code,
            person_type="anonymous",
            first_seen_at=seen_at,
            last_seen_at=seen_at,
            total_visits=1,
            confidence_avg=confidence,
        )
        db.add(person)
        db.flush()

        # Sau khi có primary key, sinh mã toàn cục ổn định.
        person.anonymous_code = f"ANON_{int(person.id):08d}"
        db.flush()
        return person

    @staticmethod
    def _mark_returning_visit(
        *,
        person: PersonProfile,
        seen_at: datetime,
        confidence: float,
    ) -> None:
        old_visits = max(0, int(person.total_visits or 0))

        # Dữ liệu cũ hoặc sentinel -1 có thể đã lọt vào DB từ các bản trước.
        # Luôn chuẩn hóa cả average cũ và confidence mới về [0, 1].
        new_confidence = max(0.0, min(1.0, float(confidence or 0.0)))

        old_average = None
        if person.confidence_avg is not None:
            try:
                parsed_old_average = float(person.confidence_avg)
                if math.isfinite(parsed_old_average):
                    old_average = max(0.0, min(1.0, parsed_old_average))
            except (TypeError, ValueError):
                old_average = None

        person.total_visits = old_visits + 1
        person.last_seen_at = seen_at

        if person.first_seen_at is None:
            person.first_seen_at = seen_at

        if old_average is None or old_visits <= 0:
            next_average = new_confidence
        else:
            next_average = (
                old_average * old_visits + new_confidence
            ) / (old_visits + 1)

        person.confidence_avg = max(0.0, min(1.0, float(next_average)))

    def _save_embedding_if_useful(
        self,
        *,
        db: Session,
        person_profile: PersonProfile,
        embedding: np.ndarray,
        image_url: Optional[str],
        quality_score: Optional[float],
        camera_id: Optional[int],
        captured_at: datetime,
    ) -> bool:
        vector = self._normalize(embedding)
        if vector is None:
            return False

        existing_rows = (
            db.query(FaceEmbedding)
            .filter(
                FaceEmbedding.person_profile_id
                == int(person_profile.id)
            )
            .order_by(
                FaceEmbedding.quality_score.desc(),
                FaceEmbedding.captured_at.desc(),
            )
            .limit(self.max_embeddings_per_profile)
            .all()
        )

        existing_vectors = [
            parsed
            for parsed in (
                self._parse_embedding(row.embedding)
                for row in existing_rows
            )
            if parsed is not None
        ]

        if existing_vectors:
            best_similarity = max(
                float(np.dot(vector, known))
                for known in existing_vectors
            )
            # Nếu gần như trùng embedding cũ thì không lưu thêm.
            if best_similarity >= (
                1.0 - self.save_embedding_min_similarity_gap
            ):
                return False

        record = FaceEmbedding(
            person_profile_id=int(person_profile.id),
            camera_id=camera_id,
            image_url=image_url,
            embedding=[
                float(value)
                for value in vector.tolist()
            ],
            quality_score=(
                max(0.0, float(quality_score))
                if quality_score is not None
                else None
            ),
            captured_at=captured_at,
        )
        db.add(record)
        db.flush()
        return True

    @staticmethod
    def _refresh_result_totals(
        db: Session,
        results: list[SessionIdentityResult],
    ) -> None:
        by_id = {
            int(person_id): person
            for person_id, person in (
                (
                    result.person_profile_id,
                    db.get(
                        PersonProfile,
                        result.person_profile_id,
                    ),
                )
                for result in results
            )
            if person is not None
        }

        for result in results:
            person = by_id.get(result.person_profile_id)
            if person is not None:
                result.total_visits = int(
                    person.total_visits or 0
                )
                result.anonymous_code = str(
                    person.anonymous_code
                )

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    @classmethod
    def _parse_embedding(
        cls,
        value: Any,
    ) -> Optional[np.ndarray]:
        if value is None:
            return None

        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (TypeError, ValueError, json.JSONDecodeError):
                return None

        if isinstance(value, dict):
            value = (
                value.get("embedding")
                or value.get("vector")
                or value.get("values")
            )

        try:
            vector = np.asarray(
                value,
                dtype=np.float32,
            ).reshape(-1)
        except (TypeError, ValueError):
            return None

        return cls._normalize(vector)

    @staticmethod
    def _normalize(
        vector: Any,
    ) -> Optional[np.ndarray]:
        try:
            array = np.asarray(
                vector,
                dtype=np.float32,
            ).reshape(-1)
        except (TypeError, ValueError):
            return None

        if array.size == 0 or not np.all(np.isfinite(array)):
            return None

        norm = float(np.linalg.norm(array))
        if norm <= 1e-12:
            return None

        return array / norm

    @staticmethod
    def _profile_confidence(
        profile: dict[str, Any],
    ) -> float:
        value = (
            profile.get("best_face_confidence")
            if profile.get("best_face_confidence") is not None
            else profile.get("confidence")
        )
        return max(0.0, min(1.0, float(value or 0.0)))

    @staticmethod
    def _profile_quality(
        profile: dict[str, Any],
    ) -> Optional[float]:
        value = (
            profile.get("best_face_quality")
            if profile.get("best_face_quality") is not None
            else profile.get("quality_score")
        )
        return (
            max(0.0, float(value))
            if value is not None
            else None
        )

    @staticmethod
    def _profile_face_path(
        profile: dict[str, Any],
    ) -> Optional[str]:
        value = (
            profile.get("best_face_image_path")
            or profile.get("face_image_path")
        )
        return str(value) if value else None


global_customer_identity_service = GlobalCustomerIdentityService()