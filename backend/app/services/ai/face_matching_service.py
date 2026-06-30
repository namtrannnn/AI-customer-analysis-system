import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class ProcessedCustomer:
    track_id: int
    observation_count: int
    best_face_image_path: str
    embedding: List[float]
    face_confidence: float
    observed_frame_indices: List[int]


class FaceMatchingService:
    """
    AI-05 Face Matching Service

    Mục tiêu:
    - Không gộp nhầm 2 người khác nhau.
    - Vẫn gộp được các track bị vỡ của cùng 1 người nếu similarity đủ chắc.
    - Không dùng relaxed threshold quá thấp khi chỉ có 1 embedding.
    """

    def __init__(
        self,
        strict_threshold: float = 0.42,
        soft_threshold: float = 0.36,
        min_margin: float = 0.05,
        max_embeddings_per_profile: int = 5,
        weak_fragment_max_observations: int = 12,
        weak_fragment_threshold: float = 0.30,
    ):
        self.strict_threshold = strict_threshold
        self.soft_threshold = soft_threshold
        self.min_margin = min_margin
        self.max_embeddings_per_profile = max_embeddings_per_profile
        self.weak_fragment_max_observations = weak_fragment_max_observations
        self.weak_fragment_threshold = weak_fragment_threshold

    def merge_fragmented_customers(self, customers: List[ProcessedCustomer]) -> List[Dict]:
        final_profiles: List[Dict] = []

        sorted_customers = sorted(
            customers,
            key=lambda c: (
                c.observation_count,
                c.face_confidence if c.face_confidence else 0.0,
            ),
            reverse=True,
        )

        for current_customer in sorted_customers:
            if not current_customer.embedding:
                continue

            current_vector = self._normalize(
                np.array(current_customer.embedding, dtype=np.float32)
            )

            if current_vector is None:
                continue

            ranked_matches = []

            for profile in final_profiles:
                # Nếu 2 người này từng xuất hiện song song trong cùng 1 frame, chắc chắn là 2 người khác nhau.
                if self._has_frame_overlap(current_customer.observed_frame_indices, profile.get("observed_frame_indices", [])):
                    print(f"[AI-05 Log] Chặn gộp Trk_{current_customer.track_id} vs {profile['profile_id']} -> Đi song song cùng lúc!")
                    continue # Cắt đứt luồng kiểm tra, sang profile tiếp theo

                profile_embeddings = profile.get("embeddings", [])

                similarities = []
                for emb in profile_embeddings:
                    known_vector = self._normalize(np.array(emb, dtype=np.float32))
                    if known_vector is None:
                        continue

                    similarity = self._cosine_similarity(current_vector, known_vector)
                    similarities.append(similarity)

                if not similarities:
                    continue

                max_similarity = max(similarities)

                ranked_matches.append({
                    "profile": profile,
                    "score": max_similarity,
                    "support_count": sum(s >= self.soft_threshold for s in similarities),
                    "embedding_count": len(profile_embeddings),
                })

                print(
                    f"[AI-05 Log] Trk_{current_customer.track_id} "
                    f"vs {profile['profile_id']} -> Score: {max_similarity:.3f}"
                )

            if not ranked_matches:
                self._create_new_profile(final_profiles, current_customer)
                continue

            ranked_matches.sort(key=lambda x: x["score"], reverse=True)

            best_match = ranked_matches[0]
            best_profile = best_match["profile"]
            best_score = best_match["score"]

            second_score = ranked_matches[1]["score"] if len(ranked_matches) > 1 else -1.0
            margin = best_score - second_score

            should_merge = self._should_merge(
                current_customer=current_customer,
                best_score=best_score,
                margin=margin,
                support_count=best_match["support_count"],
                embedding_count=best_match["embedding_count"],
            )

            if should_merge:
                self._merge_into_profile(
                    profile=best_profile,
                    customer=current_customer,
                    match_score=best_score,
                )
            else:
                self._create_new_profile(final_profiles, current_customer)

        final_profiles = self._post_merge_profiles(final_profiles)
        final_profiles = self._merge_weak_fragments(final_profiles)
        return final_profiles

    def _should_merge(
        self,
        current_customer: ProcessedCustomer,
        best_score: float,
        margin: float,
        support_count: int,
        embedding_count: int,
    ) -> bool:
        """
        Quy tắc merge phù hợp với pipeline hiện tại,
        nơi mỗi track_id mới thường chỉ có 1 embedding.

        - >= strict_threshold: merge.
        - soft_threshold -> strict_threshold: cho merge có điều kiện.
        - < soft_threshold: không merge.
        """

        current_conf = current_customer.face_confidence or 0.0
        current_obs = current_customer.observation_count or 0

        # Ảnh mặt quá yếu thì không merge để tránh gộp nhầm
        if current_conf < 0.55:
            return False

        # 1. Vùng chắc chắn
        if best_score >= self.strict_threshold:
            # Nếu có nhiều profile gần giống nhau, cần cách biệt
            if margin >= 0 and margin < self.min_margin and best_score < 0.46:
                return False
            return True

        # 2. Vùng mềm: 0.35 -> 0.40
        # Vì pipeline hiện tại chỉ có 1 embedding/profile,
        # không được bắt buộc embedding_count >= 2 nữa.
        if best_score >= self.soft_threshold:
            # Case A: track hiện tại xuất hiện đủ lâu, ảnh mặt ổn
            if current_obs >= 3 and current_conf >= 0.60:
                if margin >= self.min_margin or margin < 0:
                    return True

            # Case B: score gần strict, cho merge nhẹ hơn
            if best_score >= self.strict_threshold - 0.02 and current_conf >= 0.58:
                if margin >= self.min_margin or margin < 0:
                    return True

        return False

    def _merge_into_profile(
        self,
        profile: Dict,
        customer: ProcessedCustomer,
        match_score: float,
    ) -> None:
        profile["merged_track_ids"].append(customer.track_id)
        profile["total_observations"] += customer.observation_count
        profile["match_scores"].append(round(float(match_score), 4))

        # CẬP NHẬT DANH SÁCH FRAME MÀ PROFILE NÀY ĐÃ XUẤT HIỆN
        profile_frames = set(profile.get("observed_frame_indices", []))
        profile_frames.update(customer.observed_frame_indices)
        profile["observed_frame_indices"] = sorted(list(profile_frames))

        # Lưu thêm embedding của track mới vào profile
        self._append_embedding(profile, customer.embedding)

        # Cập nhật ảnh đại diện nếu ảnh mới tốt hơn
        if customer.face_confidence > profile["best_face_confidence"]:
            profile["best_face_image_path"] = customer.best_face_image_path
            profile["best_face_confidence"] = customer.face_confidence
            profile["primary_embedding"] = customer.embedding

    def _create_new_profile(
        self,
        final_profiles: List[Dict],
        customer: ProcessedCustomer,
    ) -> None:
        final_profiles.append({
            "profile_id": f"P_{customer.track_id:04d}",
            "merged_track_ids": [customer.track_id],
            "total_observations": customer.observation_count,
            "best_face_image_path": customer.best_face_image_path,
            "best_face_confidence": customer.face_confidence,
            "primary_embedding": customer.embedding,
            "embeddings": [customer.embedding],
            "match_scores": [],
            "observed_frame_indices": customer.observed_frame_indices,
        })

    def _append_embedding(self, profile: Dict, embedding: List[float]) -> None:
        embeddings = profile.setdefault("embeddings", [])
        embeddings.append(embedding)

        if len(embeddings) > self.max_embeddings_per_profile:
            # Giữ embedding đầu tiên + các embedding mới nhất
            first_embedding = embeddings[0]
            recent_embeddings = embeddings[-(self.max_embeddings_per_profile - 1):]
            profile["embeddings"] = [first_embedding] + recent_embeddings
        
    def _merge_weak_fragments(self, profiles: List[Dict]) -> List[Dict]:
        """
        Merge các profile rất ngắn, thường là tracklet bị vỡ do:
        - người đi nhanh
        - đội nón
        - mặt mờ / nghiêng / bị che
        - tracking bị đứt đoạn

        Chỉ áp dụng cho profile có total_observations thấp.
        """

        if len(profiles) <= 1:
            return profiles

        # Xử lý profile ngắn trước
        profiles = sorted(
            profiles,
            key=lambda p: p.get("total_observations", 0)
        )

        removed_ids = set()

        for small_profile in profiles:
            small_id = small_profile["profile_id"]

            if small_id in removed_ids:
                continue

            small_obs = small_profile.get("total_observations", 0)

            # Chỉ xử lý profile rất ngắn
            if small_obs > self.weak_fragment_max_observations:
                continue

            best_target = None
            best_score = -1.0

            for target_profile in profiles:
                target_id = target_profile["profile_id"]

                if target_id == small_id or target_id in removed_ids:
                    continue

                target_obs = target_profile.get("total_observations", 0)

                # Không merge small vào một profile cũng quá ngắn
                if target_obs <= self.weak_fragment_max_observations:
                    continue

                # Nếu từng xuất hiện cùng frame thì chắc chắn không phải cùng người
                if self._has_frame_overlap(
                    small_profile.get("observed_frame_indices", []),
                    target_profile.get("observed_frame_indices", []),
                ):
                    continue

                score = self._profile_similarity(small_profile, target_profile)

                print(
                    f"[AI-05 WeakMerge] {small_id} "
                    f"vs {target_id} -> Score: {score:.3f}, "
                    f"small_obs={small_obs}, target_obs={target_obs}"
                )

                if score > best_score:
                    best_score = score
                    best_target = target_profile

            if best_target is None:
                continue

            # Chỉ gộp fragment ngắn nếu similarity đủ mức yếu
            if best_score >= self.weak_fragment_threshold:
                print(
                    f"[AI-05 WeakMerge] MERGE fragment {small_id} "
                    f"vào {best_target['profile_id']} -> Score: {best_score:.3f}"
                )

                self._merge_profile_into_profile(
                    target_profile=best_target,
                    source_profile=small_profile,
                    match_score=best_score,
                )

                removed_ids.add(small_id)

        return [
            p for p in profiles
            if p["profile_id"] not in removed_ids
        ]

    def _post_merge_profiles(self, profiles: List[Dict]) -> List[Dict]:
        """
        Merge lần 2 ở cấp profile.

        Mục tiêu:
        - Sau khi one-pass merge xong, kiểm tra lại các profile còn sót.
        - Nếu 2 profile rất giống nhau và không từng xuất hiện cùng frame,
        gộp lại để loại bỏ duplicate người.
        """

        changed = True

        while changed:
            changed = False
            merged_profiles = []
            used_indices = set()

            for i, profile_a in enumerate(profiles):
                if i in used_indices:
                    continue

                best_j = None
                best_score = -1.0

                for j, profile_b in enumerate(profiles):
                    if i == j or j in used_indices:
                        continue

                    # Nếu từng xuất hiện cùng frame thì không merge,
                    # vì khả năng cao là 2 người khác nhau.
                    if self._has_frame_overlap(
                        profile_a.get("observed_frame_indices", []),
                        profile_b.get("observed_frame_indices", []),
                    ):
                        continue

                    score = self._profile_similarity(profile_a, profile_b)

                    print(
                        f"[AI-05 PostMerge] {profile_a['profile_id']} "
                        f"vs {profile_b['profile_id']} -> Score: {score:.3f}"
                    )

                    if score > best_score:
                        best_score = score
                        best_j = j

                if best_j is not None and self._should_post_merge(profile_a, profiles[best_j], best_score):
                    profile_b = profiles[best_j]

                    print(
                        f"[AI-05 PostMerge] MERGE {profile_b['profile_id']} "
                        f"vào {profile_a['profile_id']} -> Score: {best_score:.3f}"
                    )

                    self._merge_profile_into_profile(profile_a, profile_b, best_score)

                    used_indices.add(i)
                    used_indices.add(best_j)
                    merged_profiles.append(profile_a)
                    changed = True
                else:
                    used_indices.add(i)
                    merged_profiles.append(profile_a)

            profiles = merged_profiles

        return profiles


    def _profile_similarity(self, profile_a: Dict, profile_b: Dict) -> float:
        """
        Tính độ giống nhau giữa 2 profile.

        Dùng max similarity giữa nhiều embedding,
        vì cùng 1 người có thể có nhiều góc mặt khác nhau.
        """

        embeddings_a = profile_a.get("embeddings", [])
        embeddings_b = profile_b.get("embeddings", [])

        best_score = -1.0

        for emb_a in embeddings_a:
            vec_a = self._normalize(np.array(emb_a, dtype=np.float32))
            if vec_a is None:
                continue

            for emb_b in embeddings_b:
                vec_b = self._normalize(np.array(emb_b, dtype=np.float32))
                if vec_b is None:
                    continue

                score = self._cosine_similarity(vec_a, vec_b)

                if score > best_score:
                    best_score = score

        return best_score


    def _should_post_merge(self, profile_a: Dict, profile_b: Dict, score: float) -> bool:
        """
        Luật merge profile lần 2.

        Nới hơn một chút so với merge track ban đầu,
        vì cả hai bên đều đã là profile hợp lệ.
        """

        conf_a = profile_a.get("best_face_confidence", 0.0) or 0.0
        conf_b = profile_b.get("best_face_confidence", 0.0) or 0.0

        obs_a = profile_a.get("total_observations", 0) or 0
        obs_b = profile_b.get("total_observations", 0) or 0

        # Không merge nếu cả hai ảnh đại diện đều quá yếu
        if conf_a < 0.50 and conf_b < 0.50:
            return False

        # Merge chắc chắn
        if score >= self.strict_threshold:
            return True

        # Merge mềm cho duplicate sót lại
        if score >= self.soft_threshold:
            # Nếu một profile là track ngắn / ít quan sát,
            # rất có thể là mảnh vỡ của người kia.
            if min(obs_a, obs_b) <= 5:
                return True

            # Nếu cả hai profile có face confidence ổn thì cho merge.
            if conf_a >= 0.4 and conf_b >= 0.4:
                return True

        return False


    def _merge_profile_into_profile(
        self,
        target_profile: Dict,
        source_profile: Dict,
        match_score: float,
    ) -> None:
        """
        Gộp source_profile vào target_profile.
        """

        target_profile["merged_track_ids"].extend(source_profile.get("merged_track_ids", []))
        target_profile["merged_track_ids"] = sorted(list(set(target_profile["merged_track_ids"])))

        target_profile["total_observations"] += source_profile.get("total_observations", 0)

        target_profile["match_scores"].append(round(float(match_score), 4))
        target_profile["match_scores"].extend(source_profile.get("match_scores", []))

        # Gộp frame xuất hiện
        frames = set(target_profile.get("observed_frame_indices", []))
        frames.update(source_profile.get("observed_frame_indices", []))
        target_profile["observed_frame_indices"] = sorted(list(frames))

        # Gộp embedding
        for emb in source_profile.get("embeddings", []):
            self._append_embedding(target_profile, emb)

        # Giữ ảnh đại diện tốt hơn
        source_conf = source_profile.get("best_face_confidence", 0.0) or 0.0
        target_conf = target_profile.get("best_face_confidence", 0.0) or 0.0

        if source_conf > target_conf:
            target_profile["best_face_image_path"] = source_profile.get("best_face_image_path")
            target_profile["best_face_confidence"] = source_conf
            target_profile["primary_embedding"] = source_profile.get("primary_embedding")

    def _normalize(self, vec: np.ndarray) -> Optional[np.ndarray]:
        norm = np.linalg.norm(vec)
        if norm == 0:
            return None
        return vec / norm

    def _cosine_similarity(self, vecA: np.ndarray, vecB: np.ndarray) -> float:
        return float(np.dot(vecA, vecB))
    
    def _has_frame_overlap(self, frames_a: List[int], frames_b: List[int]) -> bool:
        if not frames_a or not frames_b:
            return False

        return len(set(frames_a).intersection(set(frames_b))) > 0


face_matcher = FaceMatchingService(
    strict_threshold=0.42,
    soft_threshold=0.36,
    min_margin=0.05,
    max_embeddings_per_profile=5,
    weak_fragment_max_observations=12,
    weak_fragment_threshold=0.30,
)