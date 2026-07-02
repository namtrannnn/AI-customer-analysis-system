import os
from typing import Dict, List, Optional

import cv2
import numpy as np


class VideoPipelineExportMixin:
    def _build_export_profiles_from_current_mapping(
        self,
        *,
        online_profiles: List[Dict],
        track_to_profile: Dict[int, str],
        track_frame_indices: Dict[int, set],
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
        track_observation_counts: Dict[int, int],
        track_best_face: Dict[int, object],
        track_best_identity_sample: Dict[int, Dict],
        skip_empty_or_tiny_profile: bool,
        min_obs_without_face: int,
    ) -> List[Dict]:
        """
        Rebuild export theo mapping hiện tại để tránh profile rỗng/ghost vẫn xuất hiện.
        """
        profile_by_id = {p.get("profile_id"): p for p in online_profiles if p.get("profile_id")}
        profile_to_tracks: Dict[str, List[int]] = {}
        for tid, pid in track_to_profile.items():
            if pid:
                profile_to_tracks.setdefault(pid, []).append(int(tid))

        merged_profiles = []
        for profile_id, tids in sorted(profile_to_tracks.items()):
            profile = profile_by_id.get(profile_id, {"profile_id": profile_id})
            valid_tids = sorted(set(int(t) for t in tids))
            frames = []
            bboxes = {}
            for tid in valid_tids:
                for fi in sorted(track_frame_indices.get(tid, set())):
                    frames.append(int(fi))
                for fi, bb in (track_frame_bboxes.get(tid, {}) or {}).items():
                    bboxes[int(fi)] = bb
            frames = sorted(set(frames))

            # Rebuild avatar/vector from the *current* mapped tracks, not from stale
            # OnlineIdentity profile metadata. Avatar MUST be track-bound: only a face/sample
            # whose owning track_id is currently in valid_tids can be used.
            profile_embeddings = profile.get("embeddings", []) or []
            best_face_path = None
            best_face_conf = -1.0
            representative_track_id = None

            def _track_last_frame_for_avatar(tid: int) -> int:
                span = self._track_span(track_frame_bboxes, int(tid))
                return int(span[1]) if span is not None else -1

            def _track_obs_for_avatar(tid: int) -> int:
                return int(track_observation_counts.get(int(tid), 0) or 0)

            avatar_candidates = []
            for tid in valid_tids:
                tid = int(tid)
                f = track_best_face.get(tid)
                if f is not None and getattr(f, "face_image_path", None):
                    avatar_candidates.append({
                        "track_id": tid,
                        "face_image_path": getattr(f, "face_image_path", None),
                        "face_confidence": float(getattr(f, "confidence", -1.0) or -1.0),
                        "embedding": None,
                        "source": "track_best_face",
                    })
                sample = track_best_identity_sample.get(tid) or {}
                if sample.get("face_image_path"):
                    avatar_candidates.append({
                        "track_id": tid,
                        "face_image_path": sample.get("face_image_path"),
                        "face_confidence": float(sample.get("face_confidence", -1.0) or -1.0),
                        "embedding": sample.get("embedding"),
                        "source": "track_best_identity_sample",
                    })

            if avatar_candidates:
                # Chọn ảnh đại diện từ chính track thuộc profile, ưu tiên face_conf cao,
                # rồi track có nhiều observation. Không ưu tiên "latest" nữa vì P001 có thể bị
                # lấy avatar của fragment ngắn mới vào sau (track19) thay vì owner/track chính (track3).
                avatar_candidates.sort(
                    key=lambda c: (
                        float(c.get("face_confidence", -1.0) or -1.0),
                        _track_obs_for_avatar(int(c.get("track_id"))),
                        _track_last_frame_for_avatar(int(c.get("track_id"))),
                        int(c.get("track_id")),
                    ),
                    reverse=True,
                )
                # Chỉ nhận avatar có path tồn tại; nếu path lỗi thì bỏ để khỏi copy nhầm/avatar stale.
                existing_avatar_candidates = []
                for c in avatar_candidates:
                    p = c.get("face_image_path")
                    if p and os.path.exists(str(p)):
                        existing_avatar_candidates.append(c)
                if existing_avatar_candidates:
                    avatar_candidates = existing_avatar_candidates
                best_avatar = avatar_candidates[0]
                best_face_path = best_avatar.get("face_image_path")
                best_face_conf = float(best_avatar.get("face_confidence", -1.0) or -1.0)
                representative_track_id = int(best_avatar.get("track_id"))
                print(
                    f"[IDDBG_EXPORT_AVATAR] profile={profile_id} tracks={valid_tids} "
                    f"representative_track={representative_track_id} "
                    f"conf={best_face_conf:.3f} source={best_avatar.get('source')} path={best_face_path}"
                )

            best_sample = None
            if representative_track_id is not None:
                best_sample = track_best_identity_sample.get(int(representative_track_id))
            if best_sample is None:
                # fallback vẫn chỉ trong valid_tids
                for tid in valid_tids:
                    sample = track_best_identity_sample.get(int(tid))
                    if not sample:
                        continue
                    if best_sample is None or float(sample.get("face_confidence", -1.0) or -1.0) > float(best_sample.get("face_confidence", -1.0) or -1.0):
                        best_sample = sample

            track_embeddings = []
            # For export, pick embedding from representative track first, not stale profile gallery.
            if representative_track_id is not None:
                rep_sample = track_best_identity_sample.get(int(representative_track_id))
                if rep_sample and rep_sample.get("embedding") is not None:
                    track_embeddings.append(rep_sample.get("embedding"))
            if not track_embeddings and best_sample is not None and best_sample.get("embedding") is not None:
                track_embeddings.append(best_sample.get("embedding"))
            # Prefer rebuilt per-track embedding for split profiles, otherwise keep profile gallery.
            embeddings = track_embeddings if track_embeddings else profile_embeddings

            max_track_obs = max([int(track_observation_counts.get(t, 0)) for t in valid_tids] or [0])
            actual_obs = len(frames)

            has_face_or_vector = bool(embeddings) or bool(best_face_path)
            if skip_empty_or_tiny_profile and not has_face_or_vector and actual_obs < int(min_obs_without_face) and max_track_obs < int(min_obs_without_face):
                print(
                    f"[IDDBG_EXPORT_SKIP_EMPTY_PROFILE] profile={profile_id} tracks={valid_tids} "
                    f"actual_frames={actual_obs} max_track_obs={max_track_obs} has_face_or_vector={has_face_or_vector}"
                )
                continue

            merged_profiles.append({
                "profile_id": profile_id,
                "merged_track_ids": valid_tids,
                "total_observations": actual_obs if actual_obs > 0 else profile.get("total_observations", 0),
                "best_face_image_path": best_face_path,
                "best_face_confidence": best_face_conf,
                "representative_track_id": representative_track_id,
                "avatar_track_id": representative_track_id,
                "primary_embedding": embeddings[0] if embeddings else None,
                "embeddings": embeddings,
                "appearance_signatures": profile.get("appearance_signatures", []),
                "match_scores": profile.get("match_scores", []),
                "observed_frame_indices": frames if frames else profile.get("observed_frame_indices", []),
                "frame_bboxes": bboxes if bboxes else profile.get("frame_bboxes", {}),
            })
        return merged_profiles

    def _build_person_paths(
        self,
        track_to_profile: Dict[int, str],
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
    ) -> Dict[str, List[Dict]]:
        """
        Build trajectory data for downstream behavior analytics.

        Output format:
        {
            "P_0001": [
                {"track_id": 31, "frame_index": 1203, "bbox": [...], "center": [cx, cy]},
                ...
            ]
        }

        Important for camera mode:
        - path is grouped by the current committed P_id,
        - original track_id is preserved for audit/debug,
        - points are sorted by frame_index so BE/analytics can draw the route.
        """
        person_paths: Dict[str, List[Dict]] = {}
        for track_id, profile_id in sorted((track_to_profile or {}).items(), key=lambda x: int(x[0])):
            if not profile_id or str(profile_id).startswith("TEMP_") or profile_id == "PENDING":
                continue
            bboxes = track_frame_bboxes.get(int(track_id), {}) or {}
            for frame_index, bbox in sorted(bboxes.items(), key=lambda x: int(x[0])):
                if bbox is None or len(bbox) < 4:
                    continue
                x1, y1, x2, y2 = [float(v) for v in bbox[:4]]
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                person_paths.setdefault(profile_id, []).append({
                    "track_id": int(track_id),
                    "frame_index": int(frame_index),
                    "bbox": [x1, y1, x2, y2],
                    "center": [cx, cy],
                })

        for profile_id in list(person_paths.keys()):
            person_paths[profile_id].sort(key=lambda p: (int(p["frame_index"]), int(p["track_id"])))
        return person_paths

