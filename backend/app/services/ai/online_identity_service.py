import numpy as np
from typing import Dict, List, Optional, Tuple


class OnlineIdentityService:
    """
    Online Face Re-ID / Online Identity Assignment

    Tracker sinh track_id tạm. Service này map track_id -> profile_id.

    Điểm quan trọng của bản này:
    - Không chỉ lấy 1 best profile theo face/appearance.
    - Trả về ranked candidates để pipeline có thể xét theo thứ tự.
    - Lưu temporal-spatial state cho mỗi profile: first/last frame + bbox.
    - Có tín hiệu stale/re-entry để tránh case một người mới đi vào cùng vị trí
      sau vài phút bị gán nhầm vào profile đã rời khỏi khung hình.
    - Lưu contribution theo từng track để có thể chuyển riêng track bị gán nhầm
      sang profile đúng, thay vì merge nguyên profile sai ở cuối video.
    """

    def __init__(
        self,
        strict_threshold: float = 0.42,
        soft_threshold: float = 0.36,
        weak_track_threshold: float = 0.30,
        max_embeddings_per_profile: int = 5,
        max_appearance_per_profile: int = 5,
        stale_profile_frames: int = 45,
        entry_reuse_distance_norm: float = 0.18,
        return_distance_norm: float = 0.28,
        stale_strong_face: float = 0.55,
        stale_strong_total: float = 0.52,
        stale_strong_margin: float = 0.08,
        entry_reuse_min_gap_frames: int = 3,
        entry_reuse_strong_face: float = 0.62,
        entry_reuse_strong_margin: float = 0.10,
    ) -> None:
        self.strict_threshold = strict_threshold
        self.soft_threshold = soft_threshold
        self.weak_track_threshold = weak_track_threshold
        self.max_embeddings_per_profile = max_embeddings_per_profile
        self.max_appearance_per_profile = max_appearance_per_profile

        self.stale_profile_frames = int(max(1, stale_profile_frames))
        self.entry_reuse_distance_norm = float(entry_reuse_distance_norm)
        self.return_distance_norm = float(return_distance_norm)
        self.stale_strong_face = float(stale_strong_face)
        self.stale_strong_total = float(stale_strong_total)
        self.stale_strong_margin = float(stale_strong_margin)
        self.entry_reuse_min_gap_frames = int(max(1, entry_reuse_min_gap_frames))
        self.entry_reuse_strong_face = float(entry_reuse_strong_face)
        self.entry_reuse_strong_margin = float(entry_reuse_strong_margin)

        self.track_to_profile: Dict[int, str] = {}
        self.profiles: Dict[str, Dict] = {}
        self.next_profile_index: int = 1
        print("ONLINE_IDENTITY_VERSION = true_delayed_realtime_v1_debug_lite")
        # Giảm log: find_ranked_candidates không in mỗi Compare nữa.
        # Pipeline sẽ chỉ in các event nghi vấn/decision quan trọng.
        self.debug_ranked_candidates = False

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
        frame_shape: Optional[Tuple[int, int]] = None,
    ) -> Tuple[Optional[str], float, float, float, float]:
        """
        Backward-compatible API. Ưu tiên dùng find_ranked_candidates() trong pipeline mới.
        """
        candidates = self.find_ranked_candidates(
            embedding=embedding,
            appearance_signature=appearance_signature,
            current_frame_index=current_frame_index,
            current_track_frames=current_track_frames,
            current_track_frame_bboxes=current_track_frame_bboxes,
            appearance_service=appearance_service,
            frame_shape=frame_shape,
        )

        if not candidates:
            return None, -1.0, -1.0, 0.0, -1.0

        best = candidates[0]
        return (
            best["profile_id"],
            float(best["total"]),
            float(best["face"]),
            float(best["app"]),
            float(best["margin"]),
        )

    def find_ranked_candidates(
        self,
        embedding: List[float],
        appearance_signature=None,
        current_frame_index: Optional[int] = None,
        current_track_frames: Optional[List[int]] = None,
        current_track_frame_bboxes: Optional[Dict[int, List[float]]] = None,
        appearance_service=None,
        frame_shape: Optional[Tuple[int, int]] = None,
    ) -> List[Dict]:
        """
        Trả về danh sách ứng viên đã sort giảm dần theo total score.

        Mỗi candidate có thêm temporal-spatial metadata:
        - gap_frames: track mới bắt đầu sau profile cũ bao nhiêu frame.
        - is_stale: profile đã vắng mặt đủ lâu.
        - start_last_distance_norm: khoảng cách từ điểm bắt đầu track hiện tại tới điểm cuối profile.
        - start_entry_distance_norm: khoảng cách từ điểm bắt đầu track hiện tại tới điểm đầu profile.
        - starts_near_profile_entry: người mới xuất hiện gần điểm mà profile cũ từng bắt đầu.
        - return_location_plausible: người mới xuất hiện gần điểm mà profile cũ rời đi.
        - temporal_spatial_risk: lý do rủi ro nếu có.
        """
        if getattr(self, "debug_ranked_candidates", False):
            print(
                f"[FindRankedCandidates] called | "
                f"profile_count={len(self.profiles)} | "
                f"current_frame={current_frame_index} | "
                f"current_track_frames={current_track_frames}"
            )

        current_vec = self._normalize(np.array(embedding, dtype=np.float32))
        if current_vec is None:
            return []

        current_track_frame_bboxes = current_track_frame_bboxes or {}
        current_track_frames = sorted(current_track_frames or current_track_frame_bboxes.keys())

        candidates = []

        for profile_id, profile in self.profiles.items():
            if self._has_conflicting_same_frame(
                current_track_frame_bboxes=current_track_frame_bboxes,
                profile_frame_bboxes=profile.get("frame_bboxes", {}),
            ):
                if getattr(self, "debug_ranked_candidates", False):
                    print(f"[FindRankedCandidates] skip {profile_id}: same-frame different bbox")
                continue

            face_score = self._max_face_similarity(embedding=embedding, profile=profile)
            app_score = 0.0

            if appearance_signature and appearance_service:
                app_scores = []
                for known_sig in profile.get("appearance_signatures", []):
                    app_scores.append(appearance_service.compare(appearance_signature, known_sig))
                if app_scores:
                    app_score = max(app_scores)

            total_score = self._combine_scores(face_score, app_score)
            spatial = self._build_temporal_spatial_features(
                profile=profile,
                current_frame_index=current_frame_index,
                current_track_frames=current_track_frames,
                current_track_frame_bboxes=current_track_frame_bboxes,
                frame_shape=frame_shape,
            )

            candidate = {
                "profile_id": profile_id,
                "total": float(total_score),
                "face": float(face_score),
                "app": float(app_score),
                "margin": 1.0,
                **spatial,
            }
            candidates.append(candidate)

            if getattr(self, "debug_ranked_candidates", False):
                print(
                    f"[Compare] current vs {profile_id}: "
                    f"total={total_score:.3f}, face={face_score:.3f}, app={app_score:.3f}, "
                    f"gap={candidate.get('gap_frames')}, stale={candidate.get('is_stale')}, "
                    f"spatial_risk={candidate.get('temporal_spatial_risk')}"
                )

        if not candidates:
            return []

        candidates.sort(key=lambda x: x["total"], reverse=True)

        for idx, candidate in enumerate(candidates):
            if idx + 1 < len(candidates):
                candidate["margin"] = float(candidate["total"] - candidates[idx + 1]["total"])
            else:
                candidate["margin"] = 1.0

        best = candidates[0]
        if getattr(self, "debug_ranked_candidates", False):
            print(
                f"[FindRankedCandidates] best={best['profile_id']} | "
                f"total={best['total']:.3f} | face={best['face']:.3f} | "
                f"app={best['app']:.3f} | margin={best['margin']:.3f} | "
                f"risk={best.get('temporal_spatial_risk')}"
            )
        return candidates

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

        frames = sorted(list(set(observed_frame_indices if observed_frame_indices else [frame_index])))
        frame_bboxes = {}
        if bbox is not None:
            for f in frames:
                frame_bboxes[int(f)] = bbox

        first_frame = min(frames) if frames else int(frame_index)
        last_frame = max(frames) if frames else int(frame_index)

        self.profiles[profile_id] = {
            "profile_id": profile_id,
            "track_ids": [track_id],
            "embeddings": [embedding],
            "appearance_signatures": [appearance_signature] if appearance_signature else [],
            "best_face_image_path": face_image_path,
            "best_face_confidence": face_confidence,
            "total_observations": observation_count,
            "observed_frame_indices": frames,
            "frame_bboxes": frame_bboxes,
            "first_frame_index": first_frame,
            "last_frame_index": last_frame,
            "first_bbox": self._bbox_for_frame(frame_bboxes, first_frame) or bbox,
            "last_bbox": self._bbox_for_frame(frame_bboxes, last_frame) or bbox,
            "match_scores": [],
            "track_samples": {
                str(track_id): {
                    "track_id": track_id,
                    "embeddings": [embedding] if embedding else [],
                    "appearance_signatures": [appearance_signature] if appearance_signature else [],
                    "best_face_image_path": face_image_path,
                    "best_face_confidence": float(face_confidence or 0.0),
                    "total_observations": int(observation_count or 0),
                    "observed_frame_indices": frames,
                    "frame_bboxes": dict(frame_bboxes),
                    "match_scores": [],
                }
            },
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
        frames.add(int(frame_index))
        if observed_frame_indices:
            frames.update(int(f) for f in observed_frame_indices)
        profile["observed_frame_indices"] = sorted(list(frames))

        if bbox is not None:
            frame_bboxes = profile.setdefault("frame_bboxes", {})
            if observed_frame_indices:
                for f in observed_frame_indices:
                    frame_bboxes[int(f)] = bbox
            else:
                frame_bboxes[int(frame_index)] = bbox

        self._upsert_track_sample(
            profile=profile,
            track_id=track_id,
            embedding=embedding,
            face_image_path=face_image_path,
            face_confidence=face_confidence,
            frame_index=frame_index,
            observation_count=observation_count,
            observed_frame_indices=observed_frame_indices,
            appearance_signature=appearance_signature,
            bbox=bbox,
            match_score=match_score,
        )

        self._refresh_profile_temporal_spatial_state(profile)
        self._append_embedding(profile, embedding)

        if appearance_signature:
            self._append_appearance_signature(profile, appearance_signature)

        if match_score is not None:
            profile.setdefault("match_scores", []).append(round(float(match_score), 4))

        if face_confidence > profile.get("best_face_confidence", 0.0):
            profile["best_face_image_path"] = face_image_path
            profile["best_face_confidence"] = face_confidence


    def update_profile_spatial_observation(
        self,
        profile_id: str,
        track_id: int,
        frame_index: int,
        bbox: Optional[List[float]] = None,
        observed_frame_indices: Optional[List[int]] = None,
    ) -> None:
        """
        Cập nhật vị trí/thời gian xuất hiện của profile ở mọi frame tracking,
        kể cả frame không sample face.

        Nếu không làm bước này, profile_last_bbox dễ bị kẹt ở lần detect face gần nhất
        thay vì điểm rời khỏi khung hình thật. Khi đó người mới đi vào cùng vị trí
        có thể bị coi nhầm là return candidate.
        """
        profile = self.profiles.get(profile_id)
        if profile is None:
            return

        if track_id not in profile.setdefault("track_ids", []):
            profile["track_ids"].append(track_id)

        frames = set(int(f) for f in profile.get("observed_frame_indices", []))
        frames.add(int(frame_index))
        if observed_frame_indices:
            frames.update(int(f) for f in observed_frame_indices)
        profile["observed_frame_indices"] = sorted(list(frames))

        if bbox is not None:
            frame_bboxes = profile.setdefault("frame_bboxes", {})
            frame_bboxes[int(frame_index)] = bbox
            if observed_frame_indices:
                for f in observed_frame_indices:
                    frame_bboxes[int(f)] = bbox

        self._upsert_track_spatial_sample(
            profile=profile,
            track_id=track_id,
            frame_index=frame_index,
            bbox=bbox,
            observed_frame_indices=observed_frame_indices,
        )

        self._refresh_profile_temporal_spatial_state(profile)

    def split_track_to_new_profile(
        self,
        track_id: int,
        source_profile_id: str,
    ) -> Optional[str]:
        """
        Tách riêng contribution của một track trong profile hiện tại thành profile mới.
        Dùng khi body/clothes cho thấy track đó là người khác nhưng đã bị match nhầm
        vào profile cũ, ví dụ người áo đỏ bị kéo vào P006 áo trắng.
        """
        source = self.profiles.get(source_profile_id)
        if source is None:
            return None

        key = str(track_id)
        source_samples = source.setdefault("track_samples", {})
        sample = source_samples.pop(key, None)
        if sample is None:
            return None

        if isinstance(self.next_profile_index, tuple):
            self.next_profile_index = self.next_profile_index[0]

        new_profile_id = f"P_{self.next_profile_index:04d}"
        self.next_profile_index += 1

        frames = sorted(list(set(int(f) for f in sample.get("observed_frame_indices", []))))
        frame_bboxes = dict(sample.get("frame_bboxes", {}) or {})
        first_frame = min(frames) if frames else None
        last_frame = max(frames) if frames else None

        self.profiles[new_profile_id] = {
            "profile_id": new_profile_id,
            "track_ids": [int(track_id)],
            "embeddings": list(sample.get("embeddings", []) or []),
            "appearance_signatures": list(sample.get("appearance_signatures", []) or [])[-self.max_appearance_per_profile:],
            "best_face_image_path": sample.get("best_face_image_path"),
            "best_face_confidence": float(sample.get("best_face_confidence", 0.0) or 0.0),
            "total_observations": int(sample.get("total_observations", 0) or 0),
            "observed_frame_indices": frames,
            "frame_bboxes": frame_bboxes,
            "first_frame_index": first_frame,
            "last_frame_index": last_frame,
            "first_bbox": self._bbox_for_frame(frame_bboxes, first_frame) if first_frame is not None else None,
            "last_bbox": self._bbox_for_frame(frame_bboxes, last_frame) if last_frame is not None else None,
            "match_scores": list(sample.get("match_scores", []) or []),
            "track_samples": {key: sample},
        }

        self.track_to_profile[int(track_id)] = new_profile_id
        self._rebuild_profile_from_track_samples(source)
        self._refresh_profile_temporal_spatial_state(self.profiles[new_profile_id])

        if not source.get("track_ids"):
            self.profiles.pop(source_profile_id, None)

        return new_profile_id

    def reassign_track_to_profile(
        self,
        track_id: int,
        source_profile_id: str,
        target_profile_id: str,
    ) -> bool:
        """
        Chuyển RIÊNG contribution của một track từ profile sai sang profile đúng.

        Lý do cần hàm này:
        - Nếu track56 của P004 bị gán nhầm vào P006, cuối video không được merge
          nguyên P006 -> P004 vì như vậy kéo cả người P006 thật vào P004.
        - Thay vào đó, khi online evidence đủ mạnh, chỉ move track56 sang P004.
        """
        if source_profile_id == target_profile_id:
            return False

        source = self.profiles.get(source_profile_id)
        target = self.profiles.get(target_profile_id)
        if source is None or target is None:
            return False

        key = str(track_id)
        source_samples = source.setdefault("track_samples", {})
        sample = source_samples.pop(key, None)
        if sample is None:
            # Fallback: vẫn đổi mapping để các frame sau đi đúng, nhưng không rebuild được lịch sử.
            if track_id in source.get("track_ids", []):
                source["track_ids"] = [t for t in source.get("track_ids", []) if t != track_id]
            self.track_to_profile[track_id] = target_profile_id
            return True

        target.setdefault("track_samples", {})[key] = sample
        self.track_to_profile[track_id] = target_profile_id

        self._rebuild_profile_from_track_samples(source)
        self._rebuild_profile_from_track_samples(target)

        if not source.get("track_ids"):
            self.profiles.pop(source_profile_id, None)

        return True

    def _upsert_track_sample(
        self,
        profile: Dict,
        track_id: int,
        embedding: Optional[List[float]],
        face_image_path: Optional[str],
        face_confidence: Optional[float],
        frame_index: int,
        observation_count: int,
        observed_frame_indices: Optional[List[int]],
        appearance_signature=None,
        bbox: Optional[List[float]] = None,
        match_score: Optional[float] = None,
    ) -> None:
        samples = profile.setdefault("track_samples", {})
        key = str(track_id)
        frames = sorted(list(set(int(f) for f in (observed_frame_indices or [frame_index]))))
        frame_bboxes = {}
        if bbox is not None:
            for f in frames:
                frame_bboxes[int(f)] = bbox

        sample = samples.setdefault(key, {
            "track_id": track_id,
            "embeddings": [],
            "appearance_signatures": [],
            "best_face_image_path": None,
            "best_face_confidence": 0.0,
            "total_observations": 0,
            "observed_frame_indices": [],
            "frame_bboxes": {},
            "match_scores": [],
        })

        if embedding:
            self._append_embedding(sample, embedding)
        if appearance_signature:
            self._append_appearance_signature(sample, appearance_signature)

        sample["total_observations"] = int(sample.get("total_observations", 0)) + int(observation_count or 0)

        old_frames = set(int(f) for f in sample.get("observed_frame_indices", []))
        old_frames.update(frames)
        sample["observed_frame_indices"] = sorted(list(old_frames))

        sample_frame_bboxes = sample.setdefault("frame_bboxes", {})
        sample_frame_bboxes.update(frame_bboxes)

        if match_score is not None:
            sample.setdefault("match_scores", []).append(round(float(match_score), 4))

        conf = float(face_confidence or 0.0)
        if conf > float(sample.get("best_face_confidence", 0.0)):
            sample["best_face_confidence"] = conf
            sample["best_face_image_path"] = face_image_path

    def _upsert_track_spatial_sample(
        self,
        profile: Dict,
        track_id: int,
        frame_index: int,
        bbox: Optional[List[float]],
        observed_frame_indices: Optional[List[int]] = None,
    ) -> None:
        samples = profile.setdefault("track_samples", {})
        key = str(track_id)
        sample = samples.setdefault(key, {
            "track_id": track_id,
            "embeddings": [],
            "appearance_signatures": [],
            "best_face_image_path": None,
            "best_face_confidence": 0.0,
            "total_observations": 0,
            "observed_frame_indices": [],
            "frame_bboxes": {},
            "match_scores": [],
        })

        frames = set(int(f) for f in sample.get("observed_frame_indices", []))
        frames.add(int(frame_index))
        if observed_frame_indices:
            frames.update(int(f) for f in observed_frame_indices)
        sample["observed_frame_indices"] = sorted(list(frames))

        if bbox is not None:
            frame_bboxes = sample.setdefault("frame_bboxes", {})
            frame_bboxes[int(frame_index)] = bbox
            if observed_frame_indices:
                for f in observed_frame_indices:
                    frame_bboxes[int(f)] = bbox

    def _rebuild_profile_from_track_samples(self, profile: Dict) -> None:
        samples = profile.get("track_samples", {}) or {}
        if not samples:
            profile["track_ids"] = []
            profile["embeddings"] = []
            profile["appearance_signatures"] = []
            profile["total_observations"] = 0
            profile["observed_frame_indices"] = []
            profile["frame_bboxes"] = {}
            profile["best_face_confidence"] = 0.0
            profile["best_face_image_path"] = None
            profile["match_scores"] = []
            return

        track_ids = []
        embeddings = []
        app_sigs = []
        total_observations = 0
        frames = set()
        frame_bboxes = {}
        match_scores = []
        best_face_conf = -1.0
        best_face_path = None

        for key, sample in samples.items():
            tid = int(sample.get("track_id", key))
            track_ids.append(tid)
            total_observations += int(sample.get("total_observations", 0))

            embeddings.extend(sample.get("embeddings", []))
            app_sigs.extend(sample.get("appearance_signatures", []))
            match_scores.extend(sample.get("match_scores", []))

            for f in sample.get("observed_frame_indices", []):
                frames.add(int(f))

            for f, b in sample.get("frame_bboxes", {}).items():
                try:
                    frame_bboxes[int(f)] = b
                except Exception:
                    frame_bboxes[f] = b

            conf = float(sample.get("best_face_confidence", 0.0))
            if conf > best_face_conf:
                best_face_conf = conf
                best_face_path = sample.get("best_face_image_path")

        profile["track_ids"] = sorted(list(set(track_ids)))
        profile["embeddings"] = embeddings[-self.max_embeddings_per_profile:]
        profile["appearance_signatures"] = app_sigs[-self.max_appearance_per_profile:]
        profile["total_observations"] = total_observations
        profile["observed_frame_indices"] = sorted(list(frames))
        profile["frame_bboxes"] = frame_bboxes
        profile["best_face_confidence"] = max(0.0, best_face_conf)
        profile["best_face_image_path"] = best_face_path
        profile["match_scores"] = match_scores
        self._refresh_profile_temporal_spatial_state(profile)

    def export_profiles(self) -> List[Dict]:
        exported = []
        for profile in list(self.profiles.values()):
            self._refresh_profile_temporal_spatial_state(profile)
            if profile.get("track_ids"):
                exported.append(profile)
        return exported

    def _combine_scores(self, face_score: float, app_score: float) -> float:
        """
        Face vẫn là chính. Appearance chỉ hỗ trợ, không được cứu một face quá yếu.
        """
        if face_score < 0:
            return -1.0
        if face_score >= self.strict_threshold:
            return float(face_score * 0.90 + app_score * 0.10)
        if self.soft_threshold <= face_score < self.strict_threshold:
            return float(face_score * 0.78 + app_score * 0.22)
        return float(face_score * 0.90 + app_score * 0.10)

    def _build_temporal_spatial_features(
        self,
        profile: Dict,
        current_frame_index: Optional[int],
        current_track_frames: List[int],
        current_track_frame_bboxes: Dict[int, List[float]],
        frame_shape: Optional[Tuple[int, int]],
    ) -> Dict:
        self._refresh_profile_temporal_spatial_state(profile)

        if current_track_frames:
            current_start_frame = min(current_track_frames)
            current_last_frame = max(current_track_frames)
        else:
            current_start_frame = int(current_frame_index or 0)
            current_last_frame = int(current_frame_index or 0)

        current_start_bbox = self._bbox_for_frame(current_track_frame_bboxes, current_start_frame)
        current_last_bbox = self._bbox_for_frame(current_track_frame_bboxes, current_last_frame)

        profile_first_frame = profile.get("first_frame_index")
        profile_last_frame = profile.get("last_frame_index")
        profile_first_bbox = profile.get("first_bbox")
        profile_last_bbox = profile.get("last_bbox")

        gap_frames = None
        is_stale = False
        if profile_last_frame is not None:
            gap_frames = int(current_start_frame) - int(profile_last_frame)
            is_stale = gap_frames >= self.stale_profile_frames

        start_last_distance_norm = self._bbox_center_distance_norm(
            current_start_bbox,
            profile_last_bbox,
            frame_shape,
        )
        start_entry_distance_norm = self._bbox_center_distance_norm(
            current_start_bbox,
            profile_first_bbox,
            frame_shape,
        )
        current_last_to_profile_last_distance_norm = self._bbox_center_distance_norm(
            current_last_bbox,
            profile_last_bbox,
            frame_shape,
        )

        starts_near_profile_entry = (
            start_entry_distance_norm is not None
            and start_entry_distance_norm <= self.entry_reuse_distance_norm
        )
        return_location_plausible = (
            start_last_distance_norm is not None
            and start_last_distance_norm <= self.return_distance_norm
        )

        # Đây là phần quan trọng để xử lý video generic:
        # Nếu profile A từng bắt đầu ở cửa/vùng vào X rồi đã rời khỏi frame,
        # một track mới cũng bắt đầu ở X KHÔNG phải là bằng chứng cùng người.
        # Ngược lại, đây là rủi ro reuse entry position.
        #
        # Bản trước chỉ coi là entry-reuse khi điểm bắt đầu mới KHÔNG gần điểm
        # rời đi cũ. Điều này vẫn hở case P006: nếu P006 bắt đầu và kết thúc
        # quanh cùng một vùng, người mới đi vào vùng đó sẽ bị xem như
        # "return_location_plausible". Vì vậy chỉ cần profile đã vắng mặt và
        # current track bắt đầu gần first_bbox cũ thì phải đánh dấu rủi ro.
        entry_reuse_after_absence = (
            gap_frames is not None
            and gap_frames >= self.entry_reuse_min_gap_frames
            and starts_near_profile_entry
        )

        entry_reuse_is_also_return_location = bool(
            entry_reuse_after_absence and return_location_plausible
        )

        temporal_spatial_risk = None
        if gap_frames is not None and gap_frames < 0:
            temporal_spatial_risk = "profile_overlaps_future_track"
        elif entry_reuse_after_absence and is_stale:
            temporal_spatial_risk = "stale_entry_reuse"
        elif entry_reuse_after_absence:
            temporal_spatial_risk = "entry_reuse_after_absence"
        elif is_stale and not return_location_plausible:
            temporal_spatial_risk = "stale_far_from_last_seen"
        elif is_stale:
            temporal_spatial_risk = "stale_return_candidate"

        return {
            "current_start_frame": current_start_frame,
            "current_last_frame": current_last_frame,
            "profile_first_frame": profile_first_frame,
            "profile_last_frame": profile_last_frame,
            "gap_frames": gap_frames,
            "is_stale": bool(is_stale),
            "start_last_distance_norm": start_last_distance_norm,
            "start_entry_distance_norm": start_entry_distance_norm,
            "current_last_to_profile_last_distance_norm": current_last_to_profile_last_distance_norm,
            "starts_near_profile_entry": bool(starts_near_profile_entry),
            "entry_reuse_after_absence": bool(entry_reuse_after_absence),
            "entry_reuse_is_also_return_location": bool(entry_reuse_is_also_return_location),
            "return_location_plausible": bool(return_location_plausible),
            "temporal_spatial_risk": temporal_spatial_risk,
        }

    def is_stale_candidate_strong_enough(self, candidate: Dict) -> bool:
        if not candidate.get("is_stale"):
            return True
        return (
            candidate.get("face", -1.0) >= self.stale_strong_face
            and candidate.get("total", -1.0) >= self.stale_strong_total
            and candidate.get("margin", -1.0) >= self.stale_strong_margin
        )

    def is_entry_reuse_candidate_strong_enough(self, candidate: Dict) -> bool:
        if not candidate.get("entry_reuse_after_absence"):
            return True
        # Với entry reuse, chỉ tin face thật mạnh. Không cho appearance kéo qua.
        return (
            candidate.get("face", -1.0) >= self.entry_reuse_strong_face
            and candidate.get("margin", -1.0) >= self.entry_reuse_strong_margin
        )

    def _refresh_profile_temporal_spatial_state(self, profile: Dict) -> None:
        frames = sorted(profile.get("observed_frame_indices", []))
        if not frames:
            return

        frame_bboxes = profile.get("frame_bboxes", {})
        first_frame = int(min(frames))
        last_frame = int(max(frames))

        profile["first_frame_index"] = first_frame
        profile["last_frame_index"] = last_frame
        profile["first_bbox"] = self._bbox_for_frame(frame_bboxes, first_frame) or profile.get("first_bbox")
        profile["last_bbox"] = self._bbox_for_frame(frame_bboxes, last_frame) or profile.get("last_bbox")

    def _bbox_for_frame(self, frame_bboxes: Dict[int, List[float]], frame_index: int) -> Optional[List[float]]:
        if not frame_bboxes:
            return None
        if frame_index in frame_bboxes:
            return frame_bboxes[frame_index]
        key = str(frame_index)
        if key in frame_bboxes:
            return frame_bboxes[key]
        numeric_keys = []
        for k in frame_bboxes.keys():
            try:
                numeric_keys.append(int(k))
            except Exception:
                continue
        if not numeric_keys:
            return None
        nearest = min(numeric_keys, key=lambda f: abs(f - int(frame_index)))
        return frame_bboxes.get(nearest) or frame_bboxes.get(str(nearest))

    def _bbox_center_distance_norm(
        self,
        box_a: Optional[List[float]],
        box_b: Optional[List[float]],
        frame_shape: Optional[Tuple[int, int]],
    ) -> Optional[float]:
        if box_a is None or box_b is None:
            return None

        ax, ay = self._bbox_center(box_a)
        bx, by = self._bbox_center(box_b)
        dist = float(np.sqrt((ax - bx) ** 2 + (ay - by) ** 2))

        if frame_shape and len(frame_shape) >= 2:
            h, w = float(frame_shape[0]), float(frame_shape[1])
            diag = max(1.0, float(np.sqrt(w * w + h * h)))
        else:
            x_values = [box_a[0], box_a[2], box_b[0], box_b[2]]
            y_values = [box_a[1], box_a[3], box_b[1], box_b[3]]
            diag = max(1.0, float(np.sqrt((max(x_values) - min(x_values)) ** 2 + (max(y_values) - min(y_values)) ** 2)))

        return float(dist / diag)

    def _bbox_center(self, box: List[float]) -> Tuple[float, float]:
        x1, y1, x2, y2 = [float(v) for v in box]
        return (x1 + x2) / 2.0, (y1 + y2) / 2.0

    def _max_face_similarity(self, embedding: List[float], profile: Dict) -> float:
        current_vec = self._normalize(np.array(embedding, dtype=np.float32))
        if current_vec is None:
            return -1.0

        best_score = -1.0
        for known_embedding in profile.get("embeddings", []):
            known_vec = self._normalize(np.array(known_embedding, dtype=np.float32))
            if known_vec is None:
                continue
            best_score = max(best_score, self._cosine_similarity(current_vec, known_vec))
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
            if self._cosine_similarity(new_vec, old_vec) >= 0.97:
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
        if not current_track_frame_bboxes or not profile_frame_bboxes:
            return False

        current_keys = set(int(k) for k in current_track_frame_bboxes.keys())
        profile_keys = set(int(k) for k in profile_frame_bboxes.keys())
        overlap_frames = current_keys.intersection(profile_keys)
        if not overlap_frames:
            return False

        for f in overlap_frames:
            current_bbox = current_track_frame_bboxes.get(f) or current_track_frame_bboxes.get(str(f))
            profile_bbox = profile_frame_bboxes.get(f) or profile_frame_bboxes.get(str(f))
            if current_bbox is None or profile_bbox is None:
                continue

            iou = self._bbox_iou(current_bbox, profile_bbox)
            containment = self._bbox_containment(current_bbox, profile_bbox)
            center_norm = self._bbox_center_distance_norm(current_bbox, profile_bbox)
            area_ratio = self._bbox_area_ratio(current_bbox, profile_bbox)

            duplicate_like = (
                iou >= 0.55
                or containment >= 0.82
                or (center_norm <= 0.075 and 0.60 <= area_ratio <= 1.75 and containment >= 0.45)
            )

            if duplicate_like:
                # Chỉ xem là tracker split nếu bbox thật sự gần như trùng nhau.
                # Không nới rộng ở đây, vì nếu nới sẽ gây lỗi 2 người cùng frame chung personid.
                return False

            # Overlap cùng frame nhưng bbox khác rõ ràng => hai người khác nhau.
            return True
        return False

    def _bbox_containment(self, box_a: List[float], box_b: List[float]) -> float:
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
        small = min(area_a, area_b)
        if small <= 0:
            return 0.0
        return float(inter_area / small)

    def _bbox_center_distance_norm(
        self,
        box_a: Optional[List[float]],
        box_b: Optional[List[float]],
        frame_shape: Optional[Tuple[int, int]] = None,
    ) -> Optional[float]:
        if box_a is None or box_b is None:
            return None

        ax1, ay1, ax2, ay2 = [float(v) for v in box_a]
        bx1, by1, bx2, by2 = [float(v) for v in box_b]
        acx = (ax1 + ax2) / 2.0
        acy = (ay1 + ay2) / 2.0
        bcx = (bx1 + bx2) / 2.0
        bcy = (by1 + by2) / 2.0

        dist = ((acx - bcx) ** 2 + (acy - bcy) ** 2) ** 0.5
        if frame_shape and len(frame_shape) >= 2:
            h, w = float(frame_shape[0]), float(frame_shape[1])
            norm = max(1.0, (w * w + h * h) ** 0.5)
        else:
            aw = max(1.0, ax2 - ax1)
            ah = max(1.0, ay2 - ay1)
            bw = max(1.0, bx2 - bx1)
            bh = max(1.0, by2 - by1)
            norm = max(aw, ah, bw, bh, 1.0)
        return float(dist / norm)

    def _bbox_area_ratio(self, box_a: List[float], box_b: List[float]) -> float:
        ax1, ay1, ax2, ay2 = [float(v) for v in box_a]
        bx1, by1, bx2, by2 = [float(v) for v in box_b]
        area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
        area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
        small = min(area_a, area_b)
        large = max(area_a, area_b)
        if small <= 0:
            return 999.0
        return float(large / small)

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
