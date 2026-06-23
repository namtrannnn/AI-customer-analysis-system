import numpy as np
from typing import Dict, List, Optional, Tuple


class OnlineIdentityService:
    """
    Online Face Re-ID / Online Identity Assignment

    Tracker sinh track_id tạm.
    Service này map:
        track_id -> profile_id

    Không sửa track_id của tracker.
    """

    def __init__(
        self,
        strict_threshold: float = 0.42,
        soft_threshold: float = 0.36,
        weak_track_threshold: float = 0.30,
        max_embeddings_per_profile: int = 5,
        max_appearance_per_profile: int = 5,
    ) -> None:
        self.strict_threshold = strict_threshold
        self.soft_threshold = soft_threshold
        self.weak_track_threshold = weak_track_threshold
        self.max_embeddings_per_profile = max_embeddings_per_profile
        self.max_appearance_per_profile = max_appearance_per_profile

        self.track_to_profile: Dict[int, str] = {}
        self.profiles: Dict[str, Dict] = {}
        self.next_profile_index: int = 1

    def reset(self) -> None:
        self.track_to_profile = {}
        self.profiles = {}
        self.next_profile_index = 1

    def find_best_profile(
        self,
        embedding: List[float],
        appearance_signature=None,
        current_frame_index: Optional[int] = None,
        current_track_frames: Optional[List[int]] = None,
        current_track_frame_bboxes: Optional[Dict[int, List[float]]] = None,
        appearance_service=None,
    ) -> Tuple[Optional[str], float, float, float, float]:
        """
        Trả về:
            best_profile_id,
            best_total_score,
            best_face_score,
            best_app_score,
            best_margin

        Có same-frame guard thông minh:
        - Cùng frame nhưng bbox không trùng nhau -> chắc chắn khác người -> skip.
        - Cùng frame nhưng bbox trùng cao -> có thể là duplicate detection -> vẫn cho so.
        """

        print(
            f"[FindBestProfile] called | "
            f"profile_count={len(self.profiles)} | "
            f"current_frame={current_frame_index} | "
            f"current_track_frames={current_track_frames}"
        )

        current_vec = self._normalize(np.array(embedding, dtype=np.float32))

        if current_vec is None:
            print("[FindBestProfile] return early: current_vec is None")
            return None, -1.0, -1.0, 0.0, -1.0

        candidates = []

        for profile_id, profile in self.profiles.items():
            print(
                f"[FindBestProfile] checking {profile_id} | "
                f"track_ids={profile.get('track_ids', [])} | "
                f"app_count={len(profile.get('appearance_signatures', []))} | "
                f"emb_count={len(profile.get('embeddings', []))}"
            )

            if self._has_conflicting_same_frame(
                current_track_frame_bboxes=current_track_frame_bboxes or {},
                profile_frame_bboxes=profile.get("frame_bboxes", {}),
            ):
                print(f"[FindBestProfile] skip {profile_id}: same-frame different bbox")
                continue

            face_score = self._max_face_similarity(
                embedding=embedding,
                profile=profile,
            )

            app_score = 0.0

            if appearance_signature and appearance_service:
                app_scores = []

                for known_sig in profile.get("appearance_signatures", []):
                    score = appearance_service.compare(
                        appearance_signature,
                        known_sig,
                    )
                    app_scores.append(score)

                if app_scores:
                    app_score = max(app_scores)
            else:
                print(
                    f"[FindBestProfile] app disabled for {profile_id} | "
                    f"appearance_signature={appearance_signature is not None} | "
                    f"appearance_service={appearance_service is not None}"
                )

            total_score = self._combine_scores(face_score, app_score)

            print(
                f"[Compare] current vs {profile_id}: "
                f"total={total_score:.3f}, "
                f"face={face_score:.3f}, "
                f"app={app_score:.3f}, "
                f"profile_app_count={len(profile.get('appearance_signatures', []))}"
            )

            candidates.append({
                "profile_id": profile_id,
                "total": total_score,
                "face": face_score,
                "app": app_score,
            })

        if not candidates:
            print(
                f"[FindBestProfile] result | "
                f"best_profile_id=None | total=-1.000 | "
                f"face=-1.000 | app=0.000 | margin=-1.000"
            )
            return None, -1.0, -1.0, 0.0, -1.0

        candidates.sort(key=lambda x: x["total"], reverse=True)

        best = candidates[0]
        second = candidates[1] if len(candidates) > 1 else None

        margin = best["total"] - second["total"] if second else 1.0

        print(
            f"[FindBestProfile] result | "
            f"best_profile_id={best['profile_id']} | "
            f"total={best['total']:.3f} | "
            f"face={best['face']:.3f} | "
            f"app={best['app']:.3f} | "
            f"margin={margin:.3f}"
        )

        return (
            best["profile_id"],
            float(best["total"]),
            float(best["face"]),
            float(best["app"]),
            float(margin),
        )

    def create_new_profile(
        self,
        track_id: int,
        embedding: List[float],
        face_image_path: str,
        face_confidence: float,
        frame_index: int,
        observation_count: int,
        observed_frame_indices: Optional[List[int]] = None,
        appearance_signature=None,
        bbox: Optional[List[float]] = None,
    ) -> str:
        if isinstance(self.next_profile_index, tuple):
            self.next_profile_index = self.next_profile_index[0]

        profile_id = f"P_{self.next_profile_index:04d}"
        self.next_profile_index += 1

        self.track_to_profile[track_id] = profile_id

        frames = observed_frame_indices if observed_frame_indices else [frame_index]

        frame_bboxes = {}

        if bbox is not None:
            for f in frames:
                frame_bboxes[int(f)] = bbox

        self.profiles[profile_id] = {
            "profile_id": profile_id,
            "track_ids": [track_id],
            "embeddings": [embedding],
            "appearance_signatures": [appearance_signature] if appearance_signature else [],
            "best_face_image_path": face_image_path,
            "best_face_confidence": face_confidence,
            "total_observations": observation_count,
            "observed_frame_indices": sorted(list(set(frames))),
            "frame_bboxes": frame_bboxes,
            "match_scores": [],
        }

        return profile_id

    def update_profile(
        self,
        profile_id: str,
        track_id: int,
        embedding: List[float],
        face_image_path: str,
        face_confidence: float,
        frame_index: int,
        observation_count: int,
        observed_frame_indices: Optional[List[int]] = None,
        appearance_signature=None,
        bbox: Optional[List[float]] = None,
        match_score: Optional[float] = None,
    ) -> None:
        profile = self.profiles[profile_id]

        if track_id not in profile["track_ids"]:
            profile["track_ids"].append(track_id)

        profile["total_observations"] += observation_count

        frames = set(profile.get("observed_frame_indices", []))
        frames.add(frame_index)

        if observed_frame_indices:
            frames.update(observed_frame_indices)

        profile["observed_frame_indices"] = sorted(list(frames))

        if bbox is not None:
            frame_bboxes = profile.setdefault("frame_bboxes", {})

            if observed_frame_indices:
                for f in observed_frame_indices:
                    frame_bboxes[int(f)] = bbox
            else:
                frame_bboxes[int(frame_index)] = bbox

        self._append_embedding(profile, embedding)

        if appearance_signature:
            self._append_appearance_signature(profile, appearance_signature)

        if match_score is not None:
            profile.setdefault("match_scores", []).append(round(float(match_score), 4))

        if face_confidence > profile.get("best_face_confidence", 0.0):
            profile["best_face_image_path"] = face_image_path
            profile["best_face_confidence"] = face_confidence

    def export_profiles(self) -> List[Dict]:
        return list(self.profiles.values())

    def _combine_scores(self, face_score: float, app_score: float) -> float:
        """
        Face vẫn là chính.
        Appearance chỉ hỗ trợ khi face score chưa đủ chắc.
        """

        if face_score < 0:
            return -1.0

        if face_score >= self.strict_threshold:
            # Vùng mạnh: gần như face quyết định, appearance hỗ trợ nhẹ.
            return float(face_score * 0.90 + app_score * 0.10)

        if self.soft_threshold <= face_score < self.strict_threshold:
            # Vùng lưng chừng: appearance có vai trò rõ hơn.
            return float(face_score * 0.75 + app_score * 0.25)

        # Vùng yếu: appearance chỉ hỗ trợ nhẹ, không được cứu quá mạnh.
        return float(face_score * 0.85 + app_score * 0.15)

    def _max_face_similarity(self, embedding: List[float], profile: Dict) -> float:
        current_vec = self._normalize(np.array(embedding, dtype=np.float32))

        if current_vec is None:
            return -1.0

        best_score = -1.0

        for known_embedding in profile.get("embeddings", []):
            known_vec = self._normalize(np.array(known_embedding, dtype=np.float32))

            if known_vec is None:
                continue

            score = self._cosine_similarity(current_vec, known_vec)

            if score > best_score:
                best_score = score

        return float(best_score)

    def _append_embedding(self, profile: Dict, embedding: List[float]) -> None:
        if not embedding:
            return

        embeddings = profile.setdefault("embeddings", [])

        new_vec = self._normalize(np.array(embedding, dtype=np.float32))

        if new_vec is None:
            return

        for old_embedding in embeddings:
            old_vec = self._normalize(np.array(old_embedding, dtype=np.float32))

            if old_vec is None:
                continue

            score = self._cosine_similarity(new_vec, old_vec)

            # Embedding gần như trùng thì không lưu thêm.
            if score >= 0.97:
                return

        embeddings.append(embedding)

        if len(embeddings) > self.max_embeddings_per_profile:
            first_embedding = embeddings[0]
            recent_embeddings = embeddings[-(self.max_embeddings_per_profile - 1):]
            profile["embeddings"] = [first_embedding] + recent_embeddings

    def _append_appearance_signature(self, profile: Dict, appearance_signature: Dict) -> None:
        if not appearance_signature:
            return

        signatures = profile.setdefault("appearance_signatures", [])
        signatures.append(appearance_signature)

        if len(signatures) > self.max_appearance_per_profile:
            profile["appearance_signatures"] = signatures[-self.max_appearance_per_profile:]

    def _has_conflicting_same_frame(
        self,
        current_track_frame_bboxes: Dict[int, List[float]],
        profile_frame_bboxes: Dict[int, List[float]],
    ) -> bool:
        """
        Same-frame guard thông minh.

        Nếu cùng frame:
        - IoU thấp: hai bbox khác vị trí -> chắc chắn khác người -> skip.
        - IoU cao: có thể là duplicate ID cùng người -> không skip.
        """

        if not current_track_frame_bboxes or not profile_frame_bboxes:
            return False

        overlap_frames = set(current_track_frame_bboxes.keys()).intersection(
            set(profile_frame_bboxes.keys())
        )

        if not overlap_frames:
            return False

        for f in overlap_frames:
            current_bbox = current_track_frame_bboxes.get(f)
            profile_bbox = profile_frame_bboxes.get(f)

            if current_bbox is None or profile_bbox is None:
                continue

            iou = self._bbox_iou(current_bbox, profile_bbox)

            # Cùng frame nhưng bbox gần như không trùng nhau:
            # đây là hai người khác nhau.
            if iou < 0.15:
                return True

            # Cùng frame và bbox trùng cao:
            # có thể là duplicate detection của cùng người.
            if iou >= 0.45:
                return False

            # Vùng mơ hồ thì chọn an toàn: coi là khác người.
            return True

        return False

    def _bbox_iou(self, box_a: List[float], box_b: List[float]) -> float:
        ax1, ay1, ax2, ay2 = [float(v) for v in box_a]
        bx1, by1, bx2, by2 = [float(v) for v in box_b]

        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)

        inter_w = max(0.0, inter_x2 - inter_x1)
        inter_h = max(0.0, inter_y2 - inter_y1)

        inter_area = inter_w * inter_h

        area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
        area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)

        union = area_a + area_b - inter_area

        if union <= 0:
            return 0.0

        return float(inter_area / union)

    def _normalize(self, vec: np.ndarray) -> Optional[np.ndarray]:
        norm = np.linalg.norm(vec)

        if norm == 0:
            return None

        return vec / norm

    def _cosine_similarity(self, vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        return float(np.dot(vec_a, vec_b))