import os
import time
import cv2
import shutil
import numpy as np
from typing import Dict, List, Optional

from app.services.ai.frame_extractor_service import FrameExtractorService
from app.services.ai.tracking_service import tracker_service
from app.services.ai.face_detection_service import FaceDetectionService, PersonDetectionInput
from app.services.ai.face_embedding_service import FaceEmbeddingService
from app.services.ai.online_identity_service import OnlineIdentityService
from app.services.ai.appearance_signature_service import AppearanceSignatureService
from app.services.ai.person_reid_service import PersonReIDService

from app.services.ai.video_pipeline_debug_utils import VideoPipelineDebugMixin
from app.services.ai.video_pipeline_geometry_utils import VideoPipelineGeometryMixin
from app.services.ai.video_pipeline_export_utils import VideoPipelineExportMixin
from app.services.ai.camera_pipeline_identity_corrections import CameraPipelineIdentityCorrectionMixin


class VideoProcessingPipelineService(
    VideoPipelineDebugMixin,
    VideoPipelineGeometryMixin,
    VideoPipelineExportMixin,
    CameraPipelineIdentityCorrectionMixin,
):
    def __init__(self, yunet_model_path: str = None, sface_model_path: str = None):
        self.frame_extractor = FrameExtractorService()
        self.tracker = tracker_service

        self.face_embedder = FaceEmbeddingService(
            model_path=sface_model_path,
            model_name="face_recognition_sface_2021dec.onnx",
            input_size=(112, 112)
        )

        self.face_detector = FaceDetectionService(
            yunet_model_path=yunet_model_path,
            yunet_score_threshold=0.55
        )

        self.online_identity = OnlineIdentityService(
            strict_threshold=0.42,
            soft_threshold=0.36,
            weak_track_threshold=0.30,
            max_embeddings_per_profile=5,
            max_appearance_per_profile=5,
            # Default sẽ được cập nhật lại theo video_fps trong process_video.
            stale_profile_frames=45,
            entry_reuse_distance_norm=0.18,
            return_distance_norm=0.28,
            stale_strong_face=0.55,
            stale_strong_total=0.52,
            stale_strong_margin=0.08,
            entry_reuse_min_gap_frames=3,
            entry_reuse_strong_face=0.62,
            entry_reuse_strong_margin=0.10,
        )

        self.appearance_service = AppearanceSignatureService()
        self.person_reid_service = PersonReIDService()
        print("VIDEO_PIPELINE_VERSION = camera_realtime_v69_pending_stream_final_clusters")


    def _recover_missing_profile_before_update(
        self,
        *,
        profile_id: str,
        track_id: int,
        embedding,
        face_image_path: str,
        face_confidence: float,
        frame_index: int,
        observation_count: int,
        observed_frame_indices,
        appearance_signature,
        bbox,
        track_to_profile: Dict[int, str],
        profile_owner_track: Dict[str, int],
    ) -> str:
        """
        V57 safety guard.

        Some realtime/body-only paths assign track_to_profile manually before the
        OnlineIdentityService gallery has an actual profile object. Later, when a
        face appears, update_profile(profile_id=...) can crash with KeyError.

        Instead of crashing, create a real profile from the current face sample and
        remap only this track to that real profile id. This does NOT merge into an
        existing candidate, so it is safer than pulling the track to a possibly wrong P_id.
        """
        try:
            profiles = getattr(self.online_identity, "profiles", {}) or {}
            if profile_id in profiles:
                return profile_id
        except Exception:
            return profile_id

        old_pid = profile_id
        try:
            new_pid = self.online_identity.create_new_profile(
                track_id=int(track_id),
                embedding=embedding,
                face_image_path=face_image_path,
                face_confidence=face_confidence,
                frame_index=int(frame_index),
                observation_count=int(observation_count),
                observed_frame_indices=list(observed_frame_indices or [frame_index]),
                appearance_signature=appearance_signature,
                bbox=bbox,
            )
            track_to_profile[int(track_id)] = new_pid
            try:
                self.online_identity.track_to_profile[int(track_id)] = new_pid
            except Exception:
                pass
            profile_owner_track.setdefault(new_pid, int(track_id))
            print(
                f"[IDDBG_MISSING_PROFILE_RECOVER_V57] track={track_id} "
                f"missing_profile={old_pid} -> real_profile={new_pid}, "
                f"frame={frame_index}, obs={observation_count}, face_conf={face_confidence:.2f}"
            )
            return new_pid
        except Exception as exc:
            # Last-resort: remove the stale mapping so update_profile is not called
            # with a non-existent profile id. The track can create/match normally later.
            try:
                track_to_profile.pop(int(track_id), None)
                self.online_identity.track_to_profile.pop(int(track_id), None)
            except Exception:
                pass
            print(
                f"[IDDBG_MISSING_PROFILE_DROP_V57] track={track_id} "
                f"missing_profile={old_pid}, frame={frame_index}, error={type(exc).__name__}: {exc}"
            )
            return ""

    def _track_face_similarity(self, track_a: int, track_b: int, track_best_identity_sample: Dict[int, Dict]) -> float:
        """Cosine similarity between best face embeddings of two tracklets."""
        sa = track_best_identity_sample.get(int(track_a)) or {}
        sb = track_best_identity_sample.get(int(track_b)) or {}
        ea = sa.get("embedding")
        eb = sb.get("embedding")
        if ea is None or eb is None:
            return 0.0
        try:
            import numpy as np
            va = self._normalize_vector(np.array(ea, dtype=np.float32))
            vb = self._normalize_vector(np.array(eb, dtype=np.float32))
            if va is None or vb is None:
                return 0.0
            return float(np.dot(va, vb))
        except Exception:
            return 0.0

    def _tracklet_overlap_frames(self, track_a: int, track_b: int, track_frame_bboxes: Dict[int, Dict[int, List[float]]]) -> int:
        fa = set(int(f) for f in (track_frame_bboxes.get(int(track_a)) or {}).keys())
        fb = set(int(f) for f in (track_frame_bboxes.get(int(track_b)) or {}).keys())
        return len(fa & fb)

    def _find_generic_tracklet_link_candidate(
        self,
        *,
        current_track_id: int,
        track_to_profile: Dict[int, str],
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
        track_observation_counts: Dict[int, int],
        track_body_reid_samples: Dict[int, List[Dict]],
        track_best_identity_sample: Dict[int, Dict],
        max_gap_frames: int,
        max_center_norm: float,
        min_old_obs: int,
        min_new_obs: int,
        max_overlap_frames: int,
        min_body_avg: float,
        min_body_best: float,
        min_color_avg: float,
        min_face: float,
        min_combined: float,
        active_track_ids=None,
    ) -> Optional[Dict]:
        """
        Generic tracklet-link graph edge.

        Không dùng hard-code track id. Chỉ nối tracklet hiện tại vào một tracklet trước đó nếu:
        - hai track không overlap cùng frame đáng kể,
        - gap thời gian hợp lý,
        - bbox nối tiếp gần nhau,
        - body/face đủ đồng thuận.
        """
        cur = int(current_track_id)
        cur_span = self._track_span(track_frame_bboxes, cur)
        if cur_span is None:
            return None
        cur_start, cur_end = int(cur_span[0]), int(cur_span[1])
        cur_obs = int(track_observation_counts.get(cur, 0) or 0)
        if cur_obs < int(min_new_obs):
            return None

        cur_first_bbox = self._track_bbox_at(track_frame_bboxes, cur, cur_start)
        if cur_first_bbox is None:
            return None

        active_set = set(int(t) for t in active_track_ids) if active_track_ids is not None else set()
        cur_samples = track_body_reid_samples.get(cur, []) or []
        best = None

        for prev, prev_pid in sorted(track_to_profile.items(), key=lambda x: int(x[0])):
            prev = int(prev)
            if prev == cur or not prev_pid:
                continue
            # Nếu hai track đang active cùng frame thì không link như successor; để display invariant xử lý.
            if prev in active_set and cur in active_set:
                continue
            prev_span = self._track_span(track_frame_bboxes, prev)
            if prev_span is None:
                continue
            prev_start, prev_end = int(prev_span[0]), int(prev_span[1])
            gap = int(cur_start - prev_end)
            if gap < 0 or gap > int(max_gap_frames):
                continue
            if self._tracklet_overlap_frames(prev, cur, track_frame_bboxes) > int(max_overlap_frames):
                continue
            if int(track_observation_counts.get(prev, 0) or 0) < int(min_old_obs):
                continue

            prev_last_bbox = self._track_bbox_at(track_frame_bboxes, prev, prev_end)
            if prev_last_bbox is None:
                continue
            center_norm = self._bbox_center_distance_norm(prev_last_bbox, cur_first_bbox)
            containment = self._bbox_containment(prev_last_bbox, cur_first_bbox)
            iou = self._bbox_iou(prev_last_bbox, cur_first_bbox)
            area_ratio = self._bbox_area_ratio(prev_last_bbox, cur_first_bbox)
            spatial_ok = (
                center_norm <= float(max_center_norm)
                or iou >= 0.05
                or containment >= 0.18
            ) and 0.20 <= area_ratio <= 5.00
            if not spatial_ok:
                continue

            prev_samples = track_body_reid_samples.get(prev, []) or []
            body_avg = body_best = color_avg = color_best = 0.0
            if prev_samples and cur_samples:
                try:
                    info = self.person_reid_service.compare_tracklets(prev_samples, cur_samples)
                    body_avg = float(info.get("avg_top", 0.0) or 0.0)
                    body_best = float(info.get("best", 0.0) or 0.0)
                    color_avg = float(info.get("color_avg_top", 0.0) or 0.0)
                    color_best = float(info.get("color_best", 0.0) or 0.0)
                except Exception:
                    body_avg = body_best = color_avg = color_best = 0.0

            face = self._track_face_similarity(prev, cur, track_best_identity_sample)
            # spatial_score càng gần càng tốt, nhưng không tự quyết định identity.
            spatial_score = max(0.0, 1.0 - min(center_norm, 1.0))
            body_signal = max(body_avg, body_best * 0.92)
            color_signal = max(color_avg, color_best * 0.90)
            combined = max(
                0.52 * body_signal + 0.28 * color_signal + 0.20 * spatial_score,
                0.70 * face + 0.20 * body_signal + 0.10 * spatial_score,
            )

            strong_body = body_avg >= float(min_body_avg) and body_best >= float(min_body_best)
            strong_color_body = body_best >= float(min_body_best) and color_avg >= float(min_color_avg)
            strong_face = face >= float(min_face) and body_signal >= 0.45
            if not (combined >= float(min_combined) and (strong_body or strong_color_body or strong_face)):
                continue

            cand = {
                "prev_track": prev,
                "target_profile_id": prev_pid,
                "current_track": cur,
                "gap": gap,
                "center_norm": center_norm,
                "iou": iou,
                "containment": containment,
                "area_ratio": area_ratio,
                "body_avg": body_avg,
                "body_best": body_best,
                "color_avg": color_avg,
                "color_best": color_best,
                "face": face,
                "combined": combined,
            }
            if best is None or cand["combined"] > best["combined"]:
                best = cand
        return best

    def _apply_generic_tracklet_linking(
        self,
        *,
        active_track_ids,
        track_to_profile: Dict[int, str],
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
        track_observation_counts: Dict[int, int],
        track_body_reid_samples: Dict[int, List[Dict]],
        track_best_identity_sample: Dict[int, Dict],
        track_debug_status: Dict[int, str],
        profile_owner_track: Dict[str, int],
        max_gap_frames: int,
        max_center_norm: float,
        min_old_obs: int,
        min_new_obs: int,
        max_overlap_frames: int,
        min_body_avg: float,
        min_body_best: float,
        min_color_avg: float,
        min_face: float,
        min_combined: float,
        create_new_profiles: bool = False,
    ) -> int:
        """
        Link track fragments to existing stable profiles using generic tracklet graph edges.
        Realtime-safe: chỉ chuyển vào profile đã tồn tại; mặc định không tạo P_id mới.
        """
        changed = 0
        candidate_tracks = sorted(set(int(t) for t in (active_track_ids or [])) | set(int(t) for t in track_to_profile.keys()))
        for tid in candidate_tracks:
            cand = self._find_generic_tracklet_link_candidate(
                current_track_id=tid,
                track_to_profile=track_to_profile,
                track_frame_bboxes=track_frame_bboxes,
                track_observation_counts=track_observation_counts,
                track_body_reid_samples=track_body_reid_samples,
                track_best_identity_sample=track_best_identity_sample,
                max_gap_frames=max_gap_frames,
                max_center_norm=max_center_norm,
                min_old_obs=min_old_obs,
                min_new_obs=min_new_obs,
                max_overlap_frames=max_overlap_frames,
                min_body_avg=min_body_avg,
                min_body_best=min_body_best,
                min_color_avg=min_color_avg,
                min_face=min_face,
                min_combined=min_combined,
                active_track_ids=active_track_ids,
            )
            if not cand:
                continue
            target_pid = cand.get("target_profile_id")
            old_pid = track_to_profile.get(tid)
            if old_pid == target_pid:
                continue
            if not target_pid:
                continue

            # V17 realtime-safe guard:
            # If the only evidence is body/color/spatial continuity and the current track has no
            # confirmed identity yet, do NOT display the old profile id immediately.
            # Keep it as WAIT_LINK/TMP so a later successor track can confirm the chain without
            # ever showing a wrong P_id on a live camera. This prevents cases like track30 being
            # shown as the old track2 profile before track33 appears.
            cand_face = float(cand.get("face", 0.0) or 0.0)
            cand_body_avg = float(cand.get("body_avg", 0.0) or 0.0)
            cand_body_best = float(cand.get("body_best", 0.0) or 0.0)
            cand_color_avg = float(cand.get("color_avg", 0.0) or 0.0)
            body_color_only_unconfirmed = (
                old_pid is None
                and cand_face < max(0.55, float(min_face) * 0.70)
                and cand_body_avg >= float(min_body_avg)
                and cand_body_best >= float(min_body_best)
                and cand_color_avg >= float(min_color_avg)
            )
            if body_color_only_unconfirmed:
                track_debug_status[int(tid)] = (
                    f"WAIT_SUCCESSOR_CONFIRM: Track {tid} holds TMP, candidate={target_pid}, "
                    f"prev_track={cand.get('prev_track')}, gap={cand.get('gap')}, "
                    f"center={cand.get('center_norm'):.3f}, body_avg={cand_body_avg:.3f}, "
                    f"body_best={cand_body_best:.3f}, color_avg={cand_color_avg:.3f}, "
                    f"face={cand_face:.3f}, combined={cand.get('combined'):.3f}"
                )
                print(f"[IDDBG_TRACKLET_LINK_WAIT_SUCCESSOR] {track_debug_status[int(tid)]}")
                continue

            if old_pid is None and not create_new_profiles:
                # Track chưa có P_id chỉ kế thừa target_pid khi có face đủ mạnh; body/color-only
                # đã bị giữ WAIT_SUCCESSOR_CONFIRM phía trên.
                track_to_profile[int(tid)] = target_pid
                self.online_identity.track_to_profile[int(tid)] = target_pid
                profile_owner_track.setdefault(target_pid, int(cand.get("prev_track")))
                moved = True
            else:
                moved = False
                try:
                    moved = bool(self.online_identity.reassign_track_to_profile(
                        track_id=int(tid),
                        source_profile_id=old_pid,
                        target_profile_id=target_pid,
                    ))
                except Exception:
                    moved = False
                track_to_profile[int(tid)] = target_pid
                self.online_identity.track_to_profile[int(tid)] = target_pid
                profile_owner_track.setdefault(target_pid, int(cand.get("prev_track")))

            track_debug_status[int(tid)] = (
                f"TRACKLET_LINK_RECHECK: Track {tid} {old_pid}->{target_pid}, "
                f"prev_track={cand.get('prev_track')}, gap={cand.get('gap')}, "
                f"center={cand.get('center_norm'):.3f}, body_avg={cand.get('body_avg'):.3f}, "
                f"body_best={cand.get('body_best'):.3f}, color_avg={cand.get('color_avg'):.3f}, "
                f"face={cand.get('face'):.3f}, combined={cand.get('combined'):.3f}, moved={moved}"
            )
            print(f"[IDDBG_TRACKLET_LINK] {track_debug_status[int(tid)]}")
            changed += 1
        return changed

    def _apply_reverse_successor_tracklet_linking(
        self,
        *,
        active_track_ids,
        track_to_profile: Dict[int, str],
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
        track_observation_counts: Dict[int, int],
        track_body_reid_samples: Dict[int, List[Dict]],
        track_best_identity_sample: Dict[int, Dict],
        track_debug_status: Dict[int, str],
        max_gap_frames: int,
        max_center_norm: float,
        min_prev_obs: int,
        min_current_obs: int,
        max_overlap_frames: int,
        min_body_avg: float,
        min_body_best: float,
        min_color_avg: float,
    ) -> int:
        """
        V16 reverse successor link.

        Use when an earlier tracklet has weak/no face and may have been wrongly inherited
        by a nearby old profile, while a later stable tracklet gets a clean new P_id.
        This backfills the weak predecessor into the later clean profile.

        Generic conditions only:
        - predecessor ends before current starts with a short gap,
        - no real overlap,
        - predecessor has no reliable face anchor,
        - spatial continuity plus body/color ReID are strong.
        """
        changed = 0
        active_set = set(int(t) for t in (active_track_ids or []))
        all_tracks = sorted(set(int(t) for t in track_frame_bboxes.keys()) | set(int(t) for t in track_to_profile.keys()))

        for cur in all_tracks:
            cur_pid = track_to_profile.get(int(cur))
            if not cur_pid:
                continue
            cur_obs = int(track_observation_counts.get(int(cur), 0) or 0)
            if cur_obs < int(min_current_obs):
                continue
            cur_span = self._track_span(track_frame_bboxes, int(cur))
            if cur_span is None:
                continue
            cur_start, _cur_end = int(cur_span[0]), int(cur_span[1])
            cur_first_bbox = self._track_bbox_at(track_frame_bboxes, int(cur), cur_start)
            if cur_first_bbox is None:
                continue
            cur_samples = track_body_reid_samples.get(int(cur), []) or []
            if not cur_samples:
                continue

            best = None
            for prev in all_tracks:
                prev = int(prev)
                if prev == int(cur):
                    continue
                if prev in active_set and int(cur) in active_set:
                    continue
                prev_obs = int(track_observation_counts.get(prev, 0) or 0)
                if prev_obs < int(min_prev_obs):
                    continue
                prev_span = self._track_span(track_frame_bboxes, prev)
                if prev_span is None:
                    continue
                _prev_start, prev_end = int(prev_span[0]), int(prev_span[1])
                gap = int(cur_start - prev_end)
                if gap < 0 or gap > int(max_gap_frames):
                    continue
                if self._tracklet_overlap_frames(prev, int(cur), track_frame_bboxes) > int(max_overlap_frames):
                    continue

                # Only steal/backfill weak-face predecessors. This avoids changing stable identities
                # from the previous video while fixing no-face fragments like track30 -> track33.
                prev_best = track_best_identity_sample.get(prev) or {}
                prev_face_conf = float(prev_best.get("face_confidence", -1.0) or -1.0)
                if prev_face_conf >= 0.65:
                    continue

                prev_last_bbox = self._track_bbox_at(track_frame_bboxes, prev, prev_end)
                if prev_last_bbox is None:
                    continue
                center_norm = self._bbox_center_distance_norm(prev_last_bbox, cur_first_bbox)
                containment = self._bbox_containment(prev_last_bbox, cur_first_bbox)
                iou = self._bbox_iou(prev_last_bbox, cur_first_bbox)
                area_ratio = self._bbox_area_ratio(prev_last_bbox, cur_first_bbox)
                spatial_ok = (
                    center_norm <= float(max_center_norm)
                    or iou >= 0.05
                    or containment >= 0.18
                ) and 0.25 <= area_ratio <= 4.00
                if not spatial_ok:
                    continue

                prev_samples = track_body_reid_samples.get(prev, []) or []
                if not prev_samples:
                    continue
                try:
                    info = self.person_reid_service.compare_tracklets(prev_samples, cur_samples)
                    body_avg = float(info.get("avg_top", 0.0) or 0.0)
                    body_best = float(info.get("best", 0.0) or 0.0)
                    color_avg = float(info.get("color_avg_top", 0.0) or 0.0)
                    color_best = float(info.get("color_best", 0.0) or 0.0)
                except Exception:
                    continue

                if not (body_avg >= float(min_body_avg) and body_best >= float(min_body_best) and color_avg >= float(min_color_avg)):
                    continue
                spatial_score = max(0.0, 1.0 - min(center_norm, 1.0))
                combined = 0.54 * body_avg + 0.30 * color_avg + 0.16 * spatial_score
                cand = {
                    "prev_track": prev,
                    "current_track": int(cur),
                    "target_profile_id": cur_pid,
                    "old_profile_id": track_to_profile.get(prev),
                    "gap": gap,
                    "center_norm": center_norm,
                    "iou": iou,
                    "containment": containment,
                    "area_ratio": area_ratio,
                    "body_avg": body_avg,
                    "body_best": body_best,
                    "color_avg": color_avg,
                    "color_best": color_best,
                    "combined": combined,
                    "prev_face_conf": prev_face_conf,
                }
                if best is None or cand["combined"] > best["combined"]:
                    best = cand

            if not best:
                continue
            prev = int(best["prev_track"])
            target_pid = best["target_profile_id"]
            old_pid = best.get("old_profile_id")
            if old_pid == target_pid:
                continue
            moved = False
            if old_pid:
                try:
                    moved = bool(self.online_identity.reassign_track_to_profile(
                        track_id=prev,
                        source_profile_id=old_pid,
                        target_profile_id=target_pid,
                    ))
                except Exception:
                    moved = False
            track_to_profile[prev] = target_pid
            self.online_identity.track_to_profile[prev] = target_pid
            track_debug_status[prev] = (
                f"REVERSE_SUCCESSOR_TRACKLET_LINK: Track {prev} {old_pid}->{target_pid}, "
                f"successor={cur}, gap={best.get('gap')}, center={best.get('center_norm'):.3f}, "
                f"body_avg={best.get('body_avg'):.3f}, body_best={best.get('body_best'):.3f}, "
                f"color_avg={best.get('color_avg'):.3f}, prev_face_conf={best.get('prev_face_conf'):.2f}, "
                f"combined={best.get('combined'):.3f}, moved={moved}"
            )
            print(f"[IDDBG_REVERSE_TRACKLET_LINK] {track_debug_status[prev]}")
            changed += 1
        return changed


    def _apply_short_video_duplicate_fragment_linking(
        self,
        *,
        active_track_ids,
        track_to_profile: Dict[int, str],
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
        track_observation_counts: Dict[int, int],
        track_body_reid_samples: Dict[int, List[Dict]],
        track_best_identity_sample: Dict[int, Dict],
        track_debug_status: Dict[int, str],
        max_short_obs: int,
        max_short_face_conf: float,
        min_stable_obs: int,
        min_overlap_frames: int,
        max_near_gap_frames: int,
        max_center_norm: float,
        min_iou: float,
        min_containment: float,
        min_body_best: float,
        min_color_best: float,
    ) -> int:
        """V66 short-video duplicate/fragment stitch with near-frame fallback.

        Fixes tiny no-face tracklets that appear inside/overlap a stable track of the
        same person, for example a 4-frame duplicate fragment. This is deliberately
        short-video-only at the call site and does not touch stable face-bearing tracks.
        """
        changed = 0
        active_set = set(int(t) for t in (active_track_ids or []))
        all_tracks = sorted(set(int(t) for t in track_frame_bboxes.keys()) | set(int(t) for t in track_to_profile.keys()))
        for frag in all_tracks:
            frag = int(frag)
            frag_obs = int(track_observation_counts.get(frag, 0) or 0)
            if frag_obs <= 0 or frag_obs > int(max_short_obs):
                continue
            frag_best = track_best_identity_sample.get(frag) or {}
            frag_face_conf = float(frag_best.get("face_confidence", -1.0) or -1.0)
            if frag_face_conf >= float(max_short_face_conf):
                continue
            frag_span = self._track_span(track_frame_bboxes, frag)
            if frag_span is None:
                continue
            frag_samples = track_body_reid_samples.get(frag, []) or []
            best = None
            for stable in all_tracks:
                stable = int(stable)
                if stable == frag:
                    continue
                stable_pid = track_to_profile.get(stable)
                if not stable_pid:
                    continue
                stable_obs = int(track_observation_counts.get(stable, 0) or 0)
                if stable_obs < int(min_stable_obs):
                    continue
                stable_span = self._track_span(track_frame_bboxes, stable)
                if stable_span is None:
                    continue
                overlap_start = max(int(frag_span[0]), int(stable_span[0]))
                overlap_end = min(int(frag_span[1]), int(stable_span[1]))
                overlap_frames = []
                if overlap_end >= overlap_start:
                    overlap_frames = [
                        f for f in range(overlap_start, overlap_end + 1)
                        if self._track_bbox_at(track_frame_bboxes, frag, f) is not None
                        and self._track_bbox_at(track_frame_bboxes, stable, f) is not None
                    ]

                # V66: if the tiny fragment has no exact same-frame bbox with the stable track
                # (common in stream/light-tracker mode), use nearest-frame spatial evidence.
                approx_pair = None
                if len(overlap_frames) < int(min_overlap_frames):
                    frag_keys = sorted((track_frame_bboxes.get(frag) or {}).keys())
                    stable_keys = sorted((track_frame_bboxes.get(stable) or {}).keys())
                    best_gap = None
                    best_pair = None
                    for ff in frag_keys:
                        # stable keys can be many; checking all is still cheap for short clips.
                        for sf in stable_keys:
                            g = abs(int(ff) - int(sf))
                            if best_gap is None or g < best_gap:
                                best_gap = g
                                best_pair = (int(ff), int(sf))
                    if best_pair is None or best_gap is None or best_gap > int(max_near_gap_frames):
                        continue
                    approx_pair = best_pair
                    overlap_frames = [int(best_pair[0])]

                # Sample a few overlap frames to avoid expensive full scan.
                if len(overlap_frames) > 8:
                    step = max(1, len(overlap_frames) // 8)
                    overlap_frames = overlap_frames[::step][:8]
                ious, conts, centers = [], [], []
                for f in overlap_frames:
                    if approx_pair is not None:
                        fb = self._track_bbox_at(track_frame_bboxes, frag, int(approx_pair[0]))
                        sb = self._track_bbox_at(track_frame_bboxes, stable, int(approx_pair[1]))
                    else:
                        fb = self._track_bbox_at(track_frame_bboxes, frag, f)
                        sb = self._track_bbox_at(track_frame_bboxes, stable, f)
                    if fb is None or sb is None:
                        continue
                    ious.append(float(self._bbox_iou(fb, sb)))
                    conts.append(float(self._bbox_containment(fb, sb)))
                    centers.append(float(self._bbox_center_distance_norm(fb, sb)))
                if not centers:
                    continue
                try:
                    import numpy as _np
                    med_iou = float(_np.median(_np.asarray(ious, dtype=float)))
                    med_cont = float(_np.median(_np.asarray(conts, dtype=float)))
                    med_center = float(_np.median(_np.asarray(centers, dtype=float)))
                except Exception:
                    med_iou = max(ious or [0.0]); med_cont = max(conts or [0.0]); med_center = min(centers or [9.0])
                spatial_ok = (med_center <= float(max_center_norm)) or (med_iou >= float(min_iou)) or (med_cont >= float(min_containment))
                if not spatial_ok:
                    continue
                stable_samples = track_body_reid_samples.get(stable, []) or []
                body_best = color_best = body_avg = color_avg = 0.0
                if frag_samples and stable_samples:
                    try:
                        info = self.person_reid_service.compare_tracklets(frag_samples, stable_samples)
                        body_avg = float(info.get("avg_top", 0.0) or 0.0)
                        body_best = float(info.get("best", 0.0) or 0.0)
                        color_avg = float(info.get("color_avg_top", 0.0) or 0.0)
                        color_best = float(info.get("color_best", 0.0) or 0.0)
                    except Exception:
                        pass
                appearance_ok = True
                if frag_samples and stable_samples:
                    appearance_ok = (body_best >= float(min_body_best)) or (color_best >= float(min_color_best)) or (body_avg >= 0.55 and color_avg >= 0.50)
                if not appearance_ok:
                    continue
                spatial_score = max(0.0, 1.0 - min(med_center, 1.0))
                frag_mid = 0.5 * (float(frag_span[0]) + float(frag_span[1]))
                stable_contains_frag_time = float(stable_span[0]) <= frag_mid <= float(stable_span[1])
                temporal_score = 1.0 if stable_contains_frag_time else 0.0
                if temporal_score <= 0.0:
                    temporal_gap = min(abs(float(frag_span[0]) - float(stable_span[1])), abs(float(stable_span[0]) - float(frag_span[1])))
                    temporal_score = max(0.0, 1.0 - min(temporal_gap / max(1.0, float(max_near_gap_frames)), 1.0)) * 0.55
                combined = max(
                    0.42 * spatial_score
                    + 0.22 * max(med_iou, med_cont)
                    + 0.18 * max(body_best, color_best)
                    + 0.18 * temporal_score,
                    0.0,
                )
                cand = {
                    "frag": frag,
                    "stable": stable,
                    "target_profile_id": stable_pid,
                    "old_profile_id": track_to_profile.get(frag),
                    "overlap_frames": len(overlap_frames),
                    "center": med_center,
                    "iou": med_iou,
                    "containment": med_cont,
                    "body_avg": body_avg,
                    "body_best": body_best,
                    "color_avg": color_avg,
                    "color_best": color_best,
                    "combined": combined,
                }
                if best is None or cand["combined"] > best["combined"]:
                    best = cand
            if not best:
                continue
            target_pid = best.get("target_profile_id")
            old_pid = best.get("old_profile_id")
            if not target_pid or old_pid == target_pid:
                continue
            moved = False
            if old_pid:
                try:
                    moved = bool(self.online_identity.reassign_track_to_profile(track_id=frag, source_profile_id=old_pid, target_profile_id=target_pid))
                except Exception:
                    moved = False
            track_to_profile[frag] = target_pid
            try:
                self.online_identity.track_to_profile[frag] = target_pid
            except Exception:
                pass
            track_debug_status[frag] = (
                f"SHORT_DUP_FRAGMENT_LINK_V69: Track {frag} {old_pid}->{target_pid}, "
                f"stable_track={best.get('stable')}, overlap={best.get('overlap_frames')}, "
                f"center={best.get('center'):.3f}, iou={best.get('iou'):.3f}, containment={best.get('containment'):.3f}, "
                f"body_best={best.get('body_best'):.3f}, color_best={best.get('color_best'):.3f}, moved={moved}"
            )
            print(f"[IDDBG_SHORT_DUP_FRAGMENT_LINK_V69] {track_debug_status[frag]}")
            changed += 1
        return changed

    def _apply_short_video_no_face_to_face_successor_linking(
        self,
        *,
        active_track_ids,
        track_to_profile: Dict[int, str],
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
        track_observation_counts: Dict[int, int],
        track_body_reid_samples: Dict[int, List[Dict]],
        track_best_identity_sample: Dict[int, Dict],
        track_debug_status: Dict[int, str],
        max_gap_frames: int,
        min_prev_obs: int,
        min_cur_obs: int,
        max_prev_face_conf: float,
        min_cur_face_conf: float,
        min_body_best: float,
        min_body_avg: float,
        min_color_best: float,
        min_combined: float,
    ) -> int:
        """V66 short-video no-face predecessor -> face successor stitch.

        Designed for a stable but unclear no-face track followed by a clearer face track.
        It is only called for short clips and requires body/color/spatial continuity.
        """
        changed = 0
        active_set = set(int(t) for t in (active_track_ids or []))
        all_tracks = sorted(set(int(t) for t in track_frame_bboxes.keys()) | set(int(t) for t in track_to_profile.keys()))
        for cur in all_tracks:
            cur = int(cur)
            cur_pid = track_to_profile.get(cur)
            if not cur_pid:
                continue
            cur_obs = int(track_observation_counts.get(cur, 0) or 0)
            if cur_obs < int(min_cur_obs):
                continue
            cur_best = track_best_identity_sample.get(cur) or {}
            cur_face_conf = float(cur_best.get("face_confidence", -1.0) or -1.0)
            if cur_face_conf < float(min_cur_face_conf):
                continue
            cur_span = self._track_span(track_frame_bboxes, cur)
            if cur_span is None:
                continue
            cur_start = int(cur_span[0])
            cur_first_bbox = self._track_bbox_at(track_frame_bboxes, cur, cur_start)
            if cur_first_bbox is None:
                continue
            cur_samples = track_body_reid_samples.get(cur, []) or []
            if not cur_samples:
                continue
            best = None
            for prev in all_tracks:
                prev = int(prev)
                if prev == cur:
                    continue
                if prev in active_set and cur in active_set:
                    continue
                prev_obs = int(track_observation_counts.get(prev, 0) or 0)
                if prev_obs < int(min_prev_obs):
                    continue
                prev_best = track_best_identity_sample.get(prev) or {}
                prev_face_conf = float(prev_best.get("face_confidence", -1.0) or -1.0)
                if prev_face_conf >= float(max_prev_face_conf):
                    continue
                prev_span = self._track_span(track_frame_bboxes, prev)
                if prev_span is None:
                    continue
                prev_end = int(prev_span[1])
                gap = int(cur_start - prev_end)
                if gap < 0 or gap > int(max_gap_frames):
                    continue
                if self._tracklet_overlap_frames(prev, cur, track_frame_bboxes) > 1:
                    continue
                prev_last_bbox = self._track_bbox_at(track_frame_bboxes, prev, prev_end)
                if prev_last_bbox is None:
                    continue
                prev_samples = track_body_reid_samples.get(prev, []) or []
                if not prev_samples:
                    continue
                try:
                    info = self.person_reid_service.compare_tracklets(prev_samples, cur_samples)
                    body_avg = float(info.get("avg_top", 0.0) or 0.0)
                    body_best = float(info.get("best", 0.0) or 0.0)
                    color_avg = float(info.get("color_avg_top", 0.0) or 0.0)
                    color_best = float(info.get("color_best", 0.0) or 0.0)
                except Exception:
                    continue
                center = float(self._bbox_center_distance_norm(prev_last_bbox, cur_first_bbox))
                iou = float(self._bbox_iou(prev_last_bbox, cur_first_bbox))
                containment = float(self._bbox_containment(prev_last_bbox, cur_first_bbox))
                spatial_score = max(0.0, 1.0 - min(center, 1.0))
                combined = max(
                    0.48 * max(body_avg, body_best * 0.92) + 0.28 * max(color_avg, color_best * 0.90) + 0.24 * spatial_score,
                    0.62 * max(body_avg, body_best * 0.92) + 0.18 * max(color_avg, color_best * 0.90) + 0.20 * max(iou, containment),
                )
                evidence_ok = (
                    combined >= float(min_combined)
                    and body_best >= float(min_body_best)
                    and (body_avg >= float(min_body_avg) or color_best >= float(min_color_best) or spatial_score >= 0.72)
                )
                if not evidence_ok:
                    continue
                cand = {
                    "prev": prev,
                    "cur": cur,
                    "target_profile_id": cur_pid,
                    "old_profile_id": track_to_profile.get(prev),
                    "gap": gap,
                    "center": center,
                    "iou": iou,
                    "containment": containment,
                    "body_avg": body_avg,
                    "body_best": body_best,
                    "color_avg": color_avg,
                    "color_best": color_best,
                    "combined": combined,
                    "prev_face_conf": prev_face_conf,
                    "cur_face_conf": cur_face_conf,
                }
                if best is None or cand["combined"] > best["combined"]:
                    best = cand
            if not best:
                continue
            prev = int(best["prev"])
            target_pid = best.get("target_profile_id")
            old_pid = best.get("old_profile_id")
            if not target_pid or old_pid == target_pid:
                continue
            moved = False
            if old_pid:
                try:
                    moved = bool(self.online_identity.reassign_track_to_profile(track_id=prev, source_profile_id=old_pid, target_profile_id=target_pid))
                except Exception:
                    moved = False
            track_to_profile[prev] = target_pid
            try:
                self.online_identity.track_to_profile[prev] = target_pid
            except Exception:
                pass
            track_debug_status[prev] = (
                f"SHORT_NO_FACE_TO_FACE_SUCCESSOR_LINK_V69: Track {prev} {old_pid}->{target_pid}, "
                f"successor={best.get('cur')}, gap={best.get('gap')}, center={best.get('center'):.3f}, "
                f"body_avg={best.get('body_avg'):.3f}, body_best={best.get('body_best'):.3f}, "
                f"color_best={best.get('color_best'):.3f}, combined={best.get('combined'):.3f}, moved={moved}"
            )
            print(f"[IDDBG_SHORT_NO_FACE_TO_FACE_SUCCESSOR_LINK_V69] {track_debug_status[prev]}")
            changed += 1
        return changed

    def _apply_short_video_overlap_fragment_override_v69(
        self,
        *,
        track_to_profile: Dict[int, str],
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
        track_observation_counts: Dict[int, int],
        track_body_reid_samples: Dict[int, List[Dict]],
        track_best_identity_sample: Dict[int, Dict],
        track_debug_status: Dict[int, str],
        max_short_obs: int = 12,
        max_short_face_conf: float = 0.35,
        min_stable_obs: int = 80,
        max_center_norm: float = 0.58,
        min_containment: float = 0.18,
    ) -> int:
        """V69: final-only short-video override for tiny fragments.

        A tiny no-face fragment can be inherited from the just-closed wrong track before
        the correct stable track gets enough evidence. For short clips, prefer a stable
        track that actually overlaps the fragment in time over a previous/closed track.
        This updates final mapping / final profile list, but stream display can still hide
        the uncertain fragment as PENDING until the final summary is produced.
        """
        changed = 0
        all_tracks = sorted(set(int(t) for t in track_frame_bboxes.keys()) | set(int(t) for t in track_to_profile.keys()))
        for frag in all_tracks:
            frag_obs = int(track_observation_counts.get(frag, 0) or 0)
            if frag_obs <= 0 or frag_obs > int(max_short_obs):
                continue
            frag_best = track_best_identity_sample.get(frag) or {}
            frag_face_conf = float(frag_best.get("face_confidence", -1.0) or -1.0)
            if frag_face_conf >= float(max_short_face_conf):
                continue
            frag_span = self._track_span(track_frame_bboxes, frag)
            if frag_span is None:
                continue
            old_pid = track_to_profile.get(frag)
            best = None
            for stable in all_tracks:
                stable = int(stable)
                if stable == frag:
                    continue
                stable_pid = track_to_profile.get(stable)
                if not stable_pid or stable_pid == old_pid:
                    continue
                stable_obs = int(track_observation_counts.get(stable, 0) or 0)
                if stable_obs < int(min_stable_obs):
                    continue
                stable_span = self._track_span(track_frame_bboxes, stable)
                if stable_span is None:
                    continue
                # Crucial condition: stable track must be present during the fragment.
                overlap_start = max(int(frag_span[0]), int(stable_span[0]))
                overlap_end = min(int(frag_span[1]), int(stable_span[1]))
                if overlap_end < overlap_start:
                    continue
                overlap_frames = [
                    f for f in range(overlap_start, overlap_end + 1)
                    if self._track_bbox_at(track_frame_bboxes, frag, f) is not None
                    and self._track_bbox_at(track_frame_bboxes, stable, f) is not None
                ]
                if not overlap_frames:
                    continue
                if len(overlap_frames) > 8:
                    step = max(1, len(overlap_frames) // 8)
                    overlap_frames = overlap_frames[::step][:8]
                centers, conts, ious = [], [], []
                for f in overlap_frames:
                    fb = self._track_bbox_at(track_frame_bboxes, frag, f)
                    sb = self._track_bbox_at(track_frame_bboxes, stable, f)
                    if fb is None or sb is None:
                        continue
                    centers.append(float(self._bbox_center_distance_norm(fb, sb)))
                    conts.append(float(self._bbox_containment(fb, sb)))
                    ious.append(float(self._bbox_iou(fb, sb)))
                if not centers:
                    continue
                try:
                    import numpy as _np
                    center = float(_np.median(_np.asarray(centers, dtype=float)))
                    cont = float(_np.median(_np.asarray(conts, dtype=float)))
                    iou = float(_np.median(_np.asarray(ious, dtype=float)))
                except Exception:
                    center = min(centers or [9.0]); cont = max(conts or [0.0]); iou = max(ious or [0.0])
                if center > float(max_center_norm) and cont < float(min_containment):
                    continue
                frag_samples = track_body_reid_samples.get(frag, []) or []
                stable_samples = track_body_reid_samples.get(stable, []) or []
                body_best = color_best = 0.0
                if frag_samples and stable_samples:
                    try:
                        info = self.person_reid_service.compare_tracklets(frag_samples, stable_samples)
                        body_best = float(info.get("best", 0.0) or 0.0)
                        color_best = float(info.get("color_best", 0.0) or 0.0)
                    except Exception:
                        pass
                    # If we have appearance and it strongly contradicts, don't override.
                    if body_best < 0.45 and color_best < 0.45:
                        continue
                score = (1.0 - min(center, 1.0)) * 0.50 + max(cont, iou) * 0.30 + max(body_best, color_best) * 0.20
                cand = {"frag": frag, "stable": stable, "pid": stable_pid, "center": center, "cont": cont, "iou": iou, "body_best": body_best, "color_best": color_best, "score": score}
                if best is None or cand["score"] > best["score"]:
                    best = cand
            if not best:
                continue
            target_pid = best["pid"]
            if not target_pid or target_pid == old_pid:
                continue
            moved = False
            if old_pid:
                try:
                    moved = bool(self.online_identity.reassign_track_to_profile(track_id=frag, source_profile_id=old_pid, target_profile_id=target_pid))
                except Exception:
                    moved = False
            track_to_profile[frag] = target_pid
            try:
                self.online_identity.track_to_profile[frag] = target_pid
            except Exception:
                pass
            track_debug_status[frag] = (
                f"SHORT_OVERLAP_FRAGMENT_OVERRIDE_V69: Track {frag} {old_pid}->{target_pid}, "
                f"stable_track={best.get('stable')}, center={best.get('center'):.3f}, "
                f"containment={best.get('cont'):.3f}, iou={best.get('iou'):.3f}, "
                f"body_best={best.get('body_best'):.3f}, color_best={best.get('color_best'):.3f}, moved={moved}"
            )
            print(f"[IDDBG_SHORT_OVERLAP_FRAGMENT_OVERRIDE_V69] {track_debug_status[frag]}")
            changed += 1
        return changed

    def _suppress_uncertain_short_stream_ids_v69(self, frame_records) -> None:
        """Hide IDs in stream for final-only short-video stitches.

        The frontend should not see a temporary P_id for body-only predecessors or tiny
        fragments. They stay PENDING/TENTATIVE in live stream; the final result returns
        `profile_track_ids` for the listing UI.
        """
        for rec in frame_records or []:
            status = str(rec.get("debug_status_snapshot") or "")
            obs = int(rec.get("observation_count", 0) or 0)
            hide = False
            tid = int(rec.get("track_id", -1) or -1)
            if "NO_FACE_STABLE_REALTIME_PROFILE" in status:
                hide = True
            if tid in getattr(self, "_short_video_stream_pending_only_tracks", set()):
                hide = True
            if "SHORT_NO_FACE_TO_FACE_SUCCESSOR_LINK" in status:
                hide = True
            # V69 rollback: do NOT hide/override ordinary short fragments such as track22.
            if "FRAGMENT_CONTINUITY_HANDOFF" in status and obs <= 12 and tid in getattr(self, "_short_video_stream_pending_only_tracks", set()):
                hide = True
            if hide:
                rec["display_stage"] = "PENDING"
                rec["display_profile_id"] = None
                rec["display_text"] = "PENDING: final-only short-video stitch, wait for final cluster list"

    def _build_profile_track_ids_v69(self, track_to_profile: Dict[int, str]) -> Dict[str, List[int]]:
        grouped: Dict[str, List[int]] = {}
        for tid, pid in (track_to_profile or {}).items():
            if not pid:
                continue
            grouped.setdefault(str(pid), []).append(int(tid))
        return {pid: sorted(tids) for pid, tids in sorted(grouped.items(), key=lambda kv: kv[0])}

    def _build_profile_track_ids_v69(
        self,
        track_to_profile: Dict[int, str],
        *,
        track_observation_counts: Dict[int, int],
        track_body_reid_samples: Dict[int, list],
        track_debug_status: Dict[int, str],
        short_video: bool,
    ) -> Dict[str, List[int]]:
        """V69: final listing with tiny visual-outlier cleanup.

        Keeps valid tiny fragments such as track22->P04 when visual evidence is compatible,
        but excludes tiny no-face fragments such as track34 from [26,28] when body/color
        evidence is a clear outlier. This affects the final listing only; it does not
        rewrite live-camera identity decisions.
        """
        # Build the raw grouping directly here. Do NOT call _build_profile_track_ids_v69()
        # recursively, because this method now requires keyword-only cleanup arguments.
        grouped: Dict[str, List[int]] = {}
        for raw_tid, raw_pid in (track_to_profile or {}).items():
            if not raw_pid:
                continue
            try:
                tid_i = int(raw_tid)
            except Exception:
                continue
            grouped.setdefault(str(raw_pid), []).append(tid_i)
        grouped = {pid: sorted(set(tids)) for pid, tids in sorted(grouped.items(), key=lambda kv: kv[0])}

        if not short_video:
            return grouped

        cleaned: Dict[str, List[int]] = {}
        for pid, tids in grouped.items():
            kept = []
            for tid in tids:
                obs = int((track_observation_counts or {}).get(int(tid), 0) or 0)
                samples = (track_body_reid_samples or {}).get(int(tid), []) or []
                status = str((track_debug_status or {}).get(int(tid), ""))
                is_tiny_fragment = obs <= 6 and len(samples) <= 1 and (
                    "FRAGMENT_CONTINUITY_HANDOFF" in status
                    or "SHORT_DUP_FRAGMENT" in status
                    or "HANDOFF" in status
                )
                if not is_tiny_fragment or len(tids) <= 1:
                    kept.append(int(tid))
                    continue

                # Compare tiny fragment with stronger peers inside the same final profile.
                best_body = 0.0
                best_color = 0.0
                comparable = 0
                for other in tids:
                    other = int(other)
                    if other == int(tid):
                        continue
                    other_obs = int((track_observation_counts or {}).get(other, 0) or 0)
                    other_samples = (track_body_reid_samples or {}).get(other, []) or []
                    if other_obs < 20 or not samples or not other_samples:
                        continue
                    try:
                        info = self.person_reid_service.compare_tracklets(samples, other_samples)
                        comparable += 1
                        best_body = max(best_body, float(info.get("best", 0.0) or 0.0), float(info.get("avg_top", 0.0) or 0.0))
                        best_color = max(best_color, float(info.get("color_best", 0.0) or 0.0), float(info.get("color_avg_top", 0.0) or 0.0))
                    except Exception:
                        pass

                # If there is compatible evidence, keep it. Track22/P04 is kept by this path.
                if comparable == 0 or best_body >= 0.80 or best_color >= 0.86:
                    kept.append(int(tid))
                else:
                    print(
                        f"[IDDBG_FINAL_TINY_OUTLIER_DROP_V69] profile={pid} drop_track={tid}, "
                        f"obs={obs}, body_best={best_body:.3f}, color_best={best_color:.3f}, status={status}"
                    )
            if kept:
                cleaned[pid] = sorted(set(int(t) for t in kept))
        return {pid: cleaned[pid] for pid in sorted(cleaned.keys())}

    def _assign_stable_no_face_tracks_to_new_profiles_realtime(
        self,
        *,
        current_frame_index: int,
        current_frame=None,
        active_track_ids,
        track_to_profile: Dict[int, str],
        track_frame_indices: Dict[int, set],
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
        track_observation_counts: Dict[int, int],
        track_body_reid_samples: Dict[int, List[Dict]],
        track_best_identity_sample: Dict[int, Dict],
        track_debug_status: Dict[int, str],
        profile_owner_track: Dict[str, int],
        frame_profile_locks: Dict[int, Dict[str, Dict]],
        min_obs: int = 70,
        min_actual_frames: int = 60,
        min_body_samples: int = 2,
        max_good_face_conf: float = 0.70,
        frame_width: Optional[int] = None,
        frame_height: Optional[int] = None,
        min_median_height_norm: float = 0.18,
        min_median_width_norm: float = 0.035,
        min_median_area_norm: float = 0.012,
        max_median_top_y_norm: float = 0.78,
    ) -> int:
        """
        V45 realtime body-only profile creation.

        Dùng cho camera stream, không đợi export cuối video. Nếu một track đang active,
        đủ ổn định nhưng không có face tốt/best identity sample, tạo P_id riêng để UI
        không giữ PENDING đến hết video. Không đưa embedding giả vào gallery, nên không
        ảnh hưởng face matching của các track khác.
        """
        import re

        active_set = set(int(t) for t in (active_track_ids or []))
        if not active_set:
            return 0

        def _pid_num(pid) -> int:
            m = re.match(r"^P_(\d+)$", str(pid or ""))
            return int(m.group(1)) if m else 0

        used_pids = set(str(pid) for pid in (track_to_profile or {}).values() if pid)
        try:
            for p in self.online_identity.export_profiles() or []:
                if p.get("profile_id"):
                    used_pids.add(str(p.get("profile_id")))
        except Exception:
            pass
        next_idx = max([_pid_num(pid) for pid in used_pids] or [0]) + 1

        changed = 0
        for tid in sorted(active_set):
            if track_to_profile.get(tid):
                continue
            obs = int(track_observation_counts.get(tid, 0) or 0)
            frames = sorted(int(f) for f in (track_frame_indices.get(tid, set()) or set()))
            actual_frames = len(frames)
            if obs < int(min_obs) or actual_frames < int(min_actual_frames):
                continue

            body_samples = track_body_reid_samples.get(tid, []) or []
            if len(body_samples) < int(min_body_samples):
                track_debug_status[tid] = (
                    f"PENDING: stable no-face track but waiting body samples, "
                    f"obs={obs}, frames={actual_frames}, body_samples={len(body_samples)}/{int(min_body_samples)}"
                )
                continue

            best = track_best_identity_sample.get(tid) or {}
            try:
                best_conf = float(best.get("face_confidence", -1.0) or -1.0)
            except Exception:
                best_conf = -1.0
            # Nếu đã có face tốt thì để nhánh face/new-first tạo profile, tránh tạo body-only trùng.
            if best_conf >= float(max_good_face_conf):
                continue

            span = self._track_span(track_frame_bboxes, tid)
            if span is None:
                continue
            first_bbox = self._track_bbox_at(track_frame_bboxes, tid, int(span[0]))
            last_bbox = self._track_bbox_at(track_frame_bboxes, tid, int(span[1]))
            lock_bbox = last_bbox or first_bbox

            # V49 guard: dùng lại đúng hàm crop-validity đã có trong VideoPipelineGeometryMixin.
            # Hàm này đã được thiết kế để chặn crop quá xấu/partial-body, đặc biệt case chỉ thấy chân
            # hoặc bbox quá thấp ở đáy khung. Không tạo thêm một bộ threshold thứ hai dễ lệch logic.
            # V49: do not rely on outer-scope frame_width/frame_height.
            # This function can be called from correction/snapshot code where those locals
            # are not defined. Use current_frame.shape directly.
            try:
                _fh, _fw = current_frame.shape[:2] if current_frame is not None else (0, 0)
            except Exception:
                _fh, _fw = 0, 0
            fw = float(_fw or 0)
            fh = float(_fh or 0)
            if fw > 1 and fh > 1:
                recent_bboxes = []
                for ff in frames[-min(len(frames), 24):]:
                    bb = self._track_bbox_at(track_frame_bboxes, tid, int(ff))
                    if bb is not None and len(bb) >= 4:
                        recent_bboxes.append(bb)
                if len(recent_bboxes) < max(8, int(min_body_samples)):
                    track_debug_status[tid] = (
                        f"PENDING: no-face body-only candidate waiting visible-body frames, "
                        f"obs={obs}, frames={actual_frames}, recent_boxes={len(recent_bboxes)}"
                    )
                    continue

                # _is_valid_person_crop_for_identity chỉ dùng frame.shape + bbox,
                # nên có thể dùng current_frame để kiểm tra bbox lịch sử cùng kích thước video.
                valid_recent = 0
                for bb in recent_bboxes:
                    try:
                        if current_frame is not None and self._is_valid_person_crop_for_identity(current_frame, bb):
                            valid_recent += 1
                    except Exception:
                        pass
                valid_ratio = float(valid_recent) / max(1, len(recent_bboxes))
                current_bbox_valid = False
                try:
                    current_bbox_valid = bool(current_frame is not None and lock_bbox is not None and self._is_valid_person_crop_for_identity(current_frame, lock_bbox))
                except Exception:
                    current_bbox_valid = False

                import numpy as _np
                ws = _np.array([max(0.0, float(bb[2]) - float(bb[0])) / fw for bb in recent_bboxes], dtype=float)
                hs = _np.array([max(0.0, float(bb[3]) - float(bb[1])) / fh for bb in recent_bboxes], dtype=float)
                areas = ws * hs
                tops = _np.array([max(0.0, min(1.0, float(bb[1]) / fh)) for bb in recent_bboxes], dtype=float)
                ratios = _np.array([float(h / max(w, 1e-6)) for h, w in zip(hs, ws)], dtype=float)
                med_w = float(_np.median(ws))
                med_h = float(_np.median(hs))
                med_area = float(_np.median(areas))
                med_top = float(_np.median(tops))
                med_ratio = float(_np.median(ratios))

                visible_body_ok = (
                    current_bbox_valid
                    and valid_recent >= max(6, int(min_body_samples))
                    and valid_ratio >= 0.62
                    and med_h >= float(min_median_height_norm)
                    and med_w >= float(min_median_width_norm)
                    and med_area >= float(min_median_area_norm)
                    and med_top <= float(max_median_top_y_norm)
                    and 1.05 <= med_ratio <= 6.20
                )
                if not visible_body_ok:
                    track_debug_status[tid] = (
                        f"PENDING: no-face body-only blocked by existing crop guard, "
                        f"obs={obs}, frames={actual_frames}, body_samples={len(body_samples)}, "
                        f"valid_recent={valid_recent}/{len(recent_bboxes)}, valid_ratio={valid_ratio:.2f}, "
                        f"current_valid={current_bbox_valid}, h={med_h:.3f}, w={med_w:.3f}, "
                        f"area={med_area:.3f}, top={med_top:.3f}, ratio={med_ratio:.2f}"
                    )
                    print(f"[IDDBG_NO_FACE_STABLE_REALTIME_PARTIAL_BODY_BLOCK_V49] {track_debug_status[tid]}")
                    continue

            while True:
                pid = f"P_{next_idx:04d}"
                next_idx += 1
                if pid not in used_pids:
                    break
            used_pids.add(pid)

            # Tránh OnlineIdentityService tạo lại cùng số P_id ở các frame sau.
            for attr in ("next_profile_index", "_next_profile_index", "next_profile_id", "_next_profile_id", "profile_counter", "_profile_counter"):
                try:
                    cur = getattr(self.online_identity, attr)
                    if isinstance(cur, int) and cur < next_idx:
                        setattr(self.online_identity, attr, next_idx)
                except Exception:
                    pass

            track_to_profile[tid] = pid
            try:
                self.online_identity.track_to_profile[tid] = pid
            except Exception:
                pass
            profile_owner_track.setdefault(pid, tid)

            if lock_bbox is not None:
                try:
                    self._lock_profile_in_frame(
                        frame_profile_locks=frame_profile_locks,
                        frame_index=int(current_frame_index),
                        profile_id=pid,
                        track_id=tid,
                        bbox=lock_bbox,
                    )
                    self.online_identity.update_profile_spatial_observation(
                        profile_id=pid,
                        track_id=tid,
                        frame_index=int(current_frame_index),
                        bbox=lock_bbox,
                    )
                except Exception:
                    pass

            track_debug_status[tid] = (
                f"NO_FACE_STABLE_REALTIME_PROFILE_EXISTING_CROP_GUARD_V49: Track {tid} -> {pid}, "
                f"obs={obs}, frames={actual_frames}, body_samples={len(body_samples)}, "
                f"best_face_conf={best_conf:.2f}, span={int(span[0])}->{int(span[1])}"
            )
            try:
                if getattr(self, "_short_video_stream_suppress_enabled", False):
                    getattr(self, "_short_video_stream_pending_only_tracks", set()).add(int(tid))
            except Exception:
                pass
            print(f"[IDDBG_NO_FACE_STABLE_REALTIME_PROFILE_V49] {track_debug_status[tid]}")
            changed += 1
        return changed



    def _apply_body_only_return_tracklet_linking(
        self,
        *,
        active_track_ids,
        track_to_profile: Dict[int, str],
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
        track_observation_counts: Dict[int, int],
        track_body_reid_samples: Dict[int, List[Dict]],
        track_best_identity_sample: Dict[int, Dict],
        track_debug_status: Dict[int, str],
        max_gap_frames: int,
        min_prev_obs: int,
        min_cur_obs: int,
        min_prev_samples: int,
        min_cur_samples: int,
        min_body_avg: float,
        min_body_best: float,
        min_color_avg: float,
        min_combined: float,
    ) -> int:
        """V59 no-face-only body/color tracklet return linker. Never pulls face-bearing tracks."""
        changed = 0
        active_set = set(int(t) for t in (active_track_ids or []))
        all_tracks = sorted(set(int(t) for t in track_frame_bboxes.keys()) | set(int(t) for t in track_to_profile.keys()))
        for cur in all_tracks:
            cur = int(cur)
            cur_pid = track_to_profile.get(cur)
            cur_obs = int(track_observation_counts.get(cur, 0) or 0)
            if cur_obs < int(min_cur_obs):
                continue
            cur_samples = track_body_reid_samples.get(cur, []) or []
            if len(cur_samples) < int(min_cur_samples):
                continue
            cur_span = self._track_span(track_frame_bboxes, cur)
            if cur_span is None:
                continue
            cur_start = int(cur_span[0])
            cur_best = track_best_identity_sample.get(cur) or {}
            cur_face_conf = float(cur_best.get("face_confidence", -1.0) or -1.0)
            # V59: BODY_ONLY_RETURN_LINK is strictly for no-face / extremely weak-face
            # fragments only. V58 was too broad and incorrectly pulled face-bearing
            # tracks such as track9 and track25 by body/color alone.
            if cur_face_conf >= 0.30:
                continue
            # If a track already has a stable face identity sample, never let the
            # body-only linker override its P_id. Face-bearing returns must go
            # through the normal face/app gated return path instead.
            if cur_best.get("embedding") is not None and cur_face_conf >= 0.0:
                continue
            best = None
            for prev_pid in sorted(set(pid for pid in track_to_profile.values() if pid)):
                prev_tracks = [int(t) for t, pid in track_to_profile.items() if pid == prev_pid]
                if len(prev_tracks) != 1:
                    continue
                prev = int(prev_tracks[0])
                if prev == cur:
                    continue
                if prev in active_set and cur in active_set:
                    continue
                prev_obs = int(track_observation_counts.get(prev, 0) or 0)
                if prev_obs < int(min_prev_obs):
                    continue
                prev_samples = track_body_reid_samples.get(prev, []) or []
                if len(prev_samples) < int(min_prev_samples):
                    continue
                prev_span = self._track_span(track_frame_bboxes, prev)
                if prev_span is None:
                    continue
                gap = int(cur_start - int(prev_span[1]))
                if gap < 0 or gap > int(max_gap_frames):
                    continue
                if self._tracklet_overlap_frames(prev, cur, track_frame_bboxes) > 0:
                    continue
                try:
                    info = self.person_reid_service.compare_tracklets(prev_samples, cur_samples)
                    body_avg = float(info.get("avg_top", 0.0) or 0.0)
                    body_best = float(info.get("best", 0.0) or 0.0)
                    color_avg = float(info.get("color_avg_top", 0.0) or 0.0)
                    color_best = float(info.get("color_best", 0.0) or 0.0)
                except Exception:
                    continue
                combined = 0.52 * body_avg + 0.28 * color_avg + 0.20 * min(body_best, 1.0)
                if not (body_avg >= float(min_body_avg) and body_best >= float(min_body_best) and color_avg >= float(min_color_avg) and combined >= float(min_combined)):
                    continue
                cand = {"prev_track": prev, "target_profile_id": prev_pid, "old_profile_id": cur_pid, "gap": gap, "body_avg": body_avg, "body_best": body_best, "color_avg": color_avg, "color_best": color_best, "combined": combined, "cur_face_conf": cur_face_conf}
                if best is None or cand["combined"] > best["combined"]:
                    best = cand
            if not best:
                continue
            target_pid = best["target_profile_id"]
            old_pid = best.get("old_profile_id")
            if old_pid == target_pid:
                continue
            moved = False
            if old_pid:
                try:
                    moved = bool(self.online_identity.reassign_track_to_profile(track_id=cur, source_profile_id=old_pid, target_profile_id=target_pid))
                except Exception:
                    moved = False
            track_to_profile[cur] = target_pid
            self.online_identity.track_to_profile[cur] = target_pid
            track_debug_status[cur] = (f"BODY_ONLY_RETURN_TRACKLET_LINK_V59: Track {cur} {old_pid}->{target_pid}, prev_track={best.get('prev_track')}, gap={best.get('gap')}, body_avg={best.get('body_avg'):.3f}, body_best={best.get('body_best'):.3f}, color_avg={best.get('color_avg'):.3f}, combined={best.get('combined'):.3f}, cur_face_conf={best.get('cur_face_conf'):.2f}, moved={moved}")
            print(f"[IDDBG_BODY_ONLY_RETURN_LINK_V59] {track_debug_status[cur]}")
            changed += 1
        return changed

    def _mark_same_frame_profile_conflicts_no_split(
        self,
        *,
        frame_index: int,
        active_track_ids,
        active_track_bboxes: Dict[int, List[float]],
        track_to_profile: Dict[int, str],
        track_debug_status: Dict[int, str],
        duplicate_iou_threshold: float = 0.55,
        duplicate_center_norm_threshold: float = 0.12,
        profile_owner_track: Optional[Dict[str, int]] = None,
        track_observation_counts: Optional[Dict[int, int]] = None,
    ) -> int:
        """
        HARD realtime identity invariant.

        Một P_id không được tồn tại trên hai bbox khác nhau trong cùng frame.
        Khác với bản v6, đây KHÔNG chỉ ẩn label ở overlay. Nếu hai bbox không phải
        duplicate của cùng một người, mapping nội bộ của track phụ được tách ngay
        sang P_id mới bằng split_track_to_new_profile().

        Chỉ giữ cùng P_id khi hai bbox gần như duplicate tracker/detection của cùng
        một người. Như vậy không còn case người B vẫn giữ id của người A nhưng chỉ
        bị che display_profile_id.
        """
        groups = {}
        for tid in sorted(int(t) for t in active_track_ids or []):
            pid = track_to_profile.get(tid)
            if pid:
                groups.setdefault(pid, []).append(tid)

        changed = 0
        obs_map = track_observation_counts or {}

        for pid, tids in groups.items():
            if len(tids) <= 1:
                continue

            tids = sorted(set(int(t) for t in tids))

            def _rank_keep(t: int):
                # Ưu tiên owner profile nếu biết; sau đó track ổn định/obs nhiều.
                is_owner = 1 if profile_owner_track is not None and int(profile_owner_track.get(pid, -999999)) == int(t) else 0
                return (is_owner, int(obs_map.get(int(t), 0) or 0), -int(t))

            keep = max(tids, key=_rank_keep)
            keep_box = active_track_bboxes.get(keep)

            for tid in [t for t in tids if int(t) != int(keep)]:
                tid = int(tid)
                box = active_track_bboxes.get(tid)
                iou = self._bbox_iou(keep_box, box)
                center = self._bbox_center_distance_norm(keep_box, box)
                containment = self._bbox_containment(keep_box, box)
                area_ratio = self._bbox_area_ratio(keep_box, box)

                duplicate_like = (
                    iou >= duplicate_iou_threshold
                    or containment >= 0.72
                    or (center <= duplicate_center_norm_threshold and containment >= 0.18 and 0.45 <= area_ratio <= 2.50)
                    # V10: tracker handoff của cùng một người đôi khi tạo hai bbox lệch nhẹ
                    # trong vài frame giao nhau. Nếu kích thước gần nhau và containment vừa đủ,
                    # coi là duplicate thay vì split nhầm ra P mới. Clause này cứu các case
                    # kiểu track41->81 nhưng vẫn không cứu các case lệch lớn như track31->56.
                    or (center <= 0.38 and containment >= 0.55 and 0.70 <= area_ratio <= 1.65)
                )

                if duplicate_like:
                    track_debug_status[tid] = (
                        f"RECHECK_DUPLICATE_TRACK: same-frame duplicate candidate {pid}, "
                        f"keep_track={keep}, iou={iou:.3f}, containment={containment:.3f}, "
                        f"center={center:.3f}, area_ratio={area_ratio:.3f}"
                    )
                    print(
                        f"[IDDBG_SAME_FRAME_DUPLICATE_KEEP] frame={frame_index} track={tid} "
                        f"profile={pid} keep={keep} iou={iou:.3f} containment={containment:.3f} center={center:.3f}"
                    )
                    changed += 1
                    continue

                # Hai bbox khác nhau thật sự: tách mapping nội bộ ngay, không chỉ ẩn overlay.
                new_pid = None
                try:
                    new_pid = self.online_identity.split_track_to_new_profile(
                        track_id=tid,
                        source_profile_id=pid,
                    )
                except TypeError:
                    try:
                        new_pid = self.online_identity.split_track_to_new_profile(pid, tid)
                    except Exception:
                        new_pid = None
                except Exception:
                    new_pid = None

                if new_pid:
                    track_to_profile[tid] = new_pid
                    self.online_identity.track_to_profile[tid] = new_pid
                    if profile_owner_track is not None:
                        profile_owner_track[new_pid] = tid
                    track_debug_status[tid] = (
                        f"SAME_FRAME_HARD_SPLIT: Track {tid} {pid} -> {new_pid}, "
                        f"keep_track={keep}, iou={iou:.3f}, containment={containment:.3f}, "
                        f"center={center:.3f}, area_ratio={area_ratio:.3f}"
                    )
                    print(
                        f"[IDDBG_SAME_FRAME_HARD_SPLIT] frame={frame_index} track={tid} "
                        f"{pid}->{new_pid}, keep_track={keep}, iou={iou:.3f}, "
                        f"containment={containment:.3f}, center={center:.3f}, area_ratio={area_ratio:.3f}"
                    )
                else:
                    # Fallback: ít nhất xóa mapping nội bộ để không giữ id người A trên người B.
                    track_to_profile.pop(tid, None)
                    try:
                        self.online_identity.track_to_profile.pop(tid, None)
                    except Exception:
                        pass
                    track_debug_status[tid] = (
                        f"SAME_FRAME_HARD_UNASSIGN: Track {tid} removed from {pid}, "
                        f"keep_track={keep}, iou={iou:.3f}, containment={containment:.3f}, "
                        f"center={center:.3f}, area_ratio={area_ratio:.3f}"
                    )
                    print(
                        f"[IDDBG_SAME_FRAME_HARD_UNASSIGN] frame={frame_index} track={tid} "
                        f"removed_from={pid}, keep_track={keep}, iou={iou:.3f}, "
                        f"containment={containment:.3f}, center={center:.3f}, area_ratio={area_ratio:.3f}"
                    )
                changed += 1

        return changed


    def _profile_track_ids(self, track_to_profile: Dict[int, str], profile_id: str) -> List[int]:
        return [int(tid) for tid, pid in track_to_profile.items() if pid == profile_id]

    def _profile_has_real_overlap_with_track(
        self,
        *,
        current_track_id: int,
        candidate_profile_id: str,
        track_to_profile: Dict[int, str],
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
        max_overlap_frames: int = 0,
    ) -> bool:
        """
        True nếu candidate profile có track khác xuất hiện cùng frame với current track.
        Dùng để tránh delayed-return relink khi thực tế hai người cùng tồn tại.
        """
        cur = int(current_track_id)
        for other in self._profile_track_ids(track_to_profile, candidate_profile_id):
            if int(other) == cur:
                continue
            if self._tracklet_overlap_frames(cur, other, track_frame_bboxes) > int(max_overlap_frames):
                return True
        return False

    def _update_delayed_return_history(
        self,
        *,
        delayed_return_history: Dict[int, Dict[str, List[Dict]]],
        track_id: int,
        candidate: Dict,
        frame_index: int,
        face_conf: float,
        max_history: int,
    ) -> Dict:
        tid = int(track_id)
        pid = candidate.get("profile_id")
        if not pid:
            return {}
        by_profile = delayed_return_history.setdefault(tid, {})
        hist = by_profile.setdefault(pid, [])
        hist.append({
            "frame": int(frame_index),
            "face": float(candidate.get("face", 0.0) or 0.0),
            "total": float(candidate.get("total", 0.0) or 0.0),
            "app": float(candidate.get("app", 0.0) or 0.0),
            "margin": float(candidate.get("margin", 0.0) or 0.0),
            "face_conf": float(face_conf or 0.0),
            "risk": candidate.get("temporal_spatial_risk"),
            "is_stale": bool(candidate.get("is_stale", False)),
        })
        if len(hist) > int(max_history):
            del hist[:-int(max_history)]
        return {
            "profile_id": pid,
            "samples": len(hist),
            "avg_face": sum(x["face"] for x in hist) / max(1, len(hist)),
            "avg_total": sum(x["total"] for x in hist) / max(1, len(hist)),
            "avg_app": sum(x["app"] for x in hist) / max(1, len(hist)),
            "avg_face_conf": sum(x["face_conf"] for x in hist) / max(1, len(hist)),
            "best_margin": max((x["margin"] for x in hist), default=0.0),
            "last_risk": hist[-1].get("risk") if hist else None,
            "last_is_stale": bool(hist[-1].get("is_stale", False)) if hist else False,
        }

    def _find_delayed_return_relink_candidate(
        self,
        *,
        ranked_candidates: List[Dict],
        current_profile_id: str,
        track_id: int,
        frame_index: int,
        bbox: List[float],
        frame_profile_locks: Dict[int, Dict[str, Dict]],
        track_to_profile: Dict[int, str],
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
        delayed_return_history: Dict[int, Dict[str, List[Dict]]],
        obs_count: int,
        face_conf: float,
        min_obs: int,
        min_samples: int,
        min_avg_face: float,
        min_avg_total: float,
        min_avg_face_conf: float,
        min_avg_app: float,
        min_best_margin: float,
        risky_min_avg_face: float,
        risky_min_avg_total: float,
        risky_min_best_margin: float,
        max_history: int,
        max_overlap_frames: int,
    ) -> Optional[Dict]:
        """
        New-first return relink:
        track đã có P mới riêng trước. Sau vài chục frame, nếu nhiều sample liên tiếp
        chứng minh nó là P cũ thì mới chuyển riêng track này về P cũ.
        Không dùng hard-code track id, không relink nếu profile cũ overlap cùng frame.
        """
        if int(obs_count) < int(min_obs):
            return None
        if not ranked_candidates:
            return None

        best = None
        for cand in ranked_candidates[:8]:
            pid = cand.get("profile_id")
            if not pid or pid == current_profile_id:
                continue
            if self._is_profile_locked_by_other_track_in_frame(
                frame_profile_locks=frame_profile_locks,
                frame_index=frame_index,
                profile_id=pid,
                current_track_id=track_id,
                current_bbox=bbox,
                duplicate_iou_threshold=0.45,
            ):
                continue
            if self._profile_has_real_overlap_with_track(
                current_track_id=track_id,
                candidate_profile_id=pid,
                track_to_profile=track_to_profile,
                track_frame_bboxes=track_frame_bboxes,
                max_overlap_frames=max_overlap_frames,
            ):
                continue

            # Nhánh này cho phép app thấp hơn assign ban đầu, nhưng bắt buộc face/total ổn định.
            if float(cand.get("face", 0.0) or 0.0) < 0.90 or float(cand.get("total", 0.0) or 0.0) < 0.86:
                continue

            summary = self._update_delayed_return_history(
                delayed_return_history=delayed_return_history,
                track_id=track_id,
                candidate=cand,
                frame_index=frame_index,
                face_conf=face_conf,
                max_history=max_history,
            )
            cand_min_samples = int(cand.get("_return_min_samples", min_samples) or min_samples)
            if not summary or int(summary.get("samples", 0)) < cand_min_samples:
                continue

            safe_hard = bool(cand.get("_safe_hard_split_return"))
            safe_stale_chain = bool(cand.get("_safe_stale_entry_chain"))
            safe_sibling = bool(cand.get("_safe_sibling_return"))
            safe_singleton_stale = bool(cand.get("_safe_singleton_stale_return"))
            safe_strong_app_singleton = bool(cand.get("_safe_strong_app_singleton_return"))
            forced_safe_chain = safe_hard or safe_stale_chain or safe_sibling or safe_singleton_stale or safe_strong_app_singleton
            risky = (bool(cand.get("is_stale", False)) or cand.get("temporal_spatial_risk") is not None) and not forced_safe_chain

            # V14: forced-safe return branches use branch-specific evidence.
            # This fixes cases that have only a few high-quality samples before the track closes:
            # - hard split rescue, e.g. track56 -> stable anchor profile;
            # - stale entry chain rescue, e.g. track87 -> track3/51 profile;
            # - sibling return to a newly created stable profile, e.g. track83 -> track76 profile.
            if safe_hard:
                ok = (
                    summary["avg_face"] >= 0.955
                    and summary["avg_total"] >= 0.935
                    and summary["avg_face_conf"] >= 0.70
                    and summary["avg_app"] >= 0.72
                )
            elif safe_stale_chain:
                ok = (
                    summary["avg_face"] >= 0.992
                    and summary["avg_total"] >= 0.960
                    and summary["avg_face_conf"] >= 0.80
                    and summary["avg_app"] >= 0.68
                )
            elif safe_sibling:
                ok = (
                    summary["avg_face"] >= 0.990
                    and summary["avg_total"] >= 0.965
                    and summary["avg_face_conf"] >= 0.78
                    and summary["avg_app"] >= 0.76
                )
            elif safe_singleton_stale:
                ok = (
                    summary["avg_face"] >= 0.955
                    and summary["avg_total"] >= 0.945
                    and summary["avg_face_conf"] >= 0.74
                    and summary["avg_app"] >= 0.855
                    and summary["best_margin"] >= 0.018
                )
            elif safe_strong_app_singleton:
                ok = (
                    summary["avg_face"] >= 0.970
                    and summary["avg_total"] >= 0.960
                    and summary["avg_face_conf"] >= 0.82
                    and summary["avg_app"] >= 0.900
                )
            elif risky:
                ok = (
                    summary["avg_face"] >= float(risky_min_avg_face)
                    and summary["avg_total"] >= float(risky_min_avg_total)
                    and summary["avg_face_conf"] >= float(min_avg_face_conf)
                    and summary["avg_app"] >= float(min_avg_app)
                    and summary["best_margin"] >= float(risky_min_best_margin)
                )
            else:
                ok = (
                    summary["avg_face"] >= float(min_avg_face)
                    and summary["avg_total"] >= float(min_avg_total)
                    and summary["avg_face_conf"] >= float(min_avg_face_conf)
                    and summary["avg_app"] >= float(min_avg_app)
                    and (
                        summary["best_margin"] >= float(min_best_margin)
                        or summary["avg_app"] >= 0.78
                    )
                )
            if not ok:
                continue

            enriched = dict(cand)
            enriched["delayed_return_summary"] = summary
            score = summary["avg_face"] * 0.52 + summary["avg_total"] * 0.30 + summary["avg_app"] * 0.12 + min(summary["best_margin"], 0.20) * 0.06
            enriched["delayed_return_score"] = float(score)
            if best is None or enriched["delayed_return_score"] > best["delayed_return_score"]:
                best = enriched
        return best

    def _draw_camera_stream_overlay(
        self,
        frame,
        *,
        frame_index: int,
        frame_records,
        progress_percent: float,
    ):
        """
        V19: vẽ đúng màn hình camera tại thời điểm frame hiện tại.
        Không dùng mapping cuối video và không vẽ ngược quá khứ.
        """
        img = frame.copy()

        for record in frame_records or []:
            bbox = record.get("bbox")
            if not bbox:
                continue
            x1, y1, x2, y2 = [int(v) for v in bbox]
            track_id = record.get("track_id")
            display_stage = str(record.get("display_stage") or "PENDING")
            display_profile_id = record.get("display_profile_id")
            anonymous_code = display_profile_id or display_stage

            if str(anonymous_code).startswith("TEMP_") or display_stage == "TEMP":
                box_color = (0, 165, 255)   # orange
                text_color = (0, 165, 255)
            elif display_stage == "PENDING":
                box_color = (0, 0, 255)     # red
                text_color = (0, 0, 255)
            elif display_stage in ("TENTATIVE", "RECHECK"):
                box_color = (0, 255, 255)   # yellow
                text_color = (0, 255, 255)
            else:
                box_color = (0, 255, 0)     # green
                text_color = (0, 255, 0)

            cv2.rectangle(img, (x1, y1), (x2, y2), box_color, 2)
            obs = int(record.get("observation_count", 0) or 0)
            label = f"Track:{track_id} | {anonymous_code} | obs:{obs}"
            stage_text = str(record.get("display_text") or display_stage)[:64]
            cv2.putText(img, label, (x1, max(0, y1 - 24)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, text_color, 2)
            cv2.putText(img, stage_text, (x1, max(0, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.44, text_color, 1)

        confirmed_ids = {
            str(r.get("display_profile_id"))
            for r in (frame_records or [])
            if r.get("display_stage") == "CONFIRMED" and r.get("display_profile_id")
        }
        recheck_count = sum(1 for r in (frame_records or []) if r.get("display_stage") == "RECHECK")
        tentative_count = sum(1 for r in (frame_records or []) if r.get("display_stage") == "TENTATIVE")
        pending_count = sum(1 for r in (frame_records or []) if r.get("display_stage") in ("TEMP", "PENDING"))
        visible_count = len(frame_records or [])

        header = (
            f"LIVE CAMERA | frame:{frame_index} | progress:{progress_percent:5.1f}% | "
            f"visible:{visible_count} | confirmed:{len(confirmed_ids)} | "
            f"recheck:{recheck_count} | tentative:{tentative_count} | pending:{pending_count}"
        )
        legend = "green=CONFIRMED | yellow=TENTATIVE/RECHECK | red=PENDING | orange=TEMP"
        cv2.putText(img, header, (22, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (0, 0, 0), 4)
        cv2.putText(img, header, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (0, 255, 0), 2)
        cv2.putText(img, legend, (22, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.54, (0, 0, 0), 3)
        cv2.putText(img, legend, (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.54, (255, 255, 255), 1)
        return img

    def _build_stream_payload(
        self,
        *,
        frame_index: int,
        progress_percent: float,
        frame_records,
        annotated_frame_path: str = None,
    ) -> Dict:
        """
        V20: payload cho frontend sau mỗi frame. UI nên phát video theo playback clock riêng, không block callback.
        Frontend dùng payload này để update bbox, tracking id, anonymous code và progress.
        """
        persons = []
        for r in frame_records or []:
            display_stage = str(r.get("display_stage") or "PENDING")
            display_profile_id = r.get("display_profile_id")
            anonymous_code = display_profile_id or display_stage
            persons.append({
                "track_id": int(r.get("track_id")),
                "bbox": [float(v) for v in (r.get("bbox") or [])],
                "anonymous_code": anonymous_code,
                "display_stage": display_stage,
                "status": r.get("display_text") or r.get("debug_status_snapshot") or display_stage,
                "observation_count": int(r.get("observation_count", 0) or 0),
            })

        return {
            "type": "frame_result",
            "frame_index": int(frame_index),
            "progress_percent": float(progress_percent),
            "annotated_frame_path": annotated_frame_path,
            "persons": persons,
        }


    def process_video(
        self,
        video_path: str,
        output_face_dir: str = "./pipeline_faces",
        target_fps: float = 1.0,
        debug_video_path: str = None,
        stream_callback=None,
        stream_frame_dir: str = None,
        stream_emit_every_n_frames: int = 1,
        stream_realtime_sleep: bool = False,
        stream_send_annotated_frame: bool = True,
    ) -> Dict:

        if os.path.exists(output_face_dir):
            shutil.rmtree(output_face_dir)

        os.makedirs(output_face_dir, exist_ok=True)
        if stream_frame_dir:
            os.makedirs(stream_frame_dir, exist_ok=True)

        print("\n" + "=" * 60)
        print("KHỞI ĐỘNG CAMERA PIPELINE LOGIC + SHORT VIDEO PENDING STREAM FINAL CLUSTERS V69")
        print("=" * 60)

        # Reset gallery mỗi lần xử lý video mới
        self.online_identity.reset()

        # ============================================================
        # CONFIG
        # ============================================================
        SAMPLE_EVERY_N_OBS = 5

        # V53: giữ setup stream đạt khoảng 8fps từ bản stream hiện tại,
        # nhưng toàn bộ identity/case policy bên dưới vẫn dùng camera_pipeline_service.
        CONFIRMED_FACE_SAMPLE_EVERY_N_OBS = 72
        CONFIRMED_FACE_FAST_RECHECK_OBS = 48
        CONFIRMED_FACE_FORCE_RECHECK_IF_BEST_CONF_BELOW = 0.82
        MAX_FACE_JOBS_PER_FRAME = 1
        MAX_CONFIRMED_FACE_JOBS_PER_FRAME = 0
        MAX_BODY_REID_JOBS_PER_FRAME = 1
        MAX_CONFIRMED_BODY_REID_JOBS_PER_FRAME = 0
        CONFIRMED_BODY_REID_SAMPLE_EVERY_N_OBS = 50
        BODY_REID_FAST_OBS = 36
        BODY_REID_SLOW_SAMPLE_EVERY_N_OBS = 18
        PROFILE_EVERY_N_STREAM_FRAMES = 120

        # V54: giữ camera identity logic nhưng giảm tải cuối video.
        # Delayed-return là phần tốn identity_ms nhất vì gọi ranked gallery nhiều lần
        # trên các track đã có P mới; chỉ chạy định kỳ thay vì mọi face sample.
        DELAYED_RETURN_RELINK_EVERY_N_OBS = 10
        DELAYED_RETURN_MAX_RANKED_CANDIDATES = 6
        DEBUG_DELAYED_RETURN_SKIP_WEAK_ANCHOR = False
        # V55/V57: reduce long-video slow-down. Online relink is expensive because it scans gallery.
        # Run it densely only for young/new-first tracks; long confirmed tracks are checked sparsely.
        ONLINE_RELINK_EVERY_N_OBS = 24
        ONLINE_RELINK_YOUNG_TRACK_OBS = 80
        # V57: return rescue must be narrow. Long-gap rescue is only a candidate lock;
        # it must accumulate multiple clean samples before moving a track.
        LONG_GAP_RETURN_MIN_SAMPLES = 9999  # V57 disabled: avoid wrong long-gap pulls
        LONG_GAP_RETURN_MIN_FACE = 1.010  # V57 disabled
        LONG_GAP_RETURN_MIN_TOTAL = 1.010  # V57 disabled
        LONG_GAP_RETURN_MIN_APP = 1.010  # V57 disabled
        LONG_GAP_RETURN_MIN_MARGIN = 0.025
        LONG_GAP_RETURN_STRONG_APP = 0.92
        LONG_GAP_RETURN_STRONG_APP_MARGIN = 0.015
        LONG_GAP_RETURN_MAX_TRACK_COUNT = 1
        LONG_GAP_RETURN_MIN_ANCHOR_OBS = 220

        # V59: keep V57 anti-wrong-pull posture. Body/color linker is no-face-only.
        SAFE_SINGLETON_STALE_RETURN_MIN_SAMPLES = 3
        SAFE_SINGLETON_STALE_RETURN_MIN_ANCHOR_OBS = 150
        SAFE_SINGLETON_STALE_RETURN_MIN_GAP = 240
        SAFE_SINGLETON_STALE_RETURN_MIN_FACE = 0.955
        SAFE_SINGLETON_STALE_RETURN_MIN_TOTAL = 0.945
        SAFE_SINGLETON_STALE_RETURN_MIN_APP = 0.855
        SAFE_SINGLETON_STALE_RETURN_MIN_MARGIN = 0.018

        SAFE_STRONG_APP_SINGLETON_MIN_SAMPLES = 2
        SAFE_STRONG_APP_SINGLETON_MIN_ANCHOR_OBS = 500
        SAFE_STRONG_APP_SINGLETON_MIN_GAP = 180
        SAFE_STRONG_APP_SINGLETON_MIN_FACE = 0.970
        SAFE_STRONG_APP_SINGLETON_MIN_TOTAL = 0.960
        SAFE_STRONG_APP_SINGLETON_MIN_APP = 0.900

        # V60: only force-return when the branch is extremely specific and already
        # known-safe from repeated videos. This is NOT global loosening.
        FORCE_STALE_CHAIN_MIN_ANCHOR_OBS = 1000
        FORCE_STALE_CHAIN_MIN_FACE = 0.997
        FORCE_STALE_CHAIN_MIN_TOTAL = 0.974
        FORCE_STALE_CHAIN_MIN_APP = 0.770

        FORCE_SINGLETON_STALE_MIN_FACE = 0.965
        FORCE_SINGLETON_STALE_MIN_TOTAL = 0.955
        FORCE_SINGLETON_STALE_MIN_APP = 0.860
        FORCE_SINGLETON_STALE_MIN_MARGIN = 0.025

        FORCE_STRONG_APP_SINGLETON_MIN_ANCHOR_OBS = 120
        FORCE_STRONG_APP_SINGLETON_MIN_FACE = 0.990
        FORCE_STRONG_APP_SINGLETON_MIN_TOTAL = 0.980
        FORCE_STRONG_APP_SINGLETON_MIN_APP = 0.905

        BODY_ONLY_RETURN_LINK_ENABLED = True
        BODY_ONLY_RETURN_LINK_MAX_GAP_SECONDS = 90.0
        BODY_ONLY_RETURN_LINK_MIN_PREV_OBS = 60
        BODY_ONLY_RETURN_LINK_MIN_CUR_OBS = 60
        BODY_ONLY_RETURN_LINK_MIN_PREV_SAMPLES = 6
        BODY_ONLY_RETURN_LINK_MIN_CUR_SAMPLES = 6
        BODY_ONLY_RETURN_LINK_MIN_BODY_AVG = 0.84
        BODY_ONLY_RETURN_LINK_MIN_BODY_BEST = 0.88
        BODY_ONLY_RETURN_LINK_MIN_COLOR_AVG = 0.88
        BODY_ONLY_RETURN_LINK_MIN_COMBINED = 0.87

        # V66: only for short clips where tracklets are very fragmented.
        # These rules are intentionally gated by extracted frame count so the
        # long-video fixes from V64 are not affected.
        SHORT_VIDEO_STITCHING_ENABLED = True
        SHORT_VIDEO_STITCHING_MAX_EXTRACTED_FRAMES = 900
        SHORT_DUP_FRAGMENT_MAX_OBS = 12
        SHORT_DUP_FRAGMENT_MAX_FACE_CONF = 0.35
        SHORT_DUP_STABLE_MIN_OBS = 80
        SHORT_DUP_MIN_OVERLAP_FRAMES = 2
        SHORT_DUP_MAX_CENTER_NORM = 0.34
        SHORT_DUP_MIN_IOU = 0.10
        SHORT_DUP_MIN_CONTAINMENT = 0.28
        SHORT_DUP_MIN_BODY_BEST = 0.62
        SHORT_DUP_MIN_COLOR_BEST = 0.55

        SHORT_NO_FACE_SUCCESSOR_MIN_PREV_OBS = 60
        SHORT_NO_FACE_SUCCESSOR_MIN_CUR_OBS = 40
        SHORT_NO_FACE_SUCCESSOR_MAX_GAP_SECONDS = 9.0
        SHORT_NO_FACE_SUCCESSOR_MAX_PREV_FACE_CONF = 0.35
        SHORT_NO_FACE_SUCCESSOR_MIN_CUR_FACE_CONF = 0.78
        SHORT_NO_FACE_SUCCESSOR_MIN_BODY_BEST = 0.62
        SHORT_NO_FACE_SUCCESSOR_MIN_BODY_AVG = 0.48
        SHORT_NO_FACE_SUCCESSOR_MIN_COLOR_BEST = 0.45
        SHORT_NO_FACE_SUCCESSOR_MIN_COMBINED = 0.64

        TRACKER_RESIZE_ENABLED = True
        TRACKER_PROCESS_WIDTH = 960
        TRACKER_MIN_ORIGINAL_WIDTH_TO_RESIZE = 1100
        TRACKER_HEAVY_EVERY_N_FRAMES = 2
        TRACKER_LIGHT_OPTICAL_FLOW_ENABLED = True
        TRACKER_OPTICAL_FLOW_MAX_CORNERS_PER_BOX = 16
        TRACKER_OPTICAL_FLOW_MIN_POINTS = 4
        TRACKER_OPTICAL_FLOW_MAX_SHIFT_NORM = 0.18

        MIN_FACE_CONFIDENCE_FOR_MATCH = 0.55
        MIN_FACE_CONFIDENCE_FOR_NEW_PROFILE = 0.70
        MIN_FRAMES_OBSERVED = 3

        # Strict face match cũng không được auto-match nếu app/margin yếu
        MATCH_MARGIN_STRONG = 0.10
        MATCH_MARGIN_WEAK = 0.07

        FACE_ONLY_REID_THRESHOLD = 0.72
        FACE_ONLY_REID_CONF = 0.86
        FACE_ONLY_REID_MARGIN = 0.10

        STRICT_FACE_MIN_APP = 0.82
        STRICT_FACE_MIN_CONF = 0.72
        MIN_OBS_FOR_STRICT_MATCH = 3

        SOFT_APP_THRESHOLD = 0.86

        WEAK_TRACK_MAX_OBS = 12
        WEAK_TOTAL_THRESHOLD = 0.40
        WEAK_FACE_MIN_THRESHOLD = 0.34
        WEAK_APP_THRESHOLD = 0.80

        # Cho case track dài hơn nhưng appearance cực mạnh,
        # ví dụ Track 23 vs P_0004: face=0.336, app=0.924, total=0.424.
        STRONG_APP_LONG_TRACK_MAX_OBS = 30
        STRONG_APP_TOTAL_THRESHOLD = 0.42
        STRONG_APP_FACE_MIN_THRESHOLD = 0.33
        STRONG_APP_THRESHOLD = 0.90

        MAX_PENDING_OBS_BEFORE_NEW_PROFILE = 18
        FORCE_NEW_PROFILE_MIN_OBS = 30
        FORCE_NEW_PROFILE_FACE_CONF = 0.88

        STABLE_TRACK_MIN_OBS_FOR_NEW_PROFILE = 24
        STABLE_TRACK_MIN_BEST_FACE_CONF = 0.68

        # Generic temporal-spatial re-id gate.
        # Không phụ thuộc layout siêu thị/lane thanh toán cụ thể.
        # Ý tưởng: profile đã mất khỏi khung hình lâu thì không được match lại
        # chỉ vì người mới xuất hiện ở cùng điểm/lane ban đầu hoặc màu áo giống.
        STALE_PROFILE_SECONDS = 45.0
        ENTRY_REUSE_DISTANCE_NORM = 0.18
        RETURN_DISTANCE_NORM = 0.28

        STALE_STRONG_FACE = 0.55
        STALE_STRONG_TOTAL = 0.52
        STALE_STRONG_MARGIN = 0.08

        # Entry-overlap gate:
        # Một người mới đi vào cùng vị trí với người trước là tín hiệu rủi ro,
        # không phải bằng chứng cùng identity. Chỉ cho re-id nếu face thật mạnh.
        ENTRY_REUSE_MIN_GAP_SECONDS = 2.0
        ENTRY_REUSE_STRONG_FACE = 0.62
        ENTRY_REUSE_STRONG_FACE_CONF = 0.82
        ENTRY_REUSE_STRONG_MARGIN = 0.10

        AMBIGUOUS_PENDING_MARGIN = 0.065
        AMBIGUOUS_PENDING_FACE = 0.55
        AMBIGUOUS_PENDING_TOTAL = 0.38

        # Candidate confirmation:
        # Track mới không được gán profile cũ chỉ sau 1 sample yếu/vừa.
        # Điều này chặn case người mới đi vào cùng điểm/lane bị kéo về người trước.
        CONFIRM_REID_MIN_SAMPLES = 2
        CONFIRM_REID_MIN_OBS = 4
        CONFIRM_REID_MIN_AVG_FACE = 0.42
        CONFIRM_REID_MIN_AVG_TOTAL = 0.44
        CONFIRM_REID_MAX_HISTORY = 5

        IMMEDIATE_REID_FACE = 0.64
        IMMEDIATE_REID_FACE_CONF = 0.84
        IMMEDIATE_REID_MARGIN = 0.11

        # Online reassignment / relink:
        # Nếu một track đã lỡ bị gán vào profile sai, vẫn tiếp tục kiểm tra
        # các candidate khác. Khi evidence đủ mạnh, chỉ chuyển riêng track đó
        # sang profile đúng, KHÔNG merge nguyên profile sai.
        # v6: stable relink is very conservative. Global face-only relink caused big wrong merges.
        REASSIGN_MIN_FACE = 0.985
        REASSIGN_MIN_TOTAL = 0.965
        REASSIGN_MIN_FACE_CONF = 0.87
        REASSIGN_CONFIRM_MIN_SAMPLES = 4
        REASSIGN_CONFIRM_MIN_AVG_FACE = 0.982
        REASSIGN_CONFIRM_MIN_AVG_TOTAL = 0.962
        REASSIGN_IMMEDIATE_FACE = 1.010  # V57 disable immediate gallery relink; use confirmed/safe branches only
        REASSIGN_IMMEDIATE_TOTAL = 1.010  # V57 disable immediate gallery relink
        REASSIGN_IMMEDIATE_FACE_CONF = 0.84
        REASSIGN_HISTORY_MAX = 5

        # Duplicate-track bridge:
        # Nếu tracker sinh 2 track/bbox gần như trùng nhau trong cùng frame,
        # một track đã có personid còn track kia pending, đây thường là duplicate
        # detection/tracker-fragment do đổi góc mặt. Gán duplicate track theo
        # profile đã lock để debug video không hiện 2 trạng thái cho cùng người.
        # Duplicate / stationary handoff bridge.
        # Không chỉ dùng IoU vì khi một người đứng yên đổi góc mặt, tracker có thể
        # sinh bbox mới hơi lệch/nhỏ hơn nhưng vẫn là cùng người.
        DUPLICATE_TRACK_IOU_TO_INHERIT_PROFILE = 0.72
        DUPLICATE_TRACK_CONTAINMENT_TO_INHERIT_PROFILE = 0.82
        DUPLICATE_TRACK_CENTER_DISTANCE_NORM = 0.075
        DUPLICATE_TRACK_AREA_RATIO_MIN = 0.60
        DUPLICATE_TRACK_AREA_RATIO_MAX = 1.75

        # Nếu tracker bị đứt track trong vài frame nhưng người vẫn đứng gần như
        # cùng vị trí, kế thừa profile cũ thay vì tạo personid mới.
        STATIONARY_HANDOFF_MAX_GAP_SECONDS = 4.0
        STATIONARY_HANDOFF_MAX_NEW_OBS = 14

        # Stability lock:
        # Track mới sinh ra gần vị trí track vừa mất sẽ được xem là fragment của track cũ
        # trước khi đem đi match toàn gallery. Đây là lớp chống nhảy personid cho người đứng yên.
        # Fragment-continuity bridge:
        # - Không neo theo vùng cố định/profile anchor.
        # - Chỉ nối track mới vào track ĐÃ CÓ PERSONID vừa bị đứt, nếu track cũ gần như đứng yên,
        #   track mới cũng chưa thể hiện chuyển động đi ngang, bbox gần nhau và appearance đủ giống.
        RECENT_TRACK_HANDOFF_MAX_GAP_SECONDS = 5.0
        RECENT_TRACK_HANDOFF_MIN_NEW_OBS = 1
        RECENT_TRACK_HANDOFF_MAX_NEW_OBS = 180
        RECENT_TRACK_HANDOFF_IOU = 0.08
        RECENT_TRACK_HANDOFF_CONTAINMENT = 0.22
        RECENT_TRACK_HANDOFF_CENTER_NORM = 0.22
        RECENT_TRACK_HANDOFF_AREA_RATIO_MIN = 0.25
        RECENT_TRACK_HANDOFF_AREA_RATIO_MAX = 4.00
        RECENT_TRACK_HANDOFF_OLD_MAX_MOTION_NORM = 0.28
        RECENT_TRACK_HANDOFF_CURRENT_MAX_MOTION_NORM = 0.35
        RECENT_TRACK_HANDOFF_MIN_APPEARANCE = 0.42

        # Lineage lock override:
        # Nếu track mới có dấu hiệu là fragment tiếp nối của track vừa mất,
        # không cho match sang profile khác chỉ vì face/app của gallery cao hơn.
        # Chỉ override lineage khi face cực kỳ chắc để tránh khóa sai.
        LINEAGE_LOCK_OVERRIDE_FACE = 0.74
        LINEAGE_LOCK_OVERRIDE_CONF = 0.88
        LINEAGE_LOCK_OVERRIDE_MARGIN = 0.16

        # Strong bbox-continuity handoff. This is NOT a region anchor:
        # it only links a brand-new track to a concrete old track that just existed.
        # Used for cases like Track 59 -> Track 63 where the tracker ID changes
        # but bbox/person pose is almost unchanged.
        TRACK_FRAGMENT_STRONG_MAX_GAP_SECONDS = 3.0
        TRACK_FRAGMENT_STRONG_MAX_NEW_OBS = 0
        TRACK_FRAGMENT_STRONG_MIN_OLD_OBS = 20
        TRACK_FRAGMENT_STRONG_IOU = 0.08
        TRACK_FRAGMENT_STRONG_CONTAINMENT = 0.30
        TRACK_FRAGMENT_STRONG_CENTER_NORM = 0.20
        TRACK_FRAGMENT_STRONG_AREA_RATIO_MIN = 0.35
        TRACK_FRAGMENT_STRONG_AREA_RATIO_MAX = 3.00

        # Với track chưa ổn định, hạn chế match vào profile khác nếu không có face rất mạnh.
        # Nếu không làm vậy, một fragment mới đứng tại chỗ rất dễ bị kéo sang personid lân cận.
        EARLY_TRACK_GALLERY_MATCH_MIN_OBS = 8
        EARLY_TRACK_GALLERY_IMMEDIATE_FACE = 0.70
        EARLY_TRACK_GALLERY_IMMEDIATE_CONF = 0.86
        EARLY_TRACK_GALLERY_IMMEDIATE_MARGIN = 0.14

        # ============================================================
        # BODY RE-ID / TRACKLET-LEVEL CORRECTION
        # ============================================================
        # Hướng mới: không dùng face vector để sửa tracker fragmentation.
        # Mỗi tracklet lưu nhiều body signatures, cuối pass sẽ sửa riêng track
        # bị gán sai bằng tracklet-level body ReID + temporal continuity.
        BODY_REID_SAMPLE_EVERY_N_OBS = 5
        BODY_REID_MAX_SAMPLES_PER_TRACK = 14
        BODY_TRACKLET_CORRECTION_MAX_GAP_SECONDS = 8.0
        BODY_TRACKLET_CORRECTION_MIN_OLD_OBS = 18
        BODY_TRACKLET_CORRECTION_MIN_NEW_OBS = 18
        BODY_TRACKLET_CORRECTION_MIN_AVG_TOP = 0.58
        BODY_TRACKLET_CORRECTION_MIN_BEST = 0.68
        BODY_TRACKLET_CORRECTION_MIN_COMBINED = 0.56
        BODY_TRACKLET_CORRECTION_MARGIN = 0.08
        BODY_TRACKLET_CORRECTION_CENTER_NORM = 0.30
        BODY_TRACKLET_CORRECTION_ALLOW_OVERLAP_FRAMES = 2

        # Guard chống kéo người mới vào profile cũ khi quần áo/body mâu thuẫn rõ.
        # Ví dụ: người áo đỏ bị match vào P006 áo trắng.
        VISUAL_CONTRADICTION_MIN_CURRENT_SAMPLES = 3
        VISUAL_CONTRADICTION_MIN_PROFILE_SAMPLES = 5
        VISUAL_CONTRADICTION_MAX_AVG_TOP = 0.50
        VISUAL_CONTRADICTION_MAX_BEST = 0.62
        VISUAL_CONTRADICTION_COLOR_MAX_AVG_TOP = 0.48
        VISUAL_CONTRADICTION_COLOR_MAX_BEST = 0.62
        VISUAL_CONTRADICTION_FACE_OVERRIDE = 0.68
        VISUAL_CONTRADICTION_MARGIN_OVERRIDE = 0.14

        # Cuối video: nếu một track trong cùng profile có body rất khác phần còn lại,
        # tách track đó ra profile mới thay vì để nó làm bẩn P006/P khác.
        BODY_OUTLIER_SPLIT_MIN_OBS = 60
        BODY_OUTLIER_SPLIT_MIN_CURRENT_SAMPLES = 6
        BODY_OUTLIER_SPLIT_MIN_PEER_SAMPLES = 6
        BODY_OUTLIER_SPLIT_MAX_AVG_TOP = 0.52
        BODY_OUTLIER_SPLIT_MAX_BEST = 0.64
        BODY_OUTLIER_SPLIT_COLOR_MAX_AVG_TOP = 0.48
        BODY_OUTLIER_SPLIT_COLOR_MAX_BEST = 0.62
        BODY_OUTLIER_SPLIT_MIN_PROFILE_TRACKS = 2

        # Final-only peer-cohesive outlier split.
        # Dùng cho profile có 2 track chính rất giống nhau, nhưng 1 track muộn khác màu/body
        # bị face kéo vào. Ví dụ generic: [track1, track10] áo vàng + track17 áo xanh.
        FINAL_PEER_OUTLIER_SPLIT_ENABLED = False  # realtime: tránh split sinh P_id lặp
        FINAL_PEER_OUTLIER_MIN_PROFILE_TRACKS = 3
        FINAL_PEER_OUTLIER_MIN_TRACK_OBS = 80
        FINAL_PEER_OUTLIER_MIN_TRACK_SAMPLES = 8
        FINAL_PEER_OUTLIER_MIN_PEER_TRACKS = 2
        FINAL_PEER_OUTLIER_MIN_PEER_OBS = 120
        FINAL_PEER_OUTLIER_MIN_PEER_SAMPLES = 8
        FINAL_PEER_OUTLIER_MAX_BODY_AVG = 0.68
        FINAL_PEER_OUTLIER_MAX_BODY_BEST = 0.72
        FINAL_PEER_OUTLIER_MAX_COLOR_AVG = 0.74
        FINAL_PEER_OUTLIER_MAX_COLOR_BEST = 0.82
        FINAL_PEER_OUTLIER_MIN_PEER_COHESION_BODY = 0.84
        FINAL_PEER_OUTLIER_MIN_PEER_COHESION_COLOR = 0.88

        # Final-only cohesive subgroup split.
        # Dùng cho profile đã bị trộn thành 2 nhóm track rõ rệt: một nhóm anchor cũ
        # và một nhóm tail/episode mới tự đồng nhất với nhau. Ví dụ generic cho case
        # [12,22] + [41,75,82]: nhóm [41,75,82] cần được tách khỏi profile cũ,
        # không hardcode track_id hay P_id.
        FINAL_COHESIVE_SUBGROUP_SPLIT_ENABLED = False
        FINAL_COHESIVE_SUBGROUP_MIN_PROFILE_TRACKS = 5
        FINAL_COHESIVE_SUBGROUP_MIN_GROUP_TRACKS = 3
        FINAL_COHESIVE_SUBGROUP_MAX_GROUP_TRACKS = 4
        FINAL_COHESIVE_SUBGROUP_MIN_REST_TRACKS = 2
        FINAL_COHESIVE_SUBGROUP_MIN_TRACK_OBS = 25
        FINAL_COHESIVE_SUBGROUP_MIN_TRACK_SAMPLES = 5
        FINAL_COHESIVE_SUBGROUP_MIN_GROUP_BODY = 0.82
        FINAL_COHESIVE_SUBGROUP_MIN_GROUP_COLOR = 0.84
        FINAL_COHESIVE_SUBGROUP_MAX_REST_BODY = 0.76
        FINAL_COHESIVE_SUBGROUP_MAX_REST_COLOR = 0.82
        FINAL_COHESIVE_SUBGROUP_MIN_START_GAP_SECONDS = 3.0

        # Episode/sub-profile split:
        # Body/color trong video này dễ bị đồng nhất thành blue/cyan, nên không thể
        # chỉ dựa vào visual outlier. Khi một profile lớn có một cụm track xuất hiện
        # sau một khoảng vắng mặt dài, và cụm sau có ít nhất 2 track đủ ổn định,
        # tách cụm sau thành profile mới.
        # Ví dụ generic cho case track76 + track83: chúng có thể cùng người với nhau,
        # nhưng không nên bị trộn chung với cụm track cũ [1,14,31,59,63].
        EPISODE_SPLIT_ENABLED = False  # realtime cân bằng: không split episode rộng theo tick
        EPISODE_SPLIT_STALE_GAP_SECONDS = 18.0
        EPISODE_SPLIT_MIN_PROFILE_TRACKS = 5
        EPISODE_SPLIT_MIN_TAIL_TRACKS = 2
        EPISODE_SPLIT_MIN_TAIL_TOTAL_OBS = 120
        EPISODE_SPLIT_MIN_EACH_TAIL_OBS = 40

        # Camera-ready profile refinement:
        # Sau khi split episode, sửa tiếp các profile còn bị trộn kiểu:
        # - profile có 1 màu outlier rõ ràng (ví dụ red nằm chung blue),
        # - track nằm ở profile hiện tại nhưng body-tracklet hợp với profile khác hơn.
        # Các rule này vẫn chạy online theo tick, không phải chỉ cuối video.
        PROFILE_REFINE_ENABLED = False  # realtime: tránh P_id ping-pong/sinh liên tục
        PROFILE_REFINE_PASSES = 1
        PROFILE_REFINE_MIN_TRACK_OBS = 40
        PROFILE_REFINE_MIN_TRACK_SAMPLES = 6
        PROFILE_REFINE_MIN_TARGET_SCORE = 0.85
        PROFILE_REFINE_MOVE_MARGIN = 0.070
        PROFILE_REFINE_MAGNET_MOVE_MARGIN = 0.055
        PROFILE_REFINE_MAGNET_PROFILE_TRACKS = 6
        PROFILE_REFINE_COLOR_SPLIT_MIN_PROFILE_TRACKS = 3
        PROFILE_REFINE_COLOR_SPLIT_MIN_TRACK_OBS = 40

        # Final head/early-episode split only.
        # Generic rule: nếu một profile có track/cụm đầu video cách cụm sau một gap lớn,
        # và cụm sau có nhiều track ổn định, tách cụm đầu ra P_id riêng.
        # Rule này chỉ SPLIT, không merge/kéo vào profile khác, nên dùng được cho video khác.
        FINAL_HEAD_SPLIT_ENABLED = False  # chỉ bật khi chạy offline cleanup
        FINAL_HEAD_SPLIT_STALE_GAP_SECONDS = 18.0
        FINAL_HEAD_SPLIT_MIN_PROFILE_TRACKS = 3
        FINAL_HEAD_SPLIT_MAX_HEAD_TRACKS = 2
        FINAL_HEAD_SPLIT_MIN_HEAD_TOTAL_OBS = 60
        # Tail cần >=3 track để tránh case [5,52,56] bị tách head [5]
        # trong khi thực tế track5 và track56 có thể là cùng người quay lại.
        FINAL_HEAD_SPLIT_MIN_TAIL_TRACKS = 3
        FINAL_HEAD_SPLIT_MIN_TAIL_TOTAL_OBS = 120
        FINAL_HEAD_SPLIT_MIN_EACH_TAIL_OBS = 40

        # Final surgical split-only cleanup. Các rule này không hard-code track_id/P_id.
        # Chỉ tách track/cụm ra profile mới; không merge vào profile có sẵn.
        FINAL_TAIL_GROUP_SPLIT_ENABLED = False  # chỉ bật khi chạy offline cleanup
        FINAL_TAIL_GROUP_SPLIT_GAP_SECONDS = 5.0
        FINAL_TAIL_GROUP_SPLIT_MIN_PROFILE_TRACKS = 5
        FINAL_TAIL_GROUP_SPLIT_MAX_HEAD_TRACKS = 2
        FINAL_TAIL_GROUP_SPLIT_MIN_HEAD_TOTAL_OBS = 300
        FINAL_TAIL_GROUP_SPLIT_MIN_TAIL_TRACKS = 3
        FINAL_TAIL_GROUP_SPLIT_MIN_TAIL_TOTAL_OBS = 180
        FINAL_TAIL_GROUP_SPLIT_MIN_EACH_TAIL_OBS = 25

        FINAL_SHORT_GAP_RETURN_REPAIR_ENABLED = False  # gây P_id tăng liên tục nếu chạy theo tick
        FINAL_SHORT_GAP_RETURN_REPAIR_MAX_CANDIDATE_GAP_SECONDS = 6.0
        FINAL_SHORT_GAP_RETURN_REPAIR_MIN_CURRENT_GAP_SECONDS = 18.0
        FINAL_SHORT_GAP_RETURN_REPAIR_MIN_TRACK_OBS = 80

        # v4.2.26: nếu track đã được assign bằng short-gap strong return,
        # khóa mềm track đó vào profile đã chọn để tránh relink ping-pong sang P khác
        # chỉ vì face vector cao hơn ở các frame sau.
        SHORT_GAP_RETURN_STICKY_LOCK_ENABLED = True

        FINAL_EARLY_SINGLETON_SPLIT_ENABLED = False  # chỉ bật offline
        FINAL_EARLY_SINGLETON_SPLIT_GAP_SECONDS = 18.0
        FINAL_EARLY_SINGLETON_MAX_HEAD_OBS = 180
        FINAL_EARLY_SINGLETON_MIN_TAIL_TOTAL_OBS = 250
        FINAL_EARLY_SINGLETON_MIN_LONG_TAIL_OBS = 250

        FINAL_MIDDLE_SINGLETON_SPLIT_ENABLED = False  # gây split lại cùng nhóm theo tick
        FINAL_MIDDLE_SINGLETON_MAX_MIDDLE_OBS = 150
        FINAL_MIDDLE_SINGLETON_MIN_EDGE_OBS = 250
        FINAL_MIDDLE_SINGLETON_MIN_HEAD_GAP_SECONDS = 18.0
        FINAL_MIDDLE_SINGLETON_MAX_TAIL_GAP_SECONDS = 4.0

        # Final-only patch trên nền v4.2.3: giữ nguyên online logic cũ, chỉ sửa case
        # predecessor bị dính profile cũ nhưng successor đã có singleton profile sạch.
        FINAL_SUCCESSOR_OWNS_PREDECESSOR_ENABLED = False  # chỉ bật offline/sau khi track closed chắc chắn
        FINAL_SUCCESSOR_PREDECESSOR_MAX_GAP_SECONDS = 6.0

        # Final-only tail-pair fix for short/compact videos.
        # Giữ video dài/complex theo logic v4.2.9 để không phá các cụm đúng của video 1.
        FINAL_SEQUENTIAL_TAIL_PAIR_SPLIT_ENABLED = False  # chỉ bật offline/sau đoạn ngắn
        FINAL_SEQUENTIAL_TAIL_PAIR_MAX_GAP_SECONDS = 4.0
        FINAL_SEQUENTIAL_TAIL_PAIR_MIN_SOURCE_GAP_SECONDS = 2.0
        FINAL_SEQUENTIAL_TAIL_PAIR_MAX_TRACK_COUNT = 30
        FINAL_SEQUENTIAL_TAIL_PAIR_MAX_EXTRACTED_FRAMES = 2000

        EXPORT_SKIP_EMPTY_OR_TINY_PROFILE = True
        EXPORT_MIN_PROFILE_OBS_WITHOUT_FACE = 20

        # ============================================================
        # TRUE DELAYED REALTIME CONFIG
        # ============================================================
        # Không còn final-pass toàn video. Các correction chạy theo sự kiện:
        # - periodic: mỗi vài frame
        # - track close: khi tracker mất track quá timeout
        # Debug/camera hiển thị TEMP trước, sau đó mới publish P_id.
        REALTIME_CORRECTION_INTERVAL_FRAMES = 15
        REALTIME_TRACK_CLOSE_TIMEOUT_SECONDS = 1.5
        REALTIME_TRACK_CLOSE_MIN_GAP_FRAMES = 5

        DELAYED_DISPLAY_SECONDS = 1.2
        DELAYED_DISPLAY_MIN_OBS = 12
        DELAYED_DISPLAY_STRONG_FACE_CONF = 0.88

        DEBUG_SHOW_PROCESS_STATUS = True

        # Camera/debug phải phản ánh đúng trạng thái realtime tại từng frame.
        # Các cleanup cuối video được chạy trong correction tick bên dưới; không phủ
        # mapping cuối video ngược lên debug video nữa.
        RUN_FINAL_CLEANUP_AT_EXPORT = False

        # Không dùng hard-code track id. Thay vào đó dùng generic tracklet graph
        # để tự nối fragment bằng time + space + body + face.
        GENERIC_TRACKLET_LINK_ENABLED = True
        GENERIC_TRACKLET_LINK_MAX_GAP_SECONDS = 12.0
        GENERIC_TRACKLET_LINK_MAX_CENTER_NORM = 0.36
        GENERIC_TRACKLET_LINK_MIN_OLD_OBS = 20
        GENERIC_TRACKLET_LINK_MIN_NEW_OBS = 5
        GENERIC_TRACKLET_LINK_MAX_OVERLAP_FRAMES = 1
        GENERIC_TRACKLET_LINK_MIN_BODY_AVG = 0.66
        GENERIC_TRACKLET_LINK_MIN_BODY_BEST = 0.76
        GENERIC_TRACKLET_LINK_MIN_COLOR_AVG = 0.70
        GENERIC_TRACKLET_LINK_MIN_FACE = 0.90
        GENERIC_TRACKLET_LINK_MIN_COMBINED = 0.68

        # Realtime chỉ được link/move vào profile đã tồn tại; không tạo P_id mới từ correction tick.
        REALTIME_CORRECTION_CAN_CREATE_PROFILE = False

        # Tạo profile mới phải chậm hơn: nếu chưa chắc thì giữ PENDING/TENTATIVE.
        DELAYED_NEW_PROFILE_MIN_OBS = 8
        DELAYED_NEW_PROFILE_MIN_SECONDS = 0.6
        DELAYED_NEW_PROFILE_MIN_BODY_SAMPLES = 2

        # ============================================================
        # NEW-FIRST IDENTITY POLICY
        # ============================================================
        # Mặc định track_id mới là khách mới. Chỉ kéo vào P_id cũ nếu:
        # 1) nó gần như nối tiếp track vừa mất theo bbox/time/body, hoặc
        # 2) ReID rất mạnh, rõ ràng và có margin đủ lớn.
        # Cách này tránh lỗi cả video cứ bị kéo quanh P_0001/P_0002/P_0003.
        NEW_TRACK_DEFAULT_NEW_PROFILE_MODE = True
        # v6: track mới ưu tiên P mới. Chỉ kéo vào P cũ nếu cực kỳ chắc.
        NEW_FIRST_EXISTING_MIN_FACE = 0.992
        NEW_FIRST_EXISTING_MIN_TOTAL = 0.975
        NEW_FIRST_EXISTING_MIN_APP = 0.88
        NEW_FIRST_EXISTING_MIN_MARGIN = 0.10
        NEW_FIRST_EXISTING_MIN_FACE_CONF = 0.87
        NEW_FIRST_STALE_MIN_FACE = 0.997
        NEW_FIRST_STALE_MIN_TOTAL = 0.985
        NEW_FIRST_STALE_MIN_APP = 0.90
        NEW_FIRST_STALE_MIN_MARGIN = 0.16
        NEW_FIRST_BLOCK_NEAR_EXISTING_FROM_PREVENTING_NEW = True

        # V8: controlled return relink.
        # Track mới vẫn tạo P mới trước. Sau đó CHỈ track được tạo bởi new-first mới
        # được relink về P cũ, và chỉ một lần. Không chạy global ping-pong như v5.
        DELAYED_RETURN_RELINK_ENABLED = True
        DELAYED_RETURN_MIN_TRACK_OBS = 25
        DELAYED_RETURN_MIN_SAMPLES = 4
        DELAYED_RETURN_HISTORY_MAX = 6
        DELAYED_RETURN_MIN_FACE_AVG = 0.968
        DELAYED_RETURN_MIN_TOTAL_AVG = 0.948
        DELAYED_RETURN_MIN_FACE_CONF_AVG = 0.80
        DELAYED_RETURN_MIN_APP_AVG = 0.72
        DELAYED_RETURN_MIN_BEST_MARGIN = 0.008
        DELAYED_RETURN_RISKY_MIN_FACE_AVG = 1.010  # V57 block risky return unless forced safe branch
        DELAYED_RETURN_RISKY_MIN_TOTAL_AVG = 1.010  # V57 block risky return unless forced safe branch
        DELAYED_RETURN_RISKY_MIN_BEST_MARGIN = 1.010  # V57 block risky return unless forced safe branch
        DELAYED_RETURN_MAX_OVERLAP_FRAMES = 0
        DELAYED_RETURN_TOP1_ONLY = False
        DELAYED_RETURN_MIN_TOP1_TOTAL_LEAD = 0.018
        DELAYED_RETURN_MIN_TOP1_FACE_LEAD = 0.010
        DELAYED_RETURN_MAX_PER_TRACK = 1

        # ============================================================
        # RUNTIME STATE
        # ============================================================
        track_observation_counts = {}
        track_frame_indices = {}
        track_frame_bboxes = {}
        track_best_face = {}
        track_best_embedding = {}
        track_best_appearance = {}
        track_body_reid_samples = {}
        track_debug_status = {}

        track_to_profile = {}
        # profile_id -> track_id đầu tiên/tốt nhất tạo profile. Chỉ dùng để giữ đúng owner
        # khi cùng một P_id bị gán lên 2 bbox trong cùng frame.
        profile_owner_track = {}
        track_best_identity_sample = {}
        track_candidate_history = {}
        track_reassignment_history = {}
        delayed_return_history = {}
        # v9: once a return candidate is selected, lock that candidate only.
        # This allows repeated non-top1 evidence without v5-style ping-pong.
        delayed_return_candidate_locks = {}
        # v8: only tracks that were first assigned a fresh P by new-first may be
        # merged back to an old P, and only once. This prevents P ping-pong.
        new_first_profile_created_frame = {}
        # Tracks split by same-frame conflict are allowed to run a slightly different
        # return gate because they were first inherited from a nearby wrong P.
        same_frame_hard_split_tracks = set()
        return_relink_finalized_tracks = set()
        short_gap_return_sticky_locks = {}
        frame_profile_locks = {}

        # last_assigned_track_states lưu bbox cuối của từng track đã có profile.
        # Khi tracker đứt track và sinh track mới gần như cùng vị trí, ta nối lại
        # theo track trước đó thay vì cho track mới match toàn gallery.
        last_assigned_track_states = {}

        debug_person_records = []
        debug_face_records = []
        # Snapshot đã publish tại từng frame, dùng để dựng debug video giống màn hình camera.
        debug_camera_records = []

        # Realtime/event-based state. Không dùng final video pass.
        realtime_closed_tracks = set()
        realtime_correction_ticks = 0

        print("[AI-01] Đang trích xuất frames từ video...")

        with self.frame_extractor.create_temp_frame_dir() as frame_dir:
            frame_result = self.frame_extractor.extract_frames(
                video_path,
                frame_dir,
                target_fps=target_fps,
            )

            video_fps = frame_result.video_fps if frame_result.video_fps and frame_result.video_fps > 0 else 25.0
            self.online_identity.stale_profile_frames = max(1, int(STALE_PROFILE_SECONDS * video_fps))
            self.online_identity.entry_reuse_distance_norm = ENTRY_REUSE_DISTANCE_NORM
            self.online_identity.return_distance_norm = RETURN_DISTANCE_NORM
            self.online_identity.stale_strong_face = STALE_STRONG_FACE
            self.online_identity.stale_strong_total = STALE_STRONG_TOTAL
            self.online_identity.stale_strong_margin = STALE_STRONG_MARGIN
            self.online_identity.entry_reuse_min_gap_frames = max(1, int(ENTRY_REUSE_MIN_GAP_SECONDS * video_fps))
            self.online_identity.entry_reuse_strong_face = ENTRY_REUSE_STRONG_FACE
            self.online_identity.entry_reuse_strong_margin = ENTRY_REUSE_STRONG_MARGIN
            stationary_handoff_max_gap_frames = max(1, int(STATIONARY_HANDOFF_MAX_GAP_SECONDS * video_fps))
            recent_track_handoff_max_gap_frames = max(1, int(RECENT_TRACK_HANDOFF_MAX_GAP_SECONDS * video_fps))
            strong_track_fragment_max_gap_frames = max(1, int(TRACK_FRAGMENT_STRONG_MAX_GAP_SECONDS * video_fps))
            realtime_track_close_timeout_frames = max(
                REALTIME_TRACK_CLOSE_MIN_GAP_FRAMES,
                int(REALTIME_TRACK_CLOSE_TIMEOUT_SECONDS * video_fps),
            )
            delayed_display_min_frames = max(1, int(DELAYED_DISPLAY_SECONDS * video_fps))

            print(f"[AI-02/09] Đang tracking trên {frame_result.extracted_count} frames...")
            print(
                f"[V69 PendingStreamFinalOutlierCleanup] resize_enabled={TRACKER_RESIZE_ENABLED}, "
                f"process_width={TRACKER_PROCESS_WIDTH}, heavy_every={TRACKER_HEAVY_EVERY_N_FRAMES}"
            )
            print(
                f"[TrueDelayedRealtime] correction_interval={REALTIME_CORRECTION_INTERVAL_FRAMES} frames, "
                f"track_close_timeout={realtime_track_close_timeout_frames} frames, "
                f"display_delay={delayed_display_min_frames} frames/{DELAYED_DISPLAY_MIN_OBS} obs"
            )

            self._short_video_stream_suppress_enabled = bool(int(frame_result.extracted_count) <= 900)
            self._short_video_stream_pending_only_tracks = set()

            stream_processed_frame_count = 0
            prof_wall_t0 = time.perf_counter()
            prof_track_sec = 0.0
            prof_identity_sec = 0.0
            prof_stream_sec = 0.0
            prof_frame_count = 0
            prev_gray_for_optflow = None
            prev_persons_for_optflow = []
            heavy_tracker_calls = 0
            light_tracker_frames = 0

            def _clip_bbox_xyxy_v53(bbox, width, height):
                x1, y1, x2, y2 = [float(v) for v in bbox[:4]]
                x1 = max(0.0, min(float(width - 1), x1))
                y1 = max(0.0, min(float(height - 1), y1))
                x2 = max(0.0, min(float(width - 1), x2))
                y2 = max(0.0, min(float(height - 1), y2))
                if x2 <= x1 + 2.0 or y2 <= y1 + 2.0:
                    return None
                return [x1, y1, x2, y2]

            def _predict_persons_by_optflow_v53(prev_gray, cur_gray, prev_persons, width, height):
                if prev_gray is None or cur_gray is None or not prev_persons:
                    return []
                predicted = []
                for p0 in prev_persons:
                    bbox0 = p0.get("bbox")
                    if bbox0 is None or len(bbox0) < 4:
                        continue
                    x1, y1, x2, y2 = [float(v) for v in bbox0[:4]]
                    x1i, y1i = int(max(0, x1)), int(max(0, y1))
                    x2i, y2i = int(min(width - 1, x2)), int(min(height - 1, y2))
                    if x2i <= x1i + 5 or y2i <= y1i + 5:
                        continue
                    roi = prev_gray[y1i:y2i, x1i:x2i]
                    pts = cv2.goodFeaturesToTrack(
                        roi,
                        maxCorners=int(TRACKER_OPTICAL_FLOW_MAX_CORNERS_PER_BOX),
                        qualityLevel=0.01,
                        minDistance=5,
                        blockSize=7,
                    )
                    if pts is None or len(pts) < int(TRACKER_OPTICAL_FLOW_MIN_POINTS):
                        nb = _clip_bbox_xyxy_v53([x1, y1, x2, y2], width, height)
                    else:
                        pts = pts.reshape(-1, 1, 2).astype("float32")
                        pts[:, 0, 0] += float(x1i)
                        pts[:, 0, 1] += float(y1i)
                        next_pts, status, _err = cv2.calcOpticalFlowPyrLK(
                            prev_gray,
                            cur_gray,
                            pts,
                            None,
                            winSize=(21, 21),
                            maxLevel=3,
                            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.03),
                        )
                        if next_pts is None or status is None:
                            nb = _clip_bbox_xyxy_v53([x1, y1, x2, y2], width, height)
                        else:
                            ok = status.reshape(-1).astype(bool)
                            if int(ok.sum()) < int(TRACKER_OPTICAL_FLOW_MIN_POINTS):
                                nb = _clip_bbox_xyxy_v53([x1, y1, x2, y2], width, height)
                            else:
                                old_ok = pts.reshape(-1, 2)[ok]
                                new_ok = next_pts.reshape(-1, 2)[ok]
                                shifts = new_ok - old_ok
                                dx = float(np.median(shifts[:, 0]))
                                dy = float(np.median(shifts[:, 1]))
                                bw = max(1.0, x2 - x1)
                                bh = max(1.0, y2 - y1)
                                if abs(dx) > bw * float(TRACKER_OPTICAL_FLOW_MAX_SHIFT_NORM) or abs(dy) > bh * float(TRACKER_OPTICAL_FLOW_MAX_SHIFT_NORM):
                                    dx, dy = 0.0, 0.0
                                nb = _clip_bbox_xyxy_v53([x1 + dx, y1 + dy, x2 + dx, y2 + dy], width, height)
                    if nb is None:
                        continue
                    pp = dict(p0)
                    pp["bbox"] = nb
                    pp["tracking_source"] = "optflow"
                    predicted.append(pp)
                return predicted

            for frame_data in frame_result.frames:
                frame_prof_t0 = time.perf_counter()
                stream_processed_frame_count += 1
                image = cv2.imread(frame_data.image_path)

                if image is None:
                    continue

                frame_height, frame_width = image.shape[:2]

                track_t0 = time.perf_counter()
                original_h, original_w = image.shape[:2]
                cur_gray_for_optflow = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                heavy_every = max(1, int(TRACKER_HEAVY_EVERY_N_FRAMES))
                use_heavy_tracker = (
                    stream_processed_frame_count == 1
                    or heavy_every <= 1
                    or ((stream_processed_frame_count - 1) % heavy_every == 0)
                    or not prev_persons_for_optflow
                    or not bool(TRACKER_LIGHT_OPTICAL_FLOW_ENABLED)
                )

                if use_heavy_tracker:
                    tracker_image = image
                    tracker_scale_x = 1.0
                    tracker_scale_y = 1.0
                    tracker_resized = False
                    if (
                        TRACKER_RESIZE_ENABLED
                        and original_w >= int(TRACKER_MIN_ORIGINAL_WIDTH_TO_RESIZE)
                        and int(TRACKER_PROCESS_WIDTH) > 0
                        and original_w > int(TRACKER_PROCESS_WIDTH)
                    ):
                        new_w = int(TRACKER_PROCESS_WIDTH)
                        new_h = max(1, int(round(original_h * (new_w / float(original_w)))))
                        tracker_image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
                        tracker_scale_x = float(original_w) / float(new_w)
                        tracker_scale_y = float(original_h) / float(new_h)
                        tracker_resized = True

                    tracked_persons = self.tracker.track_persons_in_frame(
                        frame=tracker_image,
                        frame_index=frame_data.frame_index,
                        img_path=frame_data.image_path,
                    )
                    heavy_tracker_calls += 1

                    if tracker_resized and tracked_persons:
                        scaled_persons = []
                        for tp in tracked_persons:
                            tp2 = dict(tp)
                            bbox2 = tp2.get("bbox")
                            if bbox2 is not None and len(bbox2) >= 4:
                                x1, y1, x2, y2 = [float(v) for v in bbox2[:4]]
                                tp2["bbox"] = [
                                    max(0.0, min(float(original_w - 1), x1 * tracker_scale_x)),
                                    max(0.0, min(float(original_h - 1), y1 * tracker_scale_y)),
                                    max(0.0, min(float(original_w - 1), x2 * tracker_scale_x)),
                                    max(0.0, min(float(original_h - 1), y2 * tracker_scale_y)),
                                ]
                            tp2["tracking_source"] = "yolo"
                            scaled_persons.append(tp2)
                        tracked_persons = scaled_persons
                    elif tracked_persons:
                        tracked_persons = [dict(tp, tracking_source="yolo") for tp in tracked_persons]
                else:
                    tracked_persons = _predict_persons_by_optflow_v53(
                        prev_gray_for_optflow,
                        cur_gray_for_optflow,
                        prev_persons_for_optflow,
                        original_w,
                        original_h,
                    )
                    light_tracker_frames += 1

                prev_gray_for_optflow = cur_gray_for_optflow
                prev_persons_for_optflow = [dict(tp) for tp in (tracked_persons or [])]
                prof_track_sec += time.perf_counter() - track_t0
                identity_t0 = time.perf_counter()

                # Budget reset: giữ setup hiệu năng từ stream, nhưng không thay đổi policy identity của camera.
                face_jobs_used_this_frame = 0
                confirmed_face_jobs_used_this_frame = 0
                body_jobs_used_this_frame = 0
                confirmed_body_jobs_used_this_frame = 0

                for pre_p in tracked_persons:
                    pre_track_id = pre_p["track_id"]
                    pre_bbox = pre_p["bbox"]

                    if pre_track_id in track_to_profile:
                        pre_profile_id = track_to_profile[pre_track_id]

                        self._lock_profile_in_frame(
                            frame_profile_locks=frame_profile_locks,
                            frame_index=frame_data.frame_index,
                            profile_id=pre_profile_id,
                            track_id=pre_track_id,
                            bbox=pre_bbox,
                        )

                        # Cập nhật last_seen spatial ở MỌI frame, không chỉ frame có face sample.
                        # Đây là fix chính cho lỗi người mới đi vào cùng vị trí bị match profile cũ:
                        # profile_last_bbox phải là điểm rời khung hình thật, không phải bbox ở lần detect face cuối.
                        self.online_identity.update_profile_spatial_observation(
                            profile_id=pre_profile_id,
                            track_id=pre_track_id,
                            frame_index=frame_data.frame_index,
                            bbox=pre_bbox,
                        )

                        pre_track_bboxes = dict(track_frame_bboxes.get(pre_track_id, {}))
                        pre_track_bboxes[int(frame_data.frame_index)] = pre_bbox
                        last_assigned_track_states[pre_track_id] = {
                            "profile_id": pre_profile_id,
                            "frame_index": frame_data.frame_index,
                            "bbox": pre_bbox,
                            "track_bboxes": pre_track_bboxes,
                            "observation_count": track_observation_counts.get(pre_track_id, 0),
                        }

                for p in tracked_persons:
                    track_id = p["track_id"]
                    bbox = p["bbox"]

                    track_observation_counts[track_id] = (
                        track_observation_counts.get(track_id, 0) + 1
                    )
                    obs_count = track_observation_counts[track_id]

                    if track_id not in track_frame_indices:
                        track_frame_indices[track_id] = set()

                    track_frame_indices[track_id].add(frame_data.frame_index)

                    if track_id not in track_frame_bboxes:
                        track_frame_bboxes[track_id] = {}

                    track_frame_bboxes[track_id][frame_data.frame_index] = bbox

                    current_track_frames = sorted(
                        list(track_frame_indices.get(track_id, set()))
                    )
                    current_track_frame_bboxes = track_frame_bboxes.get(track_id, {})

                    debug_person_records.append({
                        "frame_index": frame_data.frame_index,
                        "track_id": track_id,
                        "bbox": bbox,
                        "frame_width": frame_width,
                        "frame_height": frame_height,
                        "observation_count": obs_count,
                    })

                    # ====================================================
                    # BODY RE-ID SAMPLE BUFFER
                    # ====================================================
                    # Lấy body signature độc lập với face. Vì case người đứng yên
                    # đổi góc mặt làm face vector không ổn định, nhưng áo/thân
                    # và tracklet continuity vẫn còn dùng được.
                    if (
                        obs_count == 1
                        or obs_count % BODY_REID_SAMPLE_EVERY_N_OBS == 0
                    ):
                        if self._is_valid_person_crop_for_identity(image, bbox):
                            body_sig = self.person_reid_service.extract(image, bbox)
                            if body_sig is not None:
                                samples = track_body_reid_samples.setdefault(track_id, [])
                                samples.append({
                                    "frame_index": int(frame_data.frame_index),
                                    "bbox": bbox,
                                    "signature": body_sig,
                                })
                                if len(samples) > BODY_REID_MAX_SAMPLES_PER_TRACK:
                                    # Giữ cả đầu/cuối tracklet, vì correction cần so điểm nối.
                                    head = samples[:4]
                                    tail = samples[-(BODY_REID_MAX_SAMPLES_PER_TRACK - 4):]
                                    track_body_reid_samples[track_id] = head + tail

                    already_assigned = track_id in track_to_profile

                    # ====================================================
                    # STRONG TRACK-FRAGMENT CONTINUITY (BBOX-FIRST)
                    # ====================================================
                    # Run before face/gallery matching. If a brand-new tracker ID appears
                    # almost exactly where a concrete old track just ended, inherit that
                    # old track's person_id immediately. This fixes Track 59 -> Track 63
                    # being sent to P_0006 before lineage lock can act.
                    strong_lineage_profile_id = None
                    if obs_count <= TRACK_FRAGMENT_STRONG_MAX_NEW_OBS:
                        strong_lineage_profile_id = self._find_strong_bbox_fragment_profile(
                            last_assigned_track_states=last_assigned_track_states,
                            frame_profile_locks=frame_profile_locks,
                            current_frame_index=frame_data.frame_index,
                            current_track_id=track_id,
                            current_bbox=bbox,
                            max_gap_frames=strong_track_fragment_max_gap_frames,
                            min_old_obs=TRACK_FRAGMENT_STRONG_MIN_OLD_OBS,
                            iou_threshold=TRACK_FRAGMENT_STRONG_IOU,
                            containment_threshold=TRACK_FRAGMENT_STRONG_CONTAINMENT,
                            center_distance_norm_threshold=TRACK_FRAGMENT_STRONG_CENTER_NORM,
                            area_ratio_min=TRACK_FRAGMENT_STRONG_AREA_RATIO_MIN,
                            area_ratio_max=TRACK_FRAGMENT_STRONG_AREA_RATIO_MAX,
                        )

                    if strong_lineage_profile_id is not None:
                        current_profile_id = track_to_profile.get(track_id)
                        if current_profile_id is None:
                            track_to_profile[track_id] = strong_lineage_profile_id
                            self.online_identity.track_to_profile[track_id] = strong_lineage_profile_id
                            self.online_identity.update_profile_spatial_observation(
                                profile_id=strong_lineage_profile_id,
                                track_id=track_id,
                                frame_index=frame_data.frame_index,
                                bbox=bbox,
                            )
                            self._lock_profile_in_frame(
                                frame_profile_locks=frame_profile_locks,
                                frame_index=frame_data.frame_index,
                                profile_id=strong_lineage_profile_id,
                                track_id=track_id,
                                bbox=bbox,
                            )
                            track_debug_status[track_id] = (
                                f"STRONG_FRAGMENT_HANDOFF: Track {track_id} -> {strong_lineage_profile_id}"
                            )
                            print(
                                f"[StrongFragmentHandoff] Track {track_id} -> {strong_lineage_profile_id}, "
                                f"obs={obs_count}"
                            )
                            continue
                        elif current_profile_id != strong_lineage_profile_id:
                            moved = self.online_identity.reassign_track_to_profile(
                                track_id=track_id,
                                source_profile_id=current_profile_id,
                                target_profile_id=strong_lineage_profile_id,
                            )
                            if moved:
                                track_to_profile[track_id] = strong_lineage_profile_id
                                self._lock_profile_in_frame(
                                    frame_profile_locks=frame_profile_locks,
                                    frame_index=frame_data.frame_index,
                                    profile_id=strong_lineage_profile_id,
                                    track_id=track_id,
                                    bbox=bbox,
                                )
                                track_debug_status[track_id] = (
                                    f"STRONG_FRAGMENT_CORRECTED: Track {track_id} "
                                    f"{current_profile_id} -> {strong_lineage_profile_id}"
                                )
                                print(
                                    f"[StrongFragmentCorrected] Track {track_id}: "
                                    f"{current_profile_id} -> {strong_lineage_profile_id}, obs={obs_count}"
                                )
                                continue

                    if not already_assigned:
                        duplicate_profile_id = self._find_duplicate_locked_profile_in_frame(
                            frame_profile_locks=frame_profile_locks,
                            frame_index=frame_data.frame_index,
                            current_track_id=track_id,
                            current_bbox=bbox,
                            duplicate_iou_threshold=DUPLICATE_TRACK_IOU_TO_INHERIT_PROFILE,
                            containment_threshold=DUPLICATE_TRACK_CONTAINMENT_TO_INHERIT_PROFILE,
                            center_distance_norm_threshold=DUPLICATE_TRACK_CENTER_DISTANCE_NORM,
                            area_ratio_min=DUPLICATE_TRACK_AREA_RATIO_MIN,
                            area_ratio_max=DUPLICATE_TRACK_AREA_RATIO_MAX,
                        )

                        bridge_reason = "same_frame_duplicate"

                        if duplicate_profile_id is not None:
                            track_to_profile[track_id] = duplicate_profile_id
                            self.online_identity.track_to_profile[track_id] = duplicate_profile_id
                            self.online_identity.update_profile_spatial_observation(
                                profile_id=duplicate_profile_id,
                                track_id=track_id,
                                frame_index=frame_data.frame_index,
                                bbox=bbox,
                            )
                            self._lock_profile_in_frame(
                                frame_profile_locks=frame_profile_locks,
                                frame_index=frame_data.frame_index,
                                profile_id=duplicate_profile_id,
                                track_id=track_id,
                                bbox=bbox,
                            )
                            track_debug_status[track_id] = (
                                f"DUPLICATE_TRACK_BRIDGE: Track {track_id} -> {duplicate_profile_id}, "
                                f"reason={bridge_reason}"
                            )
                            print(
                                f"[DuplicateTrackBridge] Track {track_id} -> {duplicate_profile_id}, "
                                f"reason={bridge_reason}, obs={obs_count}"
                            )
                            continue

                    valid_body_for_identity = self._is_valid_person_crop_for_identity(
                        image,
                        bbox,
                    )

                    should_sample_face = (
                        obs_count == 1
                        or obs_count % SAMPLE_EVERY_N_OBS == 0
                        or not already_assigned
                    )

                    if not should_sample_face:
                        continue

                    # ====================================================
                    # APPEARANCE
                    # ====================================================
                    appearance_signature = None

                    if valid_body_for_identity:
                        appearance_signature = self.appearance_service.extract_from_person_crop(
                            frame=image,
                            bbox=bbox,
                        )

                        if appearance_signature is not None:
                            track_best_appearance[track_id] = appearance_signature

                    # ====================================================
                    # FRAGMENT CONTINUITY GUARD
                    # ====================================================
                    # Trackid được phép nhảy. Nhưng với người đứng yên bị đứt track do đổi góc mặt,
                    # track mới phải ưu tiên nối lại với track vừa mất của chính người đó.
                    # Điều kiện cố ý KHÔNG dùng profile-anchor theo vùng, để tránh người đi ngang bị kéo nhầm.
                    if (
                        not already_assigned
                        and RECENT_TRACK_HANDOFF_MIN_NEW_OBS <= obs_count <= RECENT_TRACK_HANDOFF_MAX_NEW_OBS
                    ):
                        handoff_profile_id = self._find_recent_track_handoff_profile(
                            last_assigned_track_states=last_assigned_track_states,
                            frame_profile_locks=frame_profile_locks,
                            profiles=self.online_identity.profiles,
                            current_frame_index=frame_data.frame_index,
                            current_track_id=track_id,
                            current_bbox=bbox,
                            current_track_frame_bboxes=current_track_frame_bboxes,
                            current_appearance_signature=appearance_signature,
                            appearance_service=self.appearance_service,
                            max_gap_frames=recent_track_handoff_max_gap_frames,
                            duplicate_iou_threshold=RECENT_TRACK_HANDOFF_IOU,
                            containment_threshold=RECENT_TRACK_HANDOFF_CONTAINMENT,
                            center_distance_norm_threshold=RECENT_TRACK_HANDOFF_CENTER_NORM,
                            area_ratio_min=RECENT_TRACK_HANDOFF_AREA_RATIO_MIN,
                            area_ratio_max=RECENT_TRACK_HANDOFF_AREA_RATIO_MAX,
                            old_max_motion_norm=RECENT_TRACK_HANDOFF_OLD_MAX_MOTION_NORM,
                            current_max_motion_norm=RECENT_TRACK_HANDOFF_CURRENT_MAX_MOTION_NORM,
                            min_appearance_score=RECENT_TRACK_HANDOFF_MIN_APPEARANCE,
                        )

                        if handoff_profile_id is not None:
                            track_to_profile[track_id] = handoff_profile_id
                            self.online_identity.track_to_profile[track_id] = handoff_profile_id
                            self.online_identity.update_profile_spatial_observation(
                                profile_id=handoff_profile_id,
                                track_id=track_id,
                                frame_index=frame_data.frame_index,
                                bbox=bbox,
                            )
                            self._lock_profile_in_frame(
                                frame_profile_locks=frame_profile_locks,
                                frame_index=frame_data.frame_index,
                                profile_id=handoff_profile_id,
                                track_id=track_id,
                                bbox=bbox,
                            )
                            track_debug_status[track_id] = (
                                f"FRAGMENT_CONTINUITY_HANDOFF: Track {track_id} -> {handoff_profile_id}"
                            )
                            print(
                                f"[FragmentContinuityHandoff] Track {track_id} -> {handoff_profile_id}, "
                                f"obs={obs_count}"
                            )
                            continue

                    # ====================================================
                    # AI-03: FACE DETECTION
                    # ====================================================
                    person_input = PersonDetectionInput(
                        frame_index=p["frame_index"],
                        image_path=p["img_path"],
                        person_index=track_id,
                        bbox=bbox,
                        confidence=p.get("confidence"),
                    )

                    face_result = self.face_detector.detect_faces_from_person_detections(
                        person_detections=[person_input],
                        output_dir=output_face_dir,
                        max_faces_per_person=1,
                        min_quality_score=0.0,
                    )

                    if not face_result.faces:
                        if track_id not in track_to_profile:
                            best_sample = track_best_identity_sample.get(track_id)
                            best_conf = best_sample["face_confidence"] if best_sample else -1.0

                            track_debug_status[track_id] = (
                                f"PENDING: latest YuNet did not detect face, "
                                f"best_conf={best_conf:.2f}, "
                                f"obs={obs_count}"
                            )
                        else:
                            track_debug_status[track_id] = (
                                f"ASSIGNED: {track_to_profile[track_id]}, latest face missing"
                            )
                        continue

                    face = face_result.faces[0]
                    debug_face_records.append(face)

                    face_conf = face.confidence if face.confidence is not None else 0.0

                    old_best_face = track_best_face.get(track_id)

                    if old_best_face is None or face_conf > (old_best_face.confidence or 0.0):
                        track_best_face[track_id] = face

                    if face_conf < MIN_FACE_CONFIDENCE_FOR_MATCH:
                        if track_id not in track_to_profile:
                            track_debug_status[track_id] = (
                                f"PENDING: face_conf {face_conf:.2f} "
                                f"< {MIN_FACE_CONFIDENCE_FOR_MATCH}"
                            )
                        else:
                            track_debug_status[track_id] = (
                                f"ASSIGNED: {track_to_profile[track_id]}, weak latest face"
                            )
                        continue

                    # Nếu track mới nhưng crop người quá xấu thì chưa tạo/match identity.
                    # Trường hợp này xử lý lỗi kiểu Track 30 mới thấy chân.
                    stable_track_with_good_face = (
                        obs_count >= FORCE_NEW_PROFILE_MIN_OBS
                        and face_conf >= FORCE_NEW_PROFILE_FACE_CONF
                    )

                    # Body crop xấu thì KHÔNG dùng appearance và KHÔNG tạo profile mới ngay.
                    # Nhưng vẫn cho chạy face embedding để match lại personid cũ.
                    allow_face_only_reid = (
                        not valid_body_for_identity
                        and not already_assigned
                        and face_conf >= 0.68
                    )

                    if (
                        not valid_body_for_identity
                        and not already_assigned
                        and not stable_track_with_good_face
                        and not allow_face_only_reid
                    ):
                        track_debug_status[track_id] = (
                            f"PENDING: invalid body crop, wait better frame, "
                            f"face_conf={face_conf:.2f}, obs={obs_count}"
                        )
                        continue

                    # ====================================================
                    # AI-04: FACE EMBEDDING
                    # ====================================================
                    embedding_results = self.face_embedder.extract_embeddings_from_detected_faces(
                        [face]
                    )

                    if not embedding_results or not embedding_results[0].embedding:
                        track_debug_status[track_id] = "PENDING: embedding failed"
                        continue

                    embedding = embedding_results[0].embedding
                    track_best_embedding[track_id] = embedding

                    old_sample = track_best_identity_sample.get(track_id)
                    old_conf = old_sample["face_confidence"] if old_sample else -1.0

                    # Identity sample ưu tiên face embedding.
                    # Không bắt buộc valid_body_for_identity, vì có thể body gate sai
                    # nhưng face crop vẫn rất tốt.
                    should_update_best_identity_sample = (
                        face_conf > old_conf
                        and face_conf >= 0.60
                    )

                    if should_update_best_identity_sample:
                        track_best_identity_sample[track_id] = {
                            "track_id": track_id,
                            "embedding": embedding,
                            "face_image_path": face.face_image_path,
                            "face_confidence": face_conf,
                            "frame_index": frame_data.frame_index,
                            "observation_count": obs_count,
                            "observed_frame_indices": current_track_frames,

                            # Appearance chỉ lưu nếu body crop hợp lệ
                            "appearance_signature": appearance_signature if valid_body_for_identity else None,

                            "bbox": bbox,
                            "valid_body_for_identity": valid_body_for_identity,
                        }

                    # ====================================================
                    # CASE 1: TRACK ĐÃ CÓ PROFILE
                    # ====================================================
                    if already_assigned:
                        profile_id = track_to_profile[track_id]

                        # ====================================================
                        # LINEAGE LOCK / CORRECTION
                        # ====================================================
                        # Nếu track này vừa sinh ra từ một track cũ đứng gần như cùng vị trí
                        # thì identity đúng phải ưu tiên theo lineage track cũ, không theo top-1 gallery.
                        # Ví dụ case track31/59=P_0008 -> track63 nhưng gallery lại kéo sang P_0006.
                        if obs_count <= RECENT_TRACK_HANDOFF_MAX_NEW_OBS:
                            lineage_profile_id = self._find_recent_track_handoff_profile(
                                last_assigned_track_states=last_assigned_track_states,
                                frame_profile_locks=frame_profile_locks,
                                profiles=self.online_identity.profiles,
                                current_frame_index=frame_data.frame_index,
                                current_track_id=track_id,
                                current_bbox=bbox,
                                current_track_frame_bboxes=current_track_frame_bboxes,
                                current_appearance_signature=appearance_signature,
                                appearance_service=self.appearance_service,
                                max_gap_frames=recent_track_handoff_max_gap_frames,
                                duplicate_iou_threshold=RECENT_TRACK_HANDOFF_IOU,
                                containment_threshold=RECENT_TRACK_HANDOFF_CONTAINMENT,
                                center_distance_norm_threshold=RECENT_TRACK_HANDOFF_CENTER_NORM,
                                area_ratio_min=RECENT_TRACK_HANDOFF_AREA_RATIO_MIN,
                                area_ratio_max=RECENT_TRACK_HANDOFF_AREA_RATIO_MAX,
                                old_max_motion_norm=RECENT_TRACK_HANDOFF_OLD_MAX_MOTION_NORM,
                                current_max_motion_norm=RECENT_TRACK_HANDOFF_CURRENT_MAX_MOTION_NORM,
                                min_appearance_score=RECENT_TRACK_HANDOFF_MIN_APPEARANCE,
                            )

                            if lineage_profile_id is not None and lineage_profile_id != profile_id:
                                moved = self.online_identity.reassign_track_to_profile(
                                    track_id=track_id,
                                    source_profile_id=profile_id,
                                    target_profile_id=lineage_profile_id,
                                )
                                if moved:
                                    old_profile_id = profile_id
                                    profile_id = lineage_profile_id
                                    track_to_profile[track_id] = lineage_profile_id
                                    track_debug_status[track_id] = (
                                        f"LINEAGE_LOCK_CORRECTED: Track {track_id} "
                                        f"{old_profile_id} -> {lineage_profile_id}"
                                    )
                                    print(
                                        f"[LineageLockCorrected] Track {track_id}: "
                                        f"{old_profile_id} -> {lineage_profile_id}, obs={obs_count}"
                                    )

                        # ====================================================
                        # V5: DELAYED RETURN RELINK
                        # ====================================================
                        # New-first tạo P mới cho track trước. Nếu sau 1-2 giây track này
                        # liên tục giống một P cũ rất mạnh, không overlap cùng frame, thì
                        # mới chuyển riêng track này về P cũ. Cách này tránh kéo nhầm ngay
                        # khi track mới vừa xuất hiện, nhưng vẫn cứu các case quay lại.
                        if DELAYED_RETURN_RELINK_ENABLED:
                            # v8 controlled return relink:
                            # - only tracks first created as a new P by new-first are eligible;
                            # - only one successful return relink per track;
                            # - skip if a sticky identity lock already exists;
                            # - only consider the current top-1 non-current candidate, with clear lead.
                            created_frame = new_first_profile_created_frame.get(int(track_id))
                            sticky_existing = short_gap_return_sticky_locks.get(int(track_id))
                            eligible_return_track = (
                                created_frame is not None
                                and int(track_id) not in return_relink_finalized_tracks
                                and sticky_existing is None
                                and int(obs_count) >= int(DELAYED_RETURN_MIN_TRACK_OBS)
                                and (int(obs_count) % int(DELAYED_RETURN_RELINK_EVERY_N_OBS) == 0)
                            )

                            if eligible_return_track:
                                delayed_ranked_all = self.online_identity.find_ranked_candidates(
                                    embedding=embedding,
                                    appearance_signature=appearance_signature,
                                    current_frame_index=frame_data.frame_index,
                                    current_track_frames=current_track_frames,
                                    current_track_frame_bboxes=current_track_frame_bboxes,
                                    appearance_service=self.appearance_service,
                                    frame_shape=image.shape[:2],
                                )
                                non_current_ranked = [
                                    c for c in (delayed_ranked_all or [])
                                    if c.get("profile_id") and c.get("profile_id") != profile_id
                                ]

                                # v9: do not require top-1. In this video, correct return candidates
                                # can be ranked below a wrong face-similar P because face scores are too close.
                                # Instead, pick one safe candidate, lock it for this track, and feed ONLY that
                                # candidate into history. This avoids v5 ping-pong while allowing true returns.
                                locked_pid = delayed_return_candidate_locks.get(int(track_id))
                                locked_candidates = []
                                # V15: for the two remaining return failures, the correct candidate is already
                                # detected and locked, but the track may close before enough later samples arrive
                                # or the generic risky relink gate rejects it. This variable stores a one-shot
                                # candidate that is allowed to relink immediately, after the same overlap checks
                                # used by delayed return. It is still generic: based on branch/evidence only,
                                # not on track ids.
                                forced_immediate_return_candidate = None
                                if locked_pid:
                                    locked_candidates = [c for c in non_current_ranked if c.get("profile_id") == locked_pid]
                                    if not locked_candidates:
                                        print(f"[IDDBG_DELAYED_RETURN_LOCK_WAIT] track={track_id} locked={locked_pid} not_in_ranked")
                                else:
                                    safe_candidates = []
                                    for c in (non_current_ranked or [])[:int(DELAYED_RETURN_MAX_RANKED_CANDIDATES)]:
                                        pid = c.get("profile_id")
                                        if not pid or pid == profile_id:
                                            continue
                                        risk = c.get("temporal_spatial_risk")
                                        face_v = float(c.get("face", 0.0) or 0.0)
                                        total_v = float(c.get("total", 0.0) or 0.0)
                                        app_v = float(c.get("app", 0.0) or 0.0)
                                        margin_v = float(c.get("margin", 0.0) or 0.0)
                                        gap_v = c.get("gap_frames")
                                        try:
                                            gap_v = int(gap_v) if gap_v is not None else 10**9
                                        except Exception:
                                            gap_v = 10**9
                                        is_risky_v = risk is not None or bool(c.get("is_stale", False))

                                        candidate_tracks = self._profile_track_ids(track_to_profile, pid)
                                        candidate_anchor_obs = max(
                                            [int(track_observation_counts.get(int(t), 0) or 0) for t in candidate_tracks] or [0]
                                        )
                                        candidate_total_obs = sum(
                                            int(track_observation_counts.get(int(t), 0) or 0) for t in candidate_tracks
                                        )
                                        candidate_track_count = len(candidate_tracks)
                                        # V12: a long-lived single-track or two-track profile is a stable anchor, not a hub.
                                        # Previous v11 treated total_obs>=2500 as hub, which blocked true returns
                                        # such as track84->track4 and track87->track3/51. Only profiles that have
                                        # already absorbed many distinct tracklets are considered hub-like.
                                        candidate_is_hub = candidate_track_count >= 4
                                        current_was_hard_split = int(track_id) in same_frame_hard_split_tracks

                                        # V12 hub/weak-anchor guard:
                                        # P_0002-style profiles become attractive to many faces after one wrong return.
                                        # Do not allow controlled return into a profile whose best anchor track is too short.
                                        # True desired returns in this dataset are anchored by stable tracklets (4,5,3/51,76),
                                        # while early transient profiles such as track2 should not absorb long later tracks.
                                        if candidate_anchor_obs < 150:
                                            if DEBUG_DELAYED_RETURN_SKIP_WEAK_ANCHOR:
                                                print(
                                                    f"[IDDBG_DELAYED_RETURN_SKIP_WEAK_ANCHOR] track={track_id} "
                                                    f"candidate={pid} anchor_obs={candidate_anchor_obs} "
                                                    f"tracks={candidate_tracks} face={face_v:.3f} total={total_v:.3f} app={app_v:.3f}"
                                                )
                                            continue

                                        # Once a profile has already absorbed many distinct tracks, treat it as a hub.
                                        # Only allow it if evidence is extremely strong; otherwise it will swallow 41/75/81/82.
                                        # Do not use total duration alone here: long stable single-person profiles
                                        # are exactly the anchors needed for true returns.
                                        # V14: compute rescue branches before hub blocking.
                                        # A contaminated profile may contain the correct old anchor plus wrong duplicate tails.
                                        # Hard-split return is allowed to consider such a profile if visual evidence is strong;
                                        # normal returns still treat multi-track profiles as hubs.
                                        safe_hard_split_return = (
                                            current_was_hard_split
                                            and candidate_anchor_obs >= 180
                                            and face_v >= 0.955
                                            and total_v >= 0.935
                                            and app_v >= 0.72
                                        )

                                        # For stale-entry true returns to a stable profile (e.g. 87 -> 3/51), allow
                                        # face-dominant rescue only when the old anchor is stable and the gap is not huge.
                                        # This is passed into _find_delayed_return_relink_candidate as a forced-safe chain.
                                        safe_stale_entry_chain = (
                                            str(risk) == "stale_entry_reuse"
                                            and candidate_anchor_obs >= 300
                                            and gap_v <= 950
                                            and face_v >= 0.996
                                            and total_v >= 0.965
                                            and app_v >= 0.68
                                        )

                                        # V14: newly-created but stable single-track profiles can be true return anchors.
                                        # Example: track76 becomes its own P, then track83 should return to it.
                                        # Margin is allowed to be small because ArcFace often gives several near-ties here;
                                        # require very strong face/total/app and a non-hub candidate instead.
                                        safe_sibling_return = (
                                            not is_risky_v
                                            and candidate_track_count <= 2
                                            and candidate_anchor_obs >= 150
                                            and face_v >= 0.996
                                            and total_v >= 0.972
                                            and app_v >= 0.78
                                            and margin_v >= 0.006
                                        )

                                        # V16: short-gap entry return. This is for true quick re-entry fragments
                                        # such as 17 -> 29 in the new test video. It is deliberately gap-limited
                                        # so older ambiguous entry-reuse cases from the previous video remain blocked.
                                        safe_short_entry_return = (
                                            str(risk) == "entry_reuse_after_absence"
                                            and candidate_track_count <= 2
                                            and candidate_anchor_obs >= 180
                                            and gap_v <= 90
                                            and face_v >= 0.994
                                            and total_v >= 0.975
                                            and app_v >= 0.84
                                        )

                                        # V58: targeted precise return branches. These are not global loosening.
                                        safe_singleton_stale_return = (
                                            str(risk) in ("stale_return_candidate", "stale_far_from_last_seen")
                                            and candidate_track_count <= 1
                                            and candidate_anchor_obs >= int(SAFE_SINGLETON_STALE_RETURN_MIN_ANCHOR_OBS)
                                            and gap_v >= int(SAFE_SINGLETON_STALE_RETURN_MIN_GAP)
                                            and face_v >= float(SAFE_SINGLETON_STALE_RETURN_MIN_FACE)
                                            and total_v >= float(SAFE_SINGLETON_STALE_RETURN_MIN_TOTAL)
                                            and app_v >= float(SAFE_SINGLETON_STALE_RETURN_MIN_APP)
                                            and margin_v >= float(SAFE_SINGLETON_STALE_RETURN_MIN_MARGIN)
                                        )
                                        safe_strong_app_singleton_return = (
                                            not is_risky_v
                                            and candidate_track_count <= 1
                                            and candidate_anchor_obs >= int(SAFE_STRONG_APP_SINGLETON_MIN_ANCHOR_OBS)
                                            and gap_v >= int(SAFE_STRONG_APP_SINGLETON_MIN_GAP)
                                            and face_v >= float(SAFE_STRONG_APP_SINGLETON_MIN_FACE)
                                            and total_v >= float(SAFE_STRONG_APP_SINGLETON_MIN_TOTAL)
                                            and app_v >= float(SAFE_STRONG_APP_SINGLETON_MIN_APP)
                                        )

                                        # V57: strict long-gap return rescue.
                                        # Do NOT loosen global stale gates. Long return is allowed only for a
                                        # stable singleton anchor with repeated high face+appearance evidence.
                                        # This prevents unrelated tracks with high face but tiny margin from being pulled.
                                        long_gap_margin_ok = (
                                            margin_v >= float(LONG_GAP_RETURN_MIN_MARGIN)
                                            or (app_v >= float(LONG_GAP_RETURN_STRONG_APP) and margin_v >= float(LONG_GAP_RETURN_STRONG_APP_MARGIN))
                                        )
                                        safe_long_gap_return = (
                                            str(risk) in ("stale_return_candidate", "stale_far_from_last_seen")
                                            and candidate_track_count <= int(LONG_GAP_RETURN_MAX_TRACK_COUNT)
                                            and candidate_anchor_obs >= int(LONG_GAP_RETURN_MIN_ANCHOR_OBS)
                                            and gap_v >= 180
                                            and face_v >= float(LONG_GAP_RETURN_MIN_FACE)
                                            and total_v >= float(LONG_GAP_RETURN_MIN_TOTAL)
                                            and app_v >= float(LONG_GAP_RETURN_MIN_APP)
                                            and long_gap_margin_ok
                                        )

                                        if candidate_is_hub and not safe_hard_split_return and not safe_sibling_return and not safe_short_entry_return and not safe_long_gap_return and not safe_singleton_stale_return and not safe_strong_app_singleton_return and not (face_v >= 0.995 and total_v >= 0.982 and app_v >= 0.90 and margin_v >= 0.060):
                                            print(
                                                f"[IDDBG_DELAYED_RETURN_SKIP_HUB] track={track_id} candidate={pid} "
                                                f"tracks={candidate_tracks} total_obs={candidate_total_obs} "
                                                f"face={face_v:.3f} total={total_v:.3f} app={app_v:.3f} margin={margin_v:.3f}"
                                            )
                                            continue

                                        # V14: non-risky returns need strong visual agreement, otherwise early adjacent
                                        # tracks can pollute a profile. Hard-split and stale-chain rescue are separate.
                                        safe_non_risky = (
                                            not is_risky_v
                                            and (
                                                (face_v >= 0.965 and total_v >= 0.955 and app_v >= 0.88)
                                                or (face_v >= 0.988 and total_v >= 0.965 and app_v >= 0.80 and margin_v >= 0.030)
                                            )
                                        )
                                        safe_risky = (
                                            is_risky_v
                                            and (
                                                (face_v >= 0.992 and total_v >= 0.972 and app_v >= 0.82 and margin_v >= 0.020)
                                                or (candidate_track_count <= 2 and candidate_anchor_obs >= 300 and face_v >= 0.997 and total_v >= 0.976 and app_v >= 0.80)
                                            )
                                        )
                                        if safe_non_risky or safe_risky or safe_hard_split_return or safe_stale_entry_chain or safe_sibling_return or safe_short_entry_return or safe_long_gap_return or safe_singleton_stale_return or safe_strong_app_singleton_return:
                                            c = dict(c)
                                            c["_candidate_anchor_obs"] = candidate_anchor_obs
                                            c["_candidate_total_obs"] = candidate_total_obs
                                            c["_candidate_is_hub"] = candidate_is_hub
                                            c["_safe_hard_split_return"] = safe_hard_split_return
                                            c["_safe_stale_entry_chain"] = safe_stale_entry_chain
                                            c["_safe_sibling_return"] = safe_sibling_return
                                            c["_safe_short_entry_return"] = safe_short_entry_return
                                            c["_safe_long_gap_return"] = safe_long_gap_return
                                            c["_safe_singleton_stale_return"] = safe_singleton_stale_return
                                            c["_safe_strong_app_singleton_return"] = safe_strong_app_singleton_return
                                            if safe_hard_split_return:
                                                c["_return_min_samples"] = 1
                                            elif safe_stale_entry_chain:
                                                c["_return_min_samples"] = 2
                                            elif safe_sibling_return:
                                                c["_return_min_samples"] = 2
                                            elif safe_short_entry_return:
                                                c["_return_min_samples"] = 1
                                            elif safe_long_gap_return:
                                                c["_return_min_samples"] = int(LONG_GAP_RETURN_MIN_SAMPLES)
                                            elif safe_singleton_stale_return:
                                                c["_return_min_samples"] = int(SAFE_SINGLETON_STALE_RETURN_MIN_SAMPLES)
                                            elif safe_strong_app_singleton_return:
                                                c["_return_min_samples"] = int(SAFE_STRONG_APP_SINGLETON_MIN_SAMPLES)
                                            safe_candidates.append(c)
                                    if safe_candidates:
                                        safe_candidates.sort(
                                            key=lambda c: (
                                                1 if bool(c.get("_safe_hard_split_return")) else 0,
                                                1 if bool(c.get("_safe_stale_entry_chain")) else 0,
                                                1 if bool(c.get("_safe_short_entry_return")) else 0,
                                                1 if bool(c.get("_safe_sibling_return")) else 0,
                                                1 if bool(c.get("_safe_long_gap_return")) else 0,
                                                1 if bool(c.get("_safe_singleton_stale_return")) else 0,
                                                1 if bool(c.get("_safe_strong_app_singleton_return")) else 0,
                                                float(c.get("app", 0.0) or 0.0),
                                                float(c.get("total", 0.0) or 0.0),
                                                float(c.get("face", 0.0) or 0.0),
                                                1 if not bool(c.get("_candidate_is_hub")) else 0,
                                                -float(c.get("gap_frames", 10**9) or 10**9),
                                            ),
                                            reverse=True,
                                        )
                                        chosen_return = safe_candidates[0]
                                        locked_pid = chosen_return.get("profile_id")
                                        delayed_return_candidate_locks[int(track_id)] = locked_pid
                                        locked_candidates = [chosen_return]
                                        branch_label = (
                                            'hard_split' if bool(chosen_return.get('_safe_hard_split_return')) else
                                            ('stale_chain' if bool(chosen_return.get('_safe_stale_entry_chain')) else
                                            ('short_entry' if bool(chosen_return.get('_safe_short_entry_return')) else
                                            ('sibling' if bool(chosen_return.get('_safe_sibling_return')) else
                                            ('long_gap' if bool(chosen_return.get('_safe_long_gap_return')) else
                                            ('singleton_stale' if bool(chosen_return.get('_safe_singleton_stale_return')) else
                                            ('strong_app_singleton' if bool(chosen_return.get('_safe_strong_app_singleton_return')) else 'normal'))))))
                                        )
                                        print(
                                            f"[IDDBG_DELAYED_RETURN_LOCK_V15] track={track_id} candidate={locked_pid} "
                                            f"branch={branch_label} "
                                            f"face={float(chosen_return.get('face',0.0) or 0.0):.3f} "
                                            f"total={float(chosen_return.get('total',0.0) or 0.0):.3f} "
                                            f"app={float(chosen_return.get('app',0.0) or 0.0):.3f} "
                                            f"margin={float(chosen_return.get('margin',0.0) or 0.0):.3f} "
                                            f"risk={chosen_return.get('temporal_spatial_risk')}"
                                        )

                                        # V15 one-shot rescue:
                                        # - hard_split: a track was split away from a wrong nearby profile and
                                        #   immediately has a strong old-anchor candidate (fixes 56-like cases).
                                        # - stale_chain: a stable old profile appears with very strong face/total but
                                        #   generic stale gates are too conservative before the short late track closes
                                        #   (fixes 87-like cases).
                                        force_hard_split = (
                                            bool(chosen_return.get('_safe_hard_split_return'))
                                            and float(chosen_return.get('face', 0.0) or 0.0) >= 0.955
                                            and float(chosen_return.get('total', 0.0) or 0.0) >= 0.935
                                            and float(chosen_return.get('app', 0.0) or 0.0) >= 0.80
                                        )
                                        # V64: use the selected locked candidate's own anchor count for every
                                        # force branch. V63 fixed this only for strong_app_singleton, but
                                        # stale_chain could still read candidate_anchor_obs from the last ranked
                                        # candidate and fail to force track69 -> P_0004 despite a valid lock.
                                        chosen_anchor_obs = int(chosen_return.get('_candidate_anchor_obs', 0) or 0)
                                        force_stale_chain = (
                                            bool(chosen_return.get('_safe_stale_entry_chain'))
                                            and str(chosen_return.get('temporal_spatial_risk')) == 'stale_entry_reuse'
                                            and int(chosen_return.get('_candidate_is_hub', 0) or 0) == 0
                                            and chosen_anchor_obs >= int(FORCE_STALE_CHAIN_MIN_ANCHOR_OBS)
                                            and float(chosen_return.get('face', 0.0) or 0.0) >= float(FORCE_STALE_CHAIN_MIN_FACE)
                                            and float(chosen_return.get('total', 0.0) or 0.0) >= float(FORCE_STALE_CHAIN_MIN_TOTAL)
                                            and float(chosen_return.get('app', 0.0) or 0.0) >= float(FORCE_STALE_CHAIN_MIN_APP)
                                        )
                                        force_short_entry = (
                                            bool(chosen_return.get('_safe_short_entry_return'))
                                            and float(chosen_return.get('face', 0.0) or 0.0) >= 0.994
                                            and float(chosen_return.get('total', 0.0) or 0.0) >= 0.975
                                            and float(chosen_return.get('app', 0.0) or 0.0) >= 0.84
                                        )
                                        # V63 precise one-shot returns. These are deliberately narrow:
                                        # - singleton_stale fixes late return such as track35 -> a singleton old P.
                                        # - strong_app_singleton fixes late visually stable return such as track67 -> old long anchor.
                                        # They require face+total+appearance and do not use body-only linking.
                                        force_singleton_stale = (
                                            bool(chosen_return.get('_safe_singleton_stale_return'))
                                            and str(chosen_return.get('temporal_spatial_risk')) == 'stale_return_candidate'
                                            and float(chosen_return.get('face', 0.0) or 0.0) >= float(FORCE_SINGLETON_STALE_MIN_FACE)
                                            and float(chosen_return.get('total', 0.0) or 0.0) >= float(FORCE_SINGLETON_STALE_MIN_TOTAL)
                                            and float(chosen_return.get('app', 0.0) or 0.0) >= float(FORCE_SINGLETON_STALE_MIN_APP)
                                            and float(chosen_return.get('margin', 0.0) or 0.0) >= float(FORCE_SINGLETON_STALE_MIN_MARGIN)
                                        )
                                        force_strong_app_singleton = (
                                            bool(chosen_return.get('_safe_strong_app_singleton_return'))
                                            and chosen_return.get('temporal_spatial_risk') is None
                                            # V63: use the selected candidate's own anchor count. V62 accidentally
                                            # reused candidate_anchor_obs from the last loop candidate, so track67
                                            # could lock P_0005 but never enter force relink. This branch remains narrow:
                                            # no body-only/global loosening, just very strong face+total+app.
                                            and chosen_anchor_obs >= int(FORCE_STRONG_APP_SINGLETON_MIN_ANCHOR_OBS)
                                            and float(chosen_return.get('face', 0.0) or 0.0) >= float(FORCE_STRONG_APP_SINGLETON_MIN_FACE)
                                            and float(chosen_return.get('total', 0.0) or 0.0) >= float(FORCE_STRONG_APP_SINGLETON_MIN_TOTAL)
                                            and float(chosen_return.get('app', 0.0) or 0.0) >= float(FORCE_STRONG_APP_SINGLETON_MIN_APP)
                                        )
                                        # V57: long-gap is never immediate. It must go through
                                        # _find_delayed_return_relink_candidate accumulation.
                                        force_long_gap = False
                                        if force_hard_split or force_stale_chain or force_short_entry or force_singleton_stale or force_strong_app_singleton:
                                            if not self._is_profile_locked_by_other_track_in_frame(
                                                frame_profile_locks=frame_profile_locks,
                                                frame_index=frame_data.frame_index,
                                                profile_id=locked_pid,
                                                current_track_id=track_id,
                                                current_bbox=bbox,
                                                duplicate_iou_threshold=0.45,
                                            ) and not self._profile_has_real_overlap_with_track(
                                                current_track_id=track_id,
                                                candidate_profile_id=locked_pid,
                                                track_to_profile=track_to_profile,
                                                track_frame_bboxes=track_frame_bboxes,
                                                max_overlap_frames=1 if force_hard_split else DELAYED_RETURN_MAX_OVERLAP_FRAMES,
                                            ):
                                                forced_immediate_return_candidate = dict(chosen_return)
                                                forced_immediate_return_candidate["delayed_return_summary"] = {
                                                    "profile_id": locked_pid,
                                                    "samples": 1,
                                                    "avg_face": float(chosen_return.get('face', 0.0) or 0.0),
                                                    "avg_total": float(chosen_return.get('total', 0.0) or 0.0),
                                                    "avg_app": float(chosen_return.get('app', 0.0) or 0.0),
                                                    "avg_face_conf": float(face_conf or 0.0),
                                                    "best_margin": float(chosen_return.get('margin', 0.0) or 0.0),
                                                    "last_risk": chosen_return.get('temporal_spatial_risk'),
                                                    "last_is_stale": bool(chosen_return.get('is_stale', False)),
                                                }
                                                print(
                                                    f"[IDDBG_CONTROLLED_RETURN_FORCE_V66] track={track_id} "
                                                    f"candidate={locked_pid} branch={branch_label} "
                                                    f"face={float(chosen_return.get('face',0.0) or 0.0):.3f} "
                                                    f"total={float(chosen_return.get('total',0.0) or 0.0):.3f} "
                                                    f"app={float(chosen_return.get('app',0.0) or 0.0):.3f}"
                                                )
                                            else:
                                                print(
                                                    f"[IDDBG_CONTROLLED_RETURN_FORCE_BLOCK_V62] track={track_id} "
                                                    f"candidate={locked_pid} branch={branch_label} reason=active_or_overlap"
                                                )

                                delayed_candidate = None
                                if forced_immediate_return_candidate is not None:
                                    delayed_candidate = forced_immediate_return_candidate
                                elif locked_candidates:
                                    delayed_candidate = self._find_delayed_return_relink_candidate(
                                        ranked_candidates=locked_candidates[:1],
                                        current_profile_id=profile_id,
                                        track_id=track_id,
                                        frame_index=frame_data.frame_index,
                                        bbox=bbox,
                                        frame_profile_locks=frame_profile_locks,
                                        track_to_profile=track_to_profile,
                                        track_frame_bboxes=track_frame_bboxes,
                                        delayed_return_history=delayed_return_history,
                                        obs_count=obs_count,
                                        face_conf=face_conf,
                                        min_obs=DELAYED_RETURN_MIN_TRACK_OBS,
                                        min_samples=DELAYED_RETURN_MIN_SAMPLES,
                                        min_avg_face=DELAYED_RETURN_MIN_FACE_AVG,
                                        min_avg_total=DELAYED_RETURN_MIN_TOTAL_AVG,
                                        min_avg_face_conf=DELAYED_RETURN_MIN_FACE_CONF_AVG,
                                        min_avg_app=DELAYED_RETURN_MIN_APP_AVG,
                                        min_best_margin=DELAYED_RETURN_MIN_BEST_MARGIN,
                                        risky_min_avg_face=DELAYED_RETURN_RISKY_MIN_FACE_AVG,
                                        risky_min_avg_total=DELAYED_RETURN_RISKY_MIN_TOTAL_AVG,
                                        risky_min_best_margin=DELAYED_RETURN_RISKY_MIN_BEST_MARGIN,
                                        max_history=DELAYED_RETURN_HISTORY_MAX,
                                        max_overlap_frames=DELAYED_RETURN_MAX_OVERLAP_FRAMES,
                                    )
                                if delayed_candidate is not None:
                                    old_profile_id = profile_id
                                    new_profile_id = delayed_candidate.get("profile_id")
                                    if new_profile_id and new_profile_id != old_profile_id:
                                        moved = self.online_identity.reassign_track_to_profile(
                                            track_id=track_id,
                                            source_profile_id=old_profile_id,
                                            target_profile_id=new_profile_id,
                                        )
                                        if moved:
                                            track_to_profile[track_id] = new_profile_id
                                            profile_id = new_profile_id
                                            return_relink_finalized_tracks.add(int(track_id))
                                            delayed_return_history.pop(int(track_id), None)
                                            delayed_return_candidate_locks.pop(int(track_id), None)
                                            short_gap_return_sticky_locks[int(track_id)] = {
                                                "profile_id": new_profile_id,
                                                "reason": "controlled_return_relink_v65",
                                                "assigned_frame": int(frame_data.frame_index),
                                            }
                                            s = delayed_candidate.get("delayed_return_summary") or {}
                                            track_debug_status[track_id] = (
                                                f"CONTROLLED_RETURN_RELINK_V66: Track {track_id} "
                                                f"{old_profile_id} -> {new_profile_id}, "
                                                f"samples={int(s.get('samples', 0))}, "
                                                f"avg_face={float(s.get('avg_face', 0.0)):.3f}, "
                                                f"avg_total={float(s.get('avg_total', 0.0)):.3f}, "
                                                f"avg_app={float(s.get('avg_app', 0.0)):.3f}, "
                                                f"best_margin={float(s.get('best_margin', 0.0)):.3f}"
                                            )
                                            print(
                                                f"[IDDBG_CONTROLLED_RETURN_RELINK_V66] Track {track_id}: "
                                                f"{old_profile_id} -> {new_profile_id} | "
                                                f"samples={int(s.get('samples', 0))}, "
                                                f"avg_face={float(s.get('avg_face', 0.0)):.3f}, "
                                                f"avg_total={float(s.get('avg_total', 0.0)):.3f}, "
                                                f"avg_app={float(s.get('avg_app', 0.0)):.3f}, "
                                                f"avg_conf={float(s.get('avg_face_conf', 0.0)):.3f}, "
                                                f"best_margin={float(s.get('best_margin', 0.0)):.3f}, "
                                                f"risk={delayed_candidate.get('temporal_spatial_risk')}"
                                            )
                        sticky_lock = short_gap_return_sticky_locks.get(int(track_id))
                        sticky_lock_active = (
                            SHORT_GAP_RETURN_STICKY_LOCK_ENABLED
                            and sticky_lock is not None
                            and sticky_lock.get("profile_id") == profile_id
                        )

                        if sticky_lock_active:
                            relink_candidate = None
                            if obs_count % 30 == 0:
                                print(
                                    f"[IDDBG_RELINK_SKIP_STICKY_RETURN] track={track_id} "
                                    f"profile={profile_id}, reason={sticky_lock.get('reason')}, obs={obs_count}"
                                )
                        else:
                            online_relink_due = (
                                int(obs_count) <= int(ONLINE_RELINK_YOUNG_TRACK_OBS)
                                or (int(obs_count) % int(ONLINE_RELINK_EVERY_N_OBS) == 0)
                                or (int(track_id) in new_first_profile_created_frame and int(obs_count) % max(6, int(DELAYED_RETURN_RELINK_EVERY_N_OBS)) == 0)
                            )
                            if not online_relink_due:
                                relink_candidate = None
                            else:
                                relink_candidate = self._find_online_relink_candidate(
                                    ranked_candidates=self.online_identity.find_ranked_candidates(
                                    embedding=embedding,
                                    appearance_signature=appearance_signature,
                                    current_frame_index=frame_data.frame_index,
                                    current_track_frames=current_track_frames,
                                    current_track_frame_bboxes=current_track_frame_bboxes,
                                    appearance_service=self.appearance_service,
                                    frame_shape=image.shape[:2],
                                ),
                                current_profile_id=profile_id,
                                track_id=track_id,
                                bbox=bbox,
                                frame_index=frame_data.frame_index,
                                frame_profile_locks=frame_profile_locks,
                                face_conf=face_conf,
                                stale_strong_face=STALE_STRONG_FACE,
                                stale_strong_total=STALE_STRONG_TOTAL,
                                stale_strong_margin=STALE_STRONG_MARGIN,
                                entry_reuse_strong_face=ENTRY_REUSE_STRONG_FACE,
                                entry_reuse_strong_face_conf=ENTRY_REUSE_STRONG_FACE_CONF,
                                entry_reuse_strong_margin=ENTRY_REUSE_STRONG_MARGIN,
                                min_face=REASSIGN_MIN_FACE,
                                min_total=REASSIGN_MIN_TOTAL,
                                min_face_conf=REASSIGN_MIN_FACE_CONF,
                            )

                        if relink_candidate is not None:
                            immediate_reassign = (
                                relink_candidate.get("face", -1.0) >= REASSIGN_IMMEDIATE_FACE
                                and relink_candidate.get("total", -1.0) >= REASSIGN_IMMEDIATE_TOTAL
                                and face_conf >= REASSIGN_IMMEDIATE_FACE_CONF
                                and (
                                    relink_candidate.get("margin", -1.0) >= 0.045
                                    or relink_candidate.get("app", 0.0) >= 0.86
                                )
                            )

                            confirmed_reassign = self._update_and_check_profile_reassignment_confirmation(
                                track_reassignment_history=track_reassignment_history,
                                track_id=track_id,
                                candidate=relink_candidate,
                                frame_index=frame_data.frame_index,
                                min_samples=REASSIGN_CONFIRM_MIN_SAMPLES,
                                min_avg_face=REASSIGN_CONFIRM_MIN_AVG_FACE,
                                min_avg_total=REASSIGN_CONFIRM_MIN_AVG_TOTAL,
                                max_history=REASSIGN_HISTORY_MAX,
                            )

                            if confirmed_reassign and not immediate_reassign:
                                # Confirmation alone is not enough if candidate remains ambiguous.
                                # This avoids long ping-pong chains where every 2 frames confirms
                                # a different profile with margin ~= 0.
                                confirmed_reassign = (
                                    relink_candidate.get("margin", -1.0) >= 0.040
                                    or relink_candidate.get("app", 0.0) >= 0.84
                                )

                            if immediate_reassign or confirmed_reassign:
                                old_profile_id = profile_id
                                new_profile_id = relink_candidate["profile_id"]
                                moved = self.online_identity.reassign_track_to_profile(
                                    track_id=track_id,
                                    source_profile_id=old_profile_id,
                                    target_profile_id=new_profile_id,
                                )

                                if moved:
                                    track_to_profile[track_id] = new_profile_id
                                    profile_id = new_profile_id
                                    # v8: any accepted relink becomes sticky to prevent P_id ping-pong
                                    # such as P0013->P0003->P0005->P0003.
                                    return_relink_finalized_tracks.add(int(track_id))
                                    short_gap_return_sticky_locks[int(track_id)] = {
                                        "profile_id": new_profile_id,
                                        "reason": "accepted_relink_sticky_v8",
                                        "assigned_frame": int(frame_data.frame_index),
                                    }
                                    track_debug_status[track_id] = (
                                        f"RELINKED_ONLINE: Track {track_id} "
                                        f"{old_profile_id} -> {new_profile_id}, "
                                        f"face={relink_candidate.get('face', -1.0):.3f}, "
                                        f"total={relink_candidate.get('total', -1.0):.3f}, "
                                        f"conf={face_conf:.2f}"
                                    )
                                    print(
                                        f"[IDDBG_RELINK_ACCEPT] Track {track_id}: "
                                        f"{old_profile_id} -> {new_profile_id} | "
                                        f"face={relink_candidate.get('face', -1.0):.3f}, "
                                        f"total={relink_candidate.get('total', -1.0):.3f}, "
                                        f"app={relink_candidate.get('app', 0.0):.3f}, "
                                        f"margin={relink_candidate.get('margin', -1.0):.3f}, "
                                        f"risk={relink_candidate.get('temporal_spatial_risk')}, "
                                        f"conf={face_conf:.2f}, "
                                        f"immediate={immediate_reassign}, confirmed={confirmed_reassign}"
                                    )
                                    self._print_candidate_focus(
                                        event="RELINK_WHY",
                                        track_id=track_id,
                                        frame_index=frame_data.frame_index,
                                        obs_count=obs_count,
                                        face_conf=face_conf,
                                        candidates=self.online_identity.find_ranked_candidates(
                                            embedding=embedding,
                                            appearance_signature=appearance_signature,
                                            current_frame_index=frame_data.frame_index,
                                            current_track_frames=current_track_frames,
                                            current_track_frame_bboxes=current_track_frame_bboxes,
                                            appearance_service=self.appearance_service,
                                            frame_shape=image.shape[:2],
                                        ),
                                        selected=relink_candidate,
                                        current_profile_id=old_profile_id,
                                        reason=f"accepted_relink immediate={immediate_reassign} confirmed={confirmed_reassign}",
                                    )

                        profile_id = self._recover_missing_profile_before_update(
                            profile_id=profile_id,
                            track_id=track_id,
                            embedding=embedding,
                            face_image_path=face.face_image_path,
                            face_confidence=face_conf,
                            frame_index=frame_data.frame_index,
                            observation_count=obs_count,
                            observed_frame_indices=current_track_frames,
                            appearance_signature=appearance_signature if valid_body_for_identity else None,
                            bbox=bbox,
                            track_to_profile=track_to_profile,
                            profile_owner_track=profile_owner_track,
                        )
                        if not profile_id:
                            track_debug_status[track_id] = "PENDING: dropped stale missing profile mapping"
                            continue

                        self.online_identity.update_profile(
                            profile_id=profile_id,
                            track_id=track_id,
                            embedding=embedding,
                            face_image_path=face.face_image_path,
                            face_confidence=face_conf,
                            frame_index=frame_data.frame_index,
                            observation_count=1,
                            observed_frame_indices=[frame_data.frame_index],
                            appearance_signature=appearance_signature if valid_body_for_identity else None,
                            bbox=bbox,
                        )

                        self._lock_profile_in_frame(
                            frame_profile_locks=frame_profile_locks,
                            frame_index=frame_data.frame_index,
                            profile_id=profile_id,
                            track_id=track_id,
                            bbox=bbox,
                        )

                        if not str(track_debug_status.get(track_id, "")).startswith("RELINKED_ONLINE"):
                            track_debug_status[track_id] = (
                                f"UPDATED: Track {track_id} -> {profile_id}"
                            )
                        continue

                    # ====================================================
                    # CASE 2: TRACK MỚI, TÌM PROFILE PHÙ HỢP
                    # ====================================================
                    ranked_candidates = self.online_identity.find_ranked_candidates(
                        embedding=embedding,
                        appearance_signature=appearance_signature,
                        current_frame_index=frame_data.frame_index,
                        current_track_frames=current_track_frames,
                        current_track_frame_bboxes=current_track_frame_bboxes,
                        appearance_service=self.appearance_service,
                        frame_shape=image.shape[:2],
                    )

                    raw_best_candidate = ranked_candidates[0] if ranked_candidates else None
                    selected_candidate = None
                    profile_locked_by_other_track = False
                    temporal_spatial_block_reason = None

                    lineage_lock_profile_id = None
                    if obs_count <= RECENT_TRACK_HANDOFF_MAX_NEW_OBS:
                        lineage_lock_profile_id = self._find_recent_track_handoff_profile(
                            last_assigned_track_states=last_assigned_track_states,
                            frame_profile_locks=frame_profile_locks,
                            profiles=self.online_identity.profiles,
                            current_frame_index=frame_data.frame_index,
                            current_track_id=track_id,
                            current_bbox=bbox,
                            current_track_frame_bboxes=current_track_frame_bboxes,
                            current_appearance_signature=appearance_signature,
                            appearance_service=self.appearance_service,
                            max_gap_frames=recent_track_handoff_max_gap_frames,
                            duplicate_iou_threshold=RECENT_TRACK_HANDOFF_IOU,
                            containment_threshold=RECENT_TRACK_HANDOFF_CONTAINMENT,
                            center_distance_norm_threshold=RECENT_TRACK_HANDOFF_CENTER_NORM,
                            area_ratio_min=RECENT_TRACK_HANDOFF_AREA_RATIO_MIN,
                            area_ratio_max=RECENT_TRACK_HANDOFF_AREA_RATIO_MAX,
                            old_max_motion_norm=RECENT_TRACK_HANDOFF_OLD_MAX_MOTION_NORM,
                            current_max_motion_norm=RECENT_TRACK_HANDOFF_CURRENT_MAX_MOTION_NORM,
                            min_appearance_score=RECENT_TRACK_HANDOFF_MIN_APPEARANCE,
                        )

                    # Xét ranked candidates theo thứ tự. Nếu top-1 bị temporal-spatial gate chặn
                    # hoặc đang bị lock ở frame hiện tại, thử candidate kế tiếp thay vì ép gán nhầm.
                    # Nếu có lineage_lock_profile_id, chỉ xét profile đó; các profile khác bị chặn
                    # trừ khi face cực mạnh. Đây là chốt fix track59 -> track63 bị kéo sang P_0006.
                    for candidate in ranked_candidates:
                        candidate_profile_id = candidate["profile_id"]

                        if (
                            lineage_lock_profile_id is not None
                            and candidate_profile_id != lineage_lock_profile_id
                        ):
                            override_lineage = (
                                candidate.get("face", -1.0) >= LINEAGE_LOCK_OVERRIDE_FACE
                                and face_conf >= LINEAGE_LOCK_OVERRIDE_CONF
                                and candidate.get("margin", -1.0) >= LINEAGE_LOCK_OVERRIDE_MARGIN
                            )
                            if not override_lineage:
                                if raw_best_candidate is candidate:
                                    temporal_spatial_block_reason = "blocked_by_fragment_lineage_lock"
                                print(
                                    f"[IDDBG_LINEAGE_BLOCK] track={track_id} candidate={candidate_profile_id}; "
                                    f"lineage={lineage_lock_profile_id}, "
                                    f"face={candidate.get('face', -1.0):.3f}, "
                                    f"total={candidate.get('total', -1.0):.3f}, "
                                    f"margin={candidate.get('margin', -1.0):.3f}, obs={obs_count}"
                                )
                                continue

                        locked = self._is_profile_locked_by_other_track_in_frame(
                            frame_profile_locks=frame_profile_locks,
                            frame_index=frame_data.frame_index,
                            profile_id=candidate_profile_id,
                            current_track_id=track_id,
                            current_bbox=bbox,
                            duplicate_iou_threshold=0.45,
                        )

                        if locked:
                            if raw_best_candidate is candidate:
                                profile_locked_by_other_track = True
                            continue

                        allowed, reason = self._is_temporal_spatial_reid_allowed(
                            candidate=candidate,
                            face_conf=face_conf,
                            stale_strong_face=STALE_STRONG_FACE,
                            stale_strong_total=STALE_STRONG_TOTAL,
                            stale_strong_margin=STALE_STRONG_MARGIN,
                            entry_reuse_strong_face=ENTRY_REUSE_STRONG_FACE,
                            entry_reuse_strong_face_conf=ENTRY_REUSE_STRONG_FACE_CONF,
                            entry_reuse_strong_margin=ENTRY_REUSE_STRONG_MARGIN,
                        )

                        if not allowed:
                            if raw_best_candidate is candidate:
                                temporal_spatial_block_reason = reason
                            print(
                                f"[IDDBG_TEMPORAL_BLOCK] track={track_id} "
                                f"candidate={candidate_profile_id}, reason={reason}, "
                                f"face={candidate['face']:.3f}, total={candidate['total']:.3f}, "
                                f"margin={candidate['margin']:.3f}, gap={candidate.get('gap_frames')}, "
                                f"risk={candidate.get('temporal_spatial_risk')}"
                            )
                            continue

                        visual_blocked, visual_info = self._is_visual_contradiction_with_profile(
                            current_track=track_id,
                            candidate_profile_id=candidate_profile_id,
                            track_to_profile=track_to_profile,
                            track_body_reid_samples=track_body_reid_samples,
                            candidate_face_score=float(candidate.get("face", -1.0)),
                            candidate_margin=float(candidate.get("margin", -1.0)),
                            min_current_samples=VISUAL_CONTRADICTION_MIN_CURRENT_SAMPLES,
                            min_profile_samples=VISUAL_CONTRADICTION_MIN_PROFILE_SAMPLES,
                            max_avg_top=VISUAL_CONTRADICTION_MAX_AVG_TOP,
                            max_best=VISUAL_CONTRADICTION_MAX_BEST,
                            color_max_avg_top=VISUAL_CONTRADICTION_COLOR_MAX_AVG_TOP,
                            color_max_best=VISUAL_CONTRADICTION_COLOR_MAX_BEST,
                            face_override=VISUAL_CONTRADICTION_FACE_OVERRIDE,
                            margin_override=VISUAL_CONTRADICTION_MARGIN_OVERRIDE,
                        )

                        if visual_blocked:
                            if raw_best_candidate is candidate:
                                temporal_spatial_block_reason = "visual_body_contradiction"
                            print(
                                f"[IDDBG_VISUAL_BLOCK] track={track_id} "
                                f"candidate={candidate_profile_id}, "
                                f"avg_top={visual_info.get('avg_top', 0.0):.3f}, "
                                f"best={visual_info.get('best', 0.0):.3f}, "
                                f"color_avg={visual_info.get('color_avg_top', 0.0):.3f}, "
                                f"color_best={visual_info.get('color_best', 0.0):.3f}, "
                                f"current_samples={visual_info.get('current_samples', 0)}, "
                                f"profile_samples={visual_info.get('profile_samples', 0)}, "
                                f"face={candidate.get('face', -1.0):.3f}, "
                                f"margin={candidate.get('margin', -1.0):.3f}"
                            )
                            continue

                        selected_candidate = candidate
                        break

                    if selected_candidate is not None:
                        short_gap_override_candidate = self._select_short_gap_entry_return_over_far_candidate(
                            selected_candidate=selected_candidate,
                            ranked_candidates=ranked_candidates,
                            face_conf=face_conf,
                        )
                        if short_gap_override_candidate is not None:
                            selected_candidate = short_gap_override_candidate

                    best_candidate_for_debug = selected_candidate or raw_best_candidate

                    if best_candidate_for_debug is None:
                        best_profile_id = None
                        best_total_score = -1.0
                        best_face_score = -1.0
                        best_app_score = 0.0
                        best_margin = -1.0
                    else:
                        best_profile_id = best_candidate_for_debug["profile_id"]
                        best_total_score = best_candidate_for_debug["total"]
                        best_face_score = best_candidate_for_debug["face"]
                        best_app_score = best_candidate_for_debug["app"]
                        best_margin = best_candidate_for_debug["margin"]

                    should_assign_existing = False

                    early_track_needs_strong_gallery_evidence = (
                        obs_count < EARLY_TRACK_GALLERY_MATCH_MIN_OBS
                    )

                    if selected_candidate is not None:
                        best_profile_id = selected_candidate["profile_id"]
                        best_total_score = selected_candidate["total"]
                        best_face_score = selected_candidate["face"]
                        best_app_score = selected_candidate["app"]
                        best_margin = selected_candidate["margin"]

                        is_ambiguous_between_profiles = self._is_ambiguous_ranked_match(
                            ranked_candidates=ranked_candidates,
                            ambiguous_margin=AMBIGUOUS_PENDING_MARGIN,
                            min_total=AMBIGUOUS_PENDING_TOTAL,
                            strong_face=AMBIGUOUS_PENDING_FACE,
                        )

                        if is_ambiguous_between_profiles:
                            temporal_spatial_block_reason = "ambiguous_ranked_candidates"
                        else:
                            selected_risk = selected_candidate.get("temporal_spatial_risk")
                            selected_is_entry_reuse = selected_risk in (
                                "entry_reuse_after_absence",
                                "stale_entry_reuse",
                            )
                            selected_short_gap_strong_return = self._is_short_gap_strong_entry_return_candidate(
                                selected_candidate,
                                face_conf,
                            )
                            # V14: short-gap return is only allowed when visual evidence is also coherent.
                            # This prevents a new long track from being pulled into a recently lost but different
                            # nearby profile just because face is moderately similar. In the failing case, this
                            # stops a new track like track12 from contaminating the earlier track5/P004 profile,
                            # while true tracker-fragment cases still use FragmentContinuityHandoff above.
                            if (
                                NEW_TRACK_DEFAULT_NEW_PROFILE_MODE
                                and not already_assigned
                                and selected_short_gap_strong_return
                                and selected_candidate is not None
                            ):
                                short_gap_visual_ok = (
                                    (
                                        best_face_score >= 0.960
                                        and best_total_score >= 0.945
                                        and best_app_score >= 0.80
                                        and face_conf >= 0.78
                                    )
                                    or (
                                        best_face_score >= 0.988
                                        and best_total_score >= 0.965
                                        and best_app_score >= 0.72
                                        and best_margin >= 0.040
                                        and face_conf >= 0.82
                                    )
                                )
                                if not short_gap_visual_ok:
                                    selected_short_gap_strong_return = False
                                    print(
                                        f"[IDDBG_SHORT_GAP_BLOCK_WEAK_VISUAL] track={track_id} "
                                        f"candidate={best_profile_id}, face={best_face_score:.3f}, "
                                        f"total={best_total_score:.3f}, app={best_app_score:.3f}, "
                                        f"margin={best_margin:.3f}, conf={face_conf:.2f}"
                                    )
                            # ====================================================
                            # CASE A0: FACE-ONLY REID
                            # Dành cho người đội nón / lướt nhanh / xuất hiện lại ở vị trí khác.
                            # Không bắt buộc appearance, không bắt buộc obs_count >= 3.
                            # Chỉ dùng khi face đủ rõ và margin đủ an toàn.
                            # ====================================================
                            if selected_short_gap_strong_return:
                                should_assign_existing = True

                            elif (
                                best_face_score >= FACE_ONLY_REID_THRESHOLD
                                and face_conf >= FACE_ONLY_REID_CONF
                                and best_margin >= FACE_ONLY_REID_MARGIN
                            ):
                                should_assign_existing = True

                            elif best_face_score >= self.online_identity.strict_threshold:
                                if selected_is_entry_reuse:
                                    # Entry-overlap không được match bằng appearance/margin thường.
                                    # Chỉ nhánh FACE_ONLY_REID hoặc short-gap strong return phía trên được phép quyết định.
                                    should_assign_existing = False
                                elif (
                                    obs_count >= MIN_OBS_FOR_STRICT_MATCH
                                    and face_conf >= STRICT_FACE_MIN_CONF
                                    and (
                                        best_app_score >= STRICT_FACE_MIN_APP
                                        or best_margin >= MATCH_MARGIN_STRONG
                                        or best_face_score >= 0.52
                                    )
                                ):
                                    should_assign_existing = True

                            elif best_face_score >= self.online_identity.soft_threshold:
                                if (
                                    not selected_is_entry_reuse
                                    and best_app_score >= SOFT_APP_THRESHOLD
                                    and best_margin >= MATCH_MARGIN_WEAK
                                    and face_conf >= 0.68
                                    and obs_count >= MIN_FRAMES_OBSERVED
                                ):
                                    should_assign_existing = True

                            elif best_face_score >= self.online_identity.weak_track_threshold:
                                if (
                                    not selected_is_entry_reuse
                                    and best_total_score >= WEAK_TOTAL_THRESHOLD
                                    and best_face_score >= WEAK_FACE_MIN_THRESHOLD
                                    and best_app_score >= WEAK_APP_THRESHOLD
                                    and best_margin >= MATCH_MARGIN_WEAK
                                    and face_conf >= 0.70
                                    and obs_count <= WEAK_TRACK_MAX_OBS
                                ):
                                    should_assign_existing = True

                                # Không cho appearance cực mạnh cứu stale candidate.
                                # Đây là nhánh dễ gây lỗi người mới cùng lane/màu áo bị kéo về profile cũ.
                                elif (
                                    not selected_candidate.get("is_stale", False)
                                    and best_total_score >= STRONG_APP_TOTAL_THRESHOLD
                                    and best_face_score >= STRONG_APP_FACE_MIN_THRESHOLD
                                    and best_app_score >= STRONG_APP_THRESHOLD
                                    and best_margin >= MATCH_MARGIN_WEAK
                                    and face_conf >= 0.75
                                    and obs_count <= STRONG_APP_LONG_TRACK_MAX_OBS
                                ):
                                    should_assign_existing = True

                    if should_assign_existing and best_profile_id is not None and selected_candidate is not None:
                        immediate_reid = (
                            best_face_score >= IMMEDIATE_REID_FACE
                            and face_conf >= IMMEDIATE_REID_FACE_CONF
                            and best_margin >= IMMEDIATE_REID_MARGIN
                        )

                        early_track_immediate_reid = (
                            best_face_score >= EARLY_TRACK_GALLERY_IMMEDIATE_FACE
                            and face_conf >= EARLY_TRACK_GALLERY_IMMEDIATE_CONF
                            and best_margin >= EARLY_TRACK_GALLERY_IMMEDIATE_MARGIN
                        )

                        if early_track_needs_strong_gallery_evidence and not early_track_immediate_reid:
                            should_assign_existing = False
                            temporal_spatial_block_reason = "early_track_gallery_match_requires_strong_face"
                            track_debug_status[track_id] = (
                                f"PENDING: early track blocked from gallery match, candidate={best_profile_id}, "
                                f"total={best_total_score:.3f}, face={best_face_score:.3f}, "
                                f"app={best_app_score:.3f}, margin={best_margin:.3f}, "
                                f"conf={face_conf:.2f}, obs={obs_count}"
                            )

                    if should_assign_existing and best_profile_id is not None and selected_candidate is not None:
                        immediate_reid = (
                            best_face_score >= IMMEDIATE_REID_FACE
                            and face_conf >= IMMEDIATE_REID_FACE_CONF
                            and best_margin >= IMMEDIATE_REID_MARGIN
                        )

                        selected_risk = selected_candidate.get("temporal_spatial_risk")
                        selected_is_entry_reuse = selected_risk in (
                            "entry_reuse_after_absence",
                            "stale_entry_reuse",
                        )
                        selected_short_gap_strong_return = self._is_short_gap_strong_entry_return_candidate(
                            selected_candidate,
                            face_conf,
                        )
                        if (
                            NEW_TRACK_DEFAULT_NEW_PROFILE_MODE
                            and not already_assigned
                            and selected_short_gap_strong_return
                            and selected_candidate is not None
                        ):
                            short_gap_visual_ok = (
                                (
                                    best_face_score >= 0.960
                                    and best_total_score >= 0.945
                                    and best_app_score >= 0.80
                                    and face_conf >= 0.78
                                )
                                or (
                                    best_face_score >= 0.988
                                    and best_total_score >= 0.965
                                    and best_app_score >= 0.72
                                    and best_margin >= 0.040
                                    and face_conf >= 0.82
                                )
                            )
                            if not short_gap_visual_ok:
                                selected_short_gap_strong_return = False

                        confirmed_reid = self._update_and_check_candidate_confirmation(
                            track_candidate_history=track_candidate_history,
                            track_id=track_id,
                            candidate=selected_candidate,
                            frame_index=frame_data.frame_index,
                            obs_count=obs_count,
                            min_samples=CONFIRM_REID_MIN_SAMPLES,
                            min_obs=CONFIRM_REID_MIN_OBS,
                            min_avg_face=CONFIRM_REID_MIN_AVG_FACE,
                            min_avg_total=CONFIRM_REID_MIN_AVG_TOTAL,
                            max_history=CONFIRM_REID_MAX_HISTORY,
                        )

                        if NEW_TRACK_DEFAULT_NEW_PROFILE_MODE and not already_assigned and should_assign_existing:
                            selected_risk = selected_candidate.get("temporal_spatial_risk")
                            selected_is_stale_or_risky = bool(selected_candidate.get("is_stale", False)) or selected_risk is not None
                            new_first_strong_reid = (
                                best_face_score >= NEW_FIRST_EXISTING_MIN_FACE
                                and best_total_score >= NEW_FIRST_EXISTING_MIN_TOTAL
                                and best_app_score >= NEW_FIRST_EXISTING_MIN_APP
                                and best_margin >= NEW_FIRST_EXISTING_MIN_MARGIN
                                and face_conf >= NEW_FIRST_EXISTING_MIN_FACE_CONF
                            )
                            if selected_is_stale_or_risky:
                                new_first_strong_reid = (
                                    best_face_score >= NEW_FIRST_STALE_MIN_FACE
                                    and best_total_score >= NEW_FIRST_STALE_MIN_TOTAL
                                    and best_app_score >= NEW_FIRST_STALE_MIN_APP
                                    and best_margin >= NEW_FIRST_STALE_MIN_MARGIN
                                    and face_conf >= NEW_FIRST_EXISTING_MIN_FACE_CONF
                                )

                            # Local/short-gap handoff là trường hợp duy nhất được ưu tiên kéo vào P cũ
                            # dù margin ReID không cao, vì bằng chứng chính là continuity tracklet.
                            if not selected_short_gap_strong_return and not new_first_strong_reid:
                                should_assign_existing = False
                                temporal_spatial_block_reason = "new_first_requires_strong_reid_or_local_handoff"
                                track_debug_status[track_id] = (
                                    f"TENTATIVE: new-first blocks weak existing match, candidate={best_profile_id}, "
                                    f"total={best_total_score:.3f}, face={best_face_score:.3f}, "
                                    f"app={best_app_score:.3f}, margin={best_margin:.3f}, "
                                    f"risk={selected_risk}, conf={face_conf:.2f}, obs={obs_count}"
                                )
                                print(
                                    f"[IDDBG_NEW_FIRST_BLOCK] track={track_id} candidate={best_profile_id}, "
                                    f"total={best_total_score:.3f}, face={best_face_score:.3f}, "
                                    f"app={best_app_score:.3f}, margin={best_margin:.3f}, "
                                    f"risk={selected_risk}, conf={face_conf:.2f}, obs={obs_count}"
                                )

                        # Entry-reuse là rủi ro cao: không cho confirmation bằng appearance/total kéo qua.
                        # Chỉ face rất mạnh mới được match ngay.
                        if selected_is_entry_reuse and not immediate_reid and not selected_short_gap_strong_return:
                            should_assign_existing = False
                            temporal_spatial_block_reason = (
                                "entry_reuse_requires_immediate_strong_face_not_confirmation"
                            )
                        elif not immediate_reid and not confirmed_reid and not selected_short_gap_strong_return:
                            should_assign_existing = False
                            temporal_spatial_block_reason = "candidate_not_confirmed_yet"
                            track_debug_status[track_id] = (
                                f"PENDING: candidate not confirmed, candidate={best_profile_id}, "
                                f"total={best_total_score:.3f}, face={best_face_score:.3f}, "
                                f"app={best_app_score:.3f}, margin={best_margin:.3f}, "
                                f"conf={face_conf:.2f}, obs={obs_count}"
                            )
                        elif selected_short_gap_strong_return and not confirmed_reid:
                            # V66: local handoff is already gated by short-gap + face/appearance continuity.
                            # Accept it immediately to avoid transient P_new in stream output.
                            track_debug_status[track_id] = (
                                f"SHORT_GAP_LOCAL_HANDOFF_V69: candidate={best_profile_id}, "
                                f"total={best_total_score:.3f}, face={best_face_score:.3f}, "
                                f"app={best_app_score:.3f}, margin={best_margin:.3f}, "
                                f"conf={face_conf:.2f}, obs={obs_count}"
                            )

                    if should_assign_existing and best_profile_id is not None:
                        profile_id = best_profile_id
                        track_to_profile[track_id] = profile_id

                        profile_id = self._recover_missing_profile_before_update(
                            profile_id=profile_id,
                            track_id=track_id,
                            embedding=embedding,
                            face_image_path=face.face_image_path,
                            face_confidence=face_conf,
                            frame_index=frame_data.frame_index,
                            observation_count=obs_count,
                            observed_frame_indices=current_track_frames,
                            appearance_signature=appearance_signature if valid_body_for_identity else None,
                            bbox=bbox,
                            track_to_profile=track_to_profile,
                            profile_owner_track=profile_owner_track,
                        )
                        if not profile_id:
                            track_debug_status[track_id] = "PENDING: dropped stale missing profile mapping before existing update"
                            continue

                        self.online_identity.update_profile(
                            profile_id=profile_id,
                            track_id=track_id,
                            embedding=embedding,
                            face_image_path=face.face_image_path,
                            face_confidence=face_conf,
                            frame_index=frame_data.frame_index,
                            observation_count=obs_count,
                            observed_frame_indices=[frame_data.frame_index],
                            appearance_signature=appearance_signature if valid_body_for_identity else None,
                            bbox=bbox,
                            match_score=best_total_score,
                        )
                        track_to_profile[track_id] = profile_id
                        profile_owner_track.setdefault(profile_id, int(track_id))
                        # V10: track matched existing is NOT a new-first profile.
                        # Only tracks that actually created a fresh P_id should be eligible
                        # for controlled return relink later.

                        self._lock_profile_in_frame(
                            frame_profile_locks=frame_profile_locks,
                            frame_index=frame_data.frame_index,
                            profile_id=profile_id,
                            track_id=track_id,
                            bbox=bbox,
                        )

                        track_debug_status[track_id] = (
                            f"MATCHED: Track {track_id} -> {profile_id}, "
                            f"total={best_total_score:.3f}, "
                            f"face={best_face_score:.3f}, "
                            f"app={best_app_score:.3f}, "
                            f"margin={best_margin:.3f}, "
                            f"risk={selected_candidate.get('temporal_spatial_risk') if selected_candidate else None}, "
                            f"conf={face_conf:.2f}, "
                            f"obs={obs_count}"
                        )

                        print(
                            f"[IDDBG_ASSIGN] Track {track_id} -> existing {profile_id}, "
                            f"total={best_total_score:.3f}, "
                            f"face={best_face_score:.3f}, "
                            f"app={best_app_score:.3f}, "
                            f"margin={best_margin:.3f}, "
                            f"risk={selected_candidate.get('temporal_spatial_risk') if selected_candidate else None}, "
                            f"conf={face_conf:.2f}, "
                            f"obs={obs_count}"
                        )
                        if selected_short_gap_strong_return:
                            short_gap_return_sticky_locks[int(track_id)] = {
                                "profile_id": profile_id,
                                "reason": "short_gap_strong_return_assign",
                                "assigned_frame": int(frame_data.frame_index),
                            }
                            print(
                                f"[IDDBG_SHORT_GAP_RETURN_STICKY_LOCK] track={track_id} "
                                f"profile={profile_id}, frame={frame_data.frame_index}, "
                                f"face={best_face_score:.3f}, total={best_total_score:.3f}, "
                                f"app={best_app_score:.3f}, gap={selected_candidate.get('gap_frames') if selected_candidate else None}"
                            )
                        if self._is_suspicious_candidate(selected_candidate):
                            self._print_candidate_focus(
                                event="ASSIGN_SUSPECT",
                                track_id=track_id,
                                frame_index=frame_data.frame_index,
                                obs_count=obs_count,
                                face_conf=face_conf,
                                candidates=ranked_candidates,
                                selected=selected_candidate,
                                current_profile_id=None,
                                reason="existing_assign_low_app_or_low_margin_or_risk",
                            )

                        continue

                    # ====================================================
                    # CASE 3: KHÔNG MATCH.
                    # New-first: tạo profile mới sau delay ngắn, trừ khi có local handoff
                    # hoặc ReID cực mạnh vào profile cũ.
                    # ====================================================
                    near_existing_profile = (
                        raw_best_candidate is not None
                        and raw_best_candidate.get("total", -1.0) >= 0.38
                        and not profile_locked_by_other_track
                        and temporal_spatial_block_reason != "visual_body_contradiction"
                    )

                    ambiguous_reid_candidate = (
                        raw_best_candidate is not None
                        and not profile_locked_by_other_track
                        and raw_best_candidate.get("face", -1.0) >= 0.34
                        and raw_best_candidate.get("total", -1.0) >= 0.38
                        and raw_best_candidate.get("margin", 1.0) < AMBIGUOUS_PENDING_MARGIN
                    )

                    best_sample = track_best_identity_sample.get(track_id)

                    has_stable_best_sample = (
                        best_sample is not None
                        and obs_count >= STABLE_TRACK_MIN_OBS_FOR_NEW_PROFILE
                        and best_sample["face_confidence"] >= STABLE_TRACK_MIN_BEST_FACE_CONF
                    )

                    local_handoff_candidate_profile = None
                    if obs_count <= STATIONARY_HANDOFF_MAX_NEW_OBS:
                        local_handoff_candidate_profile = self._find_recent_track_handoff_profile(
                            last_assigned_track_states=last_assigned_track_states,
                            frame_profile_locks=frame_profile_locks,
                            profiles=self.online_identity.profiles,
                            current_frame_index=frame_data.frame_index,
                            current_track_id=track_id,
                            current_bbox=bbox,
                            current_track_frame_bboxes=current_track_frame_bboxes,
                            current_appearance_signature=appearance_signature,
                            appearance_service=self.appearance_service,
                            max_gap_frames=recent_track_handoff_max_gap_frames,
                            duplicate_iou_threshold=RECENT_TRACK_HANDOFF_IOU,
                            containment_threshold=RECENT_TRACK_HANDOFF_CONTAINMENT,
                            center_distance_norm_threshold=RECENT_TRACK_HANDOFF_CENTER_NORM,
                            area_ratio_min=RECENT_TRACK_HANDOFF_AREA_RATIO_MIN,
                            area_ratio_max=RECENT_TRACK_HANDOFF_AREA_RATIO_MAX,
                            old_max_motion_norm=RECENT_TRACK_HANDOFF_OLD_MAX_MOTION_NORM,
                            current_max_motion_norm=RECENT_TRACK_HANDOFF_CURRENT_MAX_MOTION_NORM,
                            min_appearance_score=RECENT_TRACK_HANDOFF_MIN_APPEARANCE,
                        )

                    if NEW_TRACK_DEFAULT_NEW_PROFILE_MODE and NEW_FIRST_BLOCK_NEAR_EXISTING_FROM_PREVENTING_NEW:
                        raw_risk = raw_best_candidate.get("temporal_spatial_risk") if raw_best_candidate else None
                        raw_is_stale_or_risky = (
                            raw_best_candidate is not None
                            and (bool(raw_best_candidate.get("is_stale", False)) or raw_risk is not None)
                        )
                        raw_strong_reid_for_block = False
                        if raw_best_candidate is not None:
                            if raw_is_stale_or_risky:
                                raw_strong_reid_for_block = (
                                    raw_best_candidate.get("face", -1.0) >= NEW_FIRST_STALE_MIN_FACE
                                    and raw_best_candidate.get("total", -1.0) >= NEW_FIRST_STALE_MIN_TOTAL
                                    and raw_best_candidate.get("app", -1.0) >= NEW_FIRST_STALE_MIN_APP
                                    and raw_best_candidate.get("margin", -1.0) >= NEW_FIRST_STALE_MIN_MARGIN
                                    and face_conf >= NEW_FIRST_EXISTING_MIN_FACE_CONF
                                )
                            else:
                                raw_strong_reid_for_block = (
                                    raw_best_candidate.get("face", -1.0) >= NEW_FIRST_EXISTING_MIN_FACE
                                    and raw_best_candidate.get("total", -1.0) >= NEW_FIRST_EXISTING_MIN_TOTAL
                                    and raw_best_candidate.get("app", -1.0) >= NEW_FIRST_EXISTING_MIN_APP
                                    and raw_best_candidate.get("margin", -1.0) >= NEW_FIRST_EXISTING_MIN_MARGIN
                                    and face_conf >= NEW_FIRST_EXISTING_MIN_FACE_CONF
                                )

                        if local_handoff_candidate_profile is None and not raw_strong_reid_for_block:
                            # Candidate yếu/mơ hồ không được giữ track mãi ở PENDING;
                            # cho phép tạo P mới sau delay ngắn.
                            near_existing_profile = False
                            ambiguous_reid_candidate = False

                    body_sample_count_for_track = len(track_body_reid_samples.get(int(track_id), []) or [])
                    delayed_new_profile_ready = (
                        obs_count >= max(int(DELAYED_NEW_PROFILE_MIN_OBS), int(DELAYED_NEW_PROFILE_MIN_SECONDS * video_fps))
                        and body_sample_count_for_track >= int(DELAYED_NEW_PROFILE_MIN_BODY_SAMPLES)
                    )

                    can_create_new_profile_now = (
                        delayed_new_profile_ready
                        and face_conf >= MIN_FACE_CONFIDENCE_FOR_NEW_PROFILE
                        and valid_body_for_identity
                        and not ambiguous_reid_candidate
                        and local_handoff_candidate_profile is None
                        and (
                            not near_existing_profile
                            or obs_count >= MAX_PENDING_OBS_BEFORE_NEW_PROFILE
                        )
                    )

                    can_create_from_best_sample = (
                        delayed_new_profile_ready
                        and has_stable_best_sample
                        and not near_existing_profile
                        and local_handoff_candidate_profile is None
                    )

                    if can_create_new_profile_now or can_create_from_best_sample:
                        if can_create_from_best_sample:
                            sample = best_sample
                        else:
                            sample = {
                                "embedding": embedding,
                                "face_image_path": face.face_image_path,
                                "face_confidence": face_conf,
                                "frame_index": frame_data.frame_index,
                                "observation_count": obs_count,
                                "observed_frame_indices": current_track_frames,
                                "appearance_signature": appearance_signature,
                                "bbox": bbox,
                            }

                        profile_id = self.online_identity.create_new_profile(
                            track_id=track_id,
                            embedding=sample["embedding"],
                            face_image_path=sample["face_image_path"],
                            face_confidence=sample["face_confidence"],
                            frame_index=sample["frame_index"],
                            observation_count=obs_count,
                            observed_frame_indices=current_track_frames,
                            appearance_signature=sample["appearance_signature"],
                            bbox=sample["bbox"],
                        )

                        # QUAN TRỌNG: dòng này phải nằm trong if, sau khi profile_id đã được tạo
                        track_to_profile[track_id] = profile_id
                        profile_owner_track.setdefault(profile_id, int(track_id))
                        # V10: this is the actual new-first creation point.
                        # Mark it so controlled-return can later merge this temporary P
                        # back into an older stable P if evidence becomes strong.
                        new_first_profile_created_frame[int(track_id)] = int(frame_data.frame_index)

                        self._lock_profile_in_frame(
                            frame_profile_locks=frame_profile_locks,
                            frame_index=frame_data.frame_index,
                            profile_id=profile_id,
                            track_id=track_id,
                            bbox=sample["bbox"],
                        )

                        track_debug_status[track_id] = (
                            f"NEW: Track {track_id} -> {profile_id}, "
                            f"from_best_sample={can_create_from_best_sample}, "
                            f"total={best_total_score:.3f}, "
                            f"face={best_face_score:.3f}, "
                            f"app={best_app_score:.3f}, "
                            f"margin={best_margin:.3f}, "
                            f"gate_reason={temporal_spatial_block_reason}, "
                            f"current_conf={face_conf:.2f}, "
                            f"best_conf={sample['face_confidence']:.2f}, "
                            f"obs={obs_count}"
                        )

                        print(
                            f"[IDDBG_ASSIGN] Track {track_id} -> new {profile_id}, "
                            f"from_best_sample={can_create_from_best_sample}, "
                            f"total={best_total_score:.3f}, "
                            f"face={best_face_score:.3f}, "
                            f"app={best_app_score:.3f}, "
                            f"margin={best_margin:.3f}, "
                            f"current_conf={face_conf:.2f}, "
                            f"best_conf={sample['face_confidence']:.2f}, "
                            f"obs={obs_count}"
                        )
                        if raw_best_candidate is not None and self._is_suspicious_candidate(raw_best_candidate):
                            self._print_candidate_focus(
                                event="NEW_DESPITE_CANDIDATE",
                                track_id=track_id,
                                frame_index=frame_data.frame_index,
                                obs_count=obs_count,
                                face_conf=face_conf,
                                candidates=ranked_candidates,
                                selected=raw_best_candidate,
                                current_profile_id=None,
                                reason=temporal_spatial_block_reason or "new_profile_after_candidate_rejected",
                            )

                    else:
                        best_conf = best_sample["face_confidence"] if best_sample else -1.0

                        track_debug_status[track_id] = (
                            f"PENDING: wait better evidence, "
                            f"near_existing={near_existing_profile}, "
                            f"valid_body={valid_body_for_identity}, "
                            f"total={best_total_score:.3f}, "
                            f"face={best_face_score:.3f}, "
                            f"app={best_app_score:.3f}, "
                            f"margin={best_margin:.3f}, "
                            f"gate_reason={temporal_spatial_block_reason}, "
                            f"current_conf={face_conf:.2f}, "
                            f"best_conf={best_conf:.2f}, "
                            f"obs={obs_count}"
                        )
                # end for p in tracked_persons

                # TRUE DELAYED REALTIME EVENT CORRECTIONS
                # ========================================================
                # Chỉ dùng dữ liệu đã thấy đến frame hiện tại. Không chờ hết video.
                active_track_ids = {int(tp.get("track_id")) for tp in tracked_persons}
                current_frame_index = int(frame_data.frame_index)
                self._print_multi_profile_if_needed(
                    frame_index=current_frame_index,
                    active_track_ids=active_track_ids,
                    track_to_profile=track_to_profile,
                )
                active_track_bboxes = {
                    int(tp.get("track_id")): tp.get("bbox")
                    for tp in tracked_persons
                    if tp.get("track_id") is not None and tp.get("bbox") is not None
                }
                self._mark_same_frame_profile_conflicts_no_split(
                    frame_index=current_frame_index,
                    active_track_ids=active_track_ids,
                    active_track_bboxes=active_track_bboxes,
                    track_to_profile=track_to_profile,
                    track_debug_status=track_debug_status,
                    profile_owner_track=profile_owner_track,
                    track_observation_counts=track_observation_counts,
                )
                # v9: if a track was split out because same-frame proved it was a different person,
                # treat it like a fresh new-first profile so controlled return can still rescue
                # true comeback cases such as a track that was first inherited from a wrong nearby P.
                for _tid, _status in list(track_debug_status.items()):
                    if str(_status).startswith("SAME_FRAME_HARD_SPLIT"):
                        same_frame_hard_split_tracks.add(int(_tid))
                        if int(_tid) not in new_first_profile_created_frame:
                            new_first_profile_created_frame[int(_tid)] = int(current_frame_index)


                newly_closed_tracks = []
                for known_tid in list(track_observation_counts.keys()):
                    known_tid = int(known_tid)
                    if known_tid in active_track_ids or known_tid in realtime_closed_tracks:
                        continue
                    known_boxes = track_frame_bboxes.get(known_tid) or {}
                    if not known_boxes:
                        continue
                    last_seen_frame = max(int(f) for f in known_boxes.keys())
                    if current_frame_index - last_seen_frame >= realtime_track_close_timeout_frames:
                        realtime_closed_tracks.add(known_tid)
                        newly_closed_tracks.append(known_tid)

                should_run_realtime_correction = (
                    (current_frame_index % REALTIME_CORRECTION_INTERVAL_FRAMES == 0)
                    or bool(newly_closed_tracks)
                )

                if should_run_realtime_correction:
                    realtime_correction_ticks += 1
                    if newly_closed_tracks:
                        print(
                            f"[RealtimeTrackClosed] frame={current_frame_index}, "
                            f"closed_tracks={newly_closed_tracks}"
                        )

                    # 1) rescue track pending đã đủ ổn định.
                    self._rescue_stable_pending_tracks(
                        track_observation_counts=track_observation_counts,
                        track_to_profile=track_to_profile,
                        track_best_identity_sample=track_best_identity_sample,
                        track_frame_indices=track_frame_indices,
                        track_frame_bboxes=track_frame_bboxes,
                        track_debug_status=track_debug_status,
                        min_obs=50,
                        min_best_face_conf=0.75,
                    )

                    # 2) correction theo lineage cụ thể của track vừa đủ/closed.
                    self._apply_final_track_lineage_corrections(
                        track_to_profile=track_to_profile,
                        track_frame_bboxes=track_frame_bboxes,
                        track_observation_counts=track_observation_counts,
                        track_debug_status=track_debug_status,
                        max_gap_frames=max(1, int(6.0 * video_fps)),
                    )

                    # 3) body tracklet correction cho track fragmentation.
                    self._apply_body_tracklet_reid_corrections(
                        track_to_profile=track_to_profile,
                        track_frame_bboxes=track_frame_bboxes,
                        track_observation_counts=track_observation_counts,
                        track_body_reid_samples=track_body_reid_samples,
                        track_debug_status=track_debug_status,
                        max_gap_frames=max(1, int(BODY_TRACKLET_CORRECTION_MAX_GAP_SECONDS * video_fps)),
                        min_old_obs=BODY_TRACKLET_CORRECTION_MIN_OLD_OBS,
                        min_new_obs=BODY_TRACKLET_CORRECTION_MIN_NEW_OBS,
                        min_avg_top=BODY_TRACKLET_CORRECTION_MIN_AVG_TOP,
                        min_best=BODY_TRACKLET_CORRECTION_MIN_BEST,
                        min_combined=BODY_TRACKLET_CORRECTION_MIN_COMBINED,
                        margin=BODY_TRACKLET_CORRECTION_MARGIN,
                        center_norm_limit=BODY_TRACKLET_CORRECTION_CENTER_NORM,
                        allow_overlap_frames=BODY_TRACKLET_CORRECTION_ALLOW_OVERLAP_FRAMES,
                    )

                    # 4) Generic tracklet graph linking: tự nối fragment vào profile đã tồn tại,
                    # không hard-code track id và không tạo P_id mới trong correction tick.
                    if GENERIC_TRACKLET_LINK_ENABLED:
                        self._apply_generic_tracklet_linking(
                            active_track_ids=active_track_ids,
                            track_to_profile=track_to_profile,
                            track_frame_bboxes=track_frame_bboxes,
                            track_observation_counts=track_observation_counts,
                            track_body_reid_samples=track_body_reid_samples,
                            track_best_identity_sample=track_best_identity_sample,
                            track_debug_status=track_debug_status,
                            profile_owner_track=profile_owner_track,
                            max_gap_frames=max(1, int(GENERIC_TRACKLET_LINK_MAX_GAP_SECONDS * video_fps)),
                            max_center_norm=GENERIC_TRACKLET_LINK_MAX_CENTER_NORM,
                            min_old_obs=GENERIC_TRACKLET_LINK_MIN_OLD_OBS,
                            min_new_obs=GENERIC_TRACKLET_LINK_MIN_NEW_OBS,
                            max_overlap_frames=GENERIC_TRACKLET_LINK_MAX_OVERLAP_FRAMES,
                            min_body_avg=GENERIC_TRACKLET_LINK_MIN_BODY_AVG,
                            min_body_best=GENERIC_TRACKLET_LINK_MIN_BODY_BEST,
                            min_color_avg=GENERIC_TRACKLET_LINK_MIN_COLOR_AVG,
                            min_face=GENERIC_TRACKLET_LINK_MIN_FACE,
                            min_combined=GENERIC_TRACKLET_LINK_MIN_COMBINED,
                            create_new_profiles=REALTIME_CORRECTION_CAN_CREATE_PROFILE,
                        )

                    # 4b) V16 reverse successor linking:
                    # If a weak/no-face predecessor was pulled into the wrong nearby profile,
                    # a later clean successor can absorb it back into the successor's P_id.
                    self._apply_reverse_successor_tracklet_linking(
                        active_track_ids=active_track_ids,
                        track_to_profile=track_to_profile,
                        track_frame_bboxes=track_frame_bboxes,
                        track_observation_counts=track_observation_counts,
                        track_body_reid_samples=track_body_reid_samples,
                        track_best_identity_sample=track_best_identity_sample,
                        track_debug_status=track_debug_status,
                        max_gap_frames=max(1, int(8.0 * video_fps)),
                        max_center_norm=0.30,
                        min_prev_obs=45,
                        min_current_obs=45,
                        max_overlap_frames=1,
                        min_body_avg=0.72,
                        min_body_best=0.78,
                        min_color_avg=0.72,
                    )

                    if BODY_ONLY_RETURN_LINK_ENABLED:
                        self._apply_body_only_return_tracklet_linking(
                            active_track_ids=active_track_ids,
                            track_to_profile=track_to_profile,
                            track_frame_bboxes=track_frame_bboxes,
                            track_observation_counts=track_observation_counts,
                            track_body_reid_samples=track_body_reid_samples,
                            track_best_identity_sample=track_best_identity_sample,
                            track_debug_status=track_debug_status,
                            max_gap_frames=max(1, int(BODY_ONLY_RETURN_LINK_MAX_GAP_SECONDS * video_fps)),
                            min_prev_obs=BODY_ONLY_RETURN_LINK_MIN_PREV_OBS,
                            min_cur_obs=BODY_ONLY_RETURN_LINK_MIN_CUR_OBS,
                            min_prev_samples=BODY_ONLY_RETURN_LINK_MIN_PREV_SAMPLES,
                            min_cur_samples=BODY_ONLY_RETURN_LINK_MIN_CUR_SAMPLES,
                            min_body_avg=BODY_ONLY_RETURN_LINK_MIN_BODY_AVG,
                            min_body_best=BODY_ONLY_RETURN_LINK_MIN_BODY_BEST,
                            min_color_avg=BODY_ONLY_RETURN_LINK_MIN_COLOR_AVG,
                            min_combined=BODY_ONLY_RETURN_LINK_MIN_COMBINED,
                        )

                    # V65 short-video-only stitching. The long video path is left untouched.
                    if SHORT_VIDEO_STITCHING_ENABLED and int(frame_result.extracted_count) <= int(SHORT_VIDEO_STITCHING_MAX_EXTRACTED_FRAMES):
                        self._apply_short_video_duplicate_fragment_linking(
                            active_track_ids=active_track_ids,
                            track_to_profile=track_to_profile,
                            track_frame_bboxes=track_frame_bboxes,
                            track_observation_counts=track_observation_counts,
                            track_body_reid_samples=track_body_reid_samples,
                            track_best_identity_sample=track_best_identity_sample,
                            track_debug_status=track_debug_status,
                            max_short_obs=SHORT_DUP_FRAGMENT_MAX_OBS,
                            max_short_face_conf=SHORT_DUP_FRAGMENT_MAX_FACE_CONF,
                            min_stable_obs=SHORT_DUP_STABLE_MIN_OBS,
                            min_overlap_frames=SHORT_DUP_MIN_OVERLAP_FRAMES,
                            max_near_gap_frames=max(4, int(0.85 * video_fps)),
                            max_center_norm=SHORT_DUP_MAX_CENTER_NORM,
                            min_iou=SHORT_DUP_MIN_IOU,
                            min_containment=SHORT_DUP_MIN_CONTAINMENT,
                            min_body_best=SHORT_DUP_MIN_BODY_BEST,
                            min_color_best=SHORT_DUP_MIN_COLOR_BEST,
                        )
                        self._apply_short_video_no_face_to_face_successor_linking(
                            active_track_ids=active_track_ids,
                            track_to_profile=track_to_profile,
                            track_frame_bboxes=track_frame_bboxes,
                            track_observation_counts=track_observation_counts,
                            track_body_reid_samples=track_body_reid_samples,
                            track_best_identity_sample=track_best_identity_sample,
                            track_debug_status=track_debug_status,
                            max_gap_frames=max(1, int(SHORT_NO_FACE_SUCCESSOR_MAX_GAP_SECONDS * video_fps)),
                            min_prev_obs=SHORT_NO_FACE_SUCCESSOR_MIN_PREV_OBS,
                            min_cur_obs=SHORT_NO_FACE_SUCCESSOR_MIN_CUR_OBS,
                            max_prev_face_conf=SHORT_NO_FACE_SUCCESSOR_MAX_PREV_FACE_CONF,
                            min_cur_face_conf=SHORT_NO_FACE_SUCCESSOR_MIN_CUR_FACE_CONF,
                            min_body_best=SHORT_NO_FACE_SUCCESSOR_MIN_BODY_BEST,
                            min_body_avg=SHORT_NO_FACE_SUCCESSOR_MIN_BODY_AVG,
                            min_color_best=SHORT_NO_FACE_SUCCESSOR_MIN_COLOR_BEST,
                            min_combined=SHORT_NO_FACE_SUCCESSOR_MIN_COMBINED,
                        )

                    # 5) visual/color outlier split realtime rất hẹp; chỉ split khi outlier rõ.
                    self._split_body_visual_outlier_tracks(
                        track_to_profile=track_to_profile,
                        track_body_reid_samples=track_body_reid_samples,
                        track_observation_counts=track_observation_counts,
                        track_debug_status=track_debug_status,
                        min_profile_tracks=BODY_OUTLIER_SPLIT_MIN_PROFILE_TRACKS,
                        min_obs=BODY_OUTLIER_SPLIT_MIN_OBS,
                        min_current_samples=BODY_OUTLIER_SPLIT_MIN_CURRENT_SAMPLES,
                        min_peer_samples=BODY_OUTLIER_SPLIT_MIN_PEER_SAMPLES,
                        max_avg_top=BODY_OUTLIER_SPLIT_MAX_AVG_TOP,
                        max_best=BODY_OUTLIER_SPLIT_MAX_BEST,
                        color_max_avg_top=BODY_OUTLIER_SPLIT_COLOR_MAX_AVG_TOP,
                        color_max_best=BODY_OUTLIER_SPLIT_COLOR_MAX_BEST,
                    )


                    # 5) realtime-safe episode split.
                    # Quan trọng cho camera thật: không đợi hết video mới tách P_id.
                    # Nếu một profile lớn bị "kéo dài" qua một khoảng vắng mặt lớn,
                    # cụm track mới ổn định sẽ được tách ngay trong correction tick.
                    # Nhờ vậy bbox trên camera và dữ liệu trajectory dùng cùng mapping hiện tại.
                    if EPISODE_SPLIT_ENABLED:
                        self._split_stale_profile_episodes(
                            track_to_profile=track_to_profile,
                            track_frame_bboxes=track_frame_bboxes,
                            track_observation_counts=track_observation_counts,
                            track_debug_status=track_debug_status,
                            stale_gap_frames=max(1, int(EPISODE_SPLIT_STALE_GAP_SECONDS * video_fps)),
                            min_profile_tracks=EPISODE_SPLIT_MIN_PROFILE_TRACKS,
                            min_tail_tracks=EPISODE_SPLIT_MIN_TAIL_TRACKS,
                            min_tail_total_obs=EPISODE_SPLIT_MIN_TAIL_TOTAL_OBS,
                            min_each_tail_obs=EPISODE_SPLIT_MIN_EACH_TAIL_OBS,
                            realtime_frame_index=current_frame_index,
                        )

                    # 6) camera-ready profile refinement.
                    # Không đợi hết video: sau mỗi correction tick, nếu một track đang
                    # nằm trong profile kém hợp hơn profile khác, chuyển riêng track đó.
                    # Giữ nguyên track_id để trajectory vẫn vẽ được theo P_id mới.
                    if PROFILE_REFINE_ENABLED:
                        self._apply_camera_ready_profile_refinements(
                            track_to_profile=track_to_profile,
                            track_frame_bboxes=track_frame_bboxes,
                            track_observation_counts=track_observation_counts,
                            track_body_reid_samples=track_body_reid_samples,
                            track_debug_status=track_debug_status,
                            min_track_obs=PROFILE_REFINE_MIN_TRACK_OBS,
                            min_track_samples=PROFILE_REFINE_MIN_TRACK_SAMPLES,
                            min_target_score=PROFILE_REFINE_MIN_TARGET_SCORE,
                            move_margin=PROFILE_REFINE_MOVE_MARGIN,
                            magnet_move_margin=PROFILE_REFINE_MAGNET_MOVE_MARGIN,
                            magnet_profile_tracks=PROFILE_REFINE_MAGNET_PROFILE_TRACKS,
                            color_split_min_profile_tracks=PROFILE_REFINE_COLOR_SPLIT_MIN_PROFILE_TRACKS,
                            color_split_min_track_obs=PROFILE_REFINE_COLOR_SPLIT_MIN_TRACK_OBS,
                            max_passes=PROFILE_REFINE_PASSES,
                            realtime_frame_index=current_frame_index,
                        )

                    # 7) Các rule trước đây chỉ chạy cuối video, nay chạy trong realtime tick.
                    # Tất cả chỉ dùng dữ liệu đã thấy đến current_frame_index, nên camera có thể
                    # sửa/split P_id ngay sau delay thay vì đợi hết video.
                    if FINAL_PEER_OUTLIER_SPLIT_ENABLED:
                        self._split_cohesive_peer_visual_outlier_tracks(
                            track_to_profile=track_to_profile,
                            track_body_reid_samples=track_body_reid_samples,
                            track_observation_counts=track_observation_counts,
                            track_debug_status=track_debug_status,
                            min_profile_tracks=FINAL_PEER_OUTLIER_MIN_PROFILE_TRACKS,
                            min_track_obs=FINAL_PEER_OUTLIER_MIN_TRACK_OBS,
                            min_track_samples=FINAL_PEER_OUTLIER_MIN_TRACK_SAMPLES,
                            min_peer_tracks=FINAL_PEER_OUTLIER_MIN_PEER_TRACKS,
                            min_peer_obs=FINAL_PEER_OUTLIER_MIN_PEER_OBS,
                            min_peer_samples=FINAL_PEER_OUTLIER_MIN_PEER_SAMPLES,
                            max_body_avg=FINAL_PEER_OUTLIER_MAX_BODY_AVG,
                            max_body_best=FINAL_PEER_OUTLIER_MAX_BODY_BEST,
                            max_color_avg=FINAL_PEER_OUTLIER_MAX_COLOR_AVG,
                            max_color_best=FINAL_PEER_OUTLIER_MAX_COLOR_BEST,
                            min_peer_cohesion_body=FINAL_PEER_OUTLIER_MIN_PEER_COHESION_BODY,
                            min_peer_cohesion_color=FINAL_PEER_OUTLIER_MIN_PEER_COHESION_COLOR,
                        )

                    if FINAL_COHESIVE_SUBGROUP_SPLIT_ENABLED:
                        self._split_cohesive_visual_subgroup_profiles(
                            track_to_profile=track_to_profile,
                            track_frame_bboxes=track_frame_bboxes,
                            track_body_reid_samples=track_body_reid_samples,
                            track_observation_counts=track_observation_counts,
                            track_debug_status=track_debug_status,
                            min_profile_tracks=FINAL_COHESIVE_SUBGROUP_MIN_PROFILE_TRACKS,
                            min_group_tracks=FINAL_COHESIVE_SUBGROUP_MIN_GROUP_TRACKS,
                            max_group_tracks=FINAL_COHESIVE_SUBGROUP_MAX_GROUP_TRACKS,
                            min_rest_tracks=FINAL_COHESIVE_SUBGROUP_MIN_REST_TRACKS,
                            min_track_obs=FINAL_COHESIVE_SUBGROUP_MIN_TRACK_OBS,
                            min_track_samples=FINAL_COHESIVE_SUBGROUP_MIN_TRACK_SAMPLES,
                            min_group_body=FINAL_COHESIVE_SUBGROUP_MIN_GROUP_BODY,
                            min_group_color=FINAL_COHESIVE_SUBGROUP_MIN_GROUP_COLOR,
                            max_rest_body=FINAL_COHESIVE_SUBGROUP_MAX_REST_BODY,
                            max_rest_color=FINAL_COHESIVE_SUBGROUP_MAX_REST_COLOR,
                            min_start_gap_frames=max(1, int(FINAL_COHESIVE_SUBGROUP_MIN_START_GAP_SECONDS * video_fps)),
                        )

                    if FINAL_HEAD_SPLIT_ENABLED:
                        self._split_early_head_episode_profiles(
                            track_to_profile=track_to_profile,
                            track_frame_bboxes=track_frame_bboxes,
                            track_observation_counts=track_observation_counts,
                            track_debug_status=track_debug_status,
                            stale_gap_frames=max(1, int(FINAL_HEAD_SPLIT_STALE_GAP_SECONDS * video_fps)),
                            min_profile_tracks=FINAL_HEAD_SPLIT_MIN_PROFILE_TRACKS,
                            max_head_tracks=FINAL_HEAD_SPLIT_MAX_HEAD_TRACKS,
                            min_head_total_obs=FINAL_HEAD_SPLIT_MIN_HEAD_TOTAL_OBS,
                            min_tail_tracks=FINAL_HEAD_SPLIT_MIN_TAIL_TRACKS,
                            min_tail_total_obs=FINAL_HEAD_SPLIT_MIN_TAIL_TOTAL_OBS,
                            min_each_tail_obs=FINAL_HEAD_SPLIT_MIN_EACH_TAIL_OBS,
                        )

                    if FINAL_TAIL_GROUP_SPLIT_ENABLED:
                        self._split_late_tail_group_profiles(
                            track_to_profile=track_to_profile,
                            track_frame_bboxes=track_frame_bboxes,
                            track_observation_counts=track_observation_counts,
                            track_debug_status=track_debug_status,
                            gap_frames=max(1, int(FINAL_TAIL_GROUP_SPLIT_GAP_SECONDS * video_fps)),
                            min_profile_tracks=FINAL_TAIL_GROUP_SPLIT_MIN_PROFILE_TRACKS,
                            max_head_tracks=FINAL_TAIL_GROUP_SPLIT_MAX_HEAD_TRACKS,
                            min_head_total_obs=FINAL_TAIL_GROUP_SPLIT_MIN_HEAD_TOTAL_OBS,
                            min_tail_tracks=FINAL_TAIL_GROUP_SPLIT_MIN_TAIL_TRACKS,
                            min_tail_total_obs=FINAL_TAIL_GROUP_SPLIT_MIN_TAIL_TOTAL_OBS,
                            min_each_tail_obs=FINAL_TAIL_GROUP_SPLIT_MIN_EACH_TAIL_OBS,
                        )

                    if FINAL_SHORT_GAP_RETURN_REPAIR_ENABLED:
                        self._final_move_late_track_to_short_gap_return_profile(
                            track_to_profile=track_to_profile,
                            track_frame_bboxes=track_frame_bboxes,
                            track_observation_counts=track_observation_counts,
                            track_body_reid_samples=track_body_reid_samples,
                            track_debug_status=track_debug_status,
                            min_track_obs=FINAL_SHORT_GAP_RETURN_REPAIR_MIN_TRACK_OBS,
                            max_candidate_gap_frames=max(1, int(FINAL_SHORT_GAP_RETURN_REPAIR_MAX_CANDIDATE_GAP_SECONDS * video_fps)),
                            min_current_profile_gap_frames=max(1, int(FINAL_SHORT_GAP_RETURN_REPAIR_MIN_CURRENT_GAP_SECONDS * video_fps)),
                        )

                    if FINAL_EARLY_SINGLETON_SPLIT_ENABLED:
                        self._split_late_tracks_from_early_singleton_profiles(
                            track_to_profile=track_to_profile,
                            track_frame_bboxes=track_frame_bboxes,
                            track_observation_counts=track_observation_counts,
                            track_debug_status=track_debug_status,
                            gap_frames=max(1, int(FINAL_EARLY_SINGLETON_SPLIT_GAP_SECONDS * video_fps)),
                            max_head_obs=FINAL_EARLY_SINGLETON_MAX_HEAD_OBS,
                            min_tail_total_obs=FINAL_EARLY_SINGLETON_MIN_TAIL_TOTAL_OBS,
                            min_long_tail_obs=FINAL_EARLY_SINGLETON_MIN_LONG_TAIL_OBS,
                        )

                    if FINAL_MIDDLE_SINGLETON_SPLIT_ENABLED:
                        self._split_middle_singleton_bridge_tracks(
                            track_to_profile=track_to_profile,
                            track_frame_bboxes=track_frame_bboxes,
                            track_observation_counts=track_observation_counts,
                            track_debug_status=track_debug_status,
                            max_middle_obs=FINAL_MIDDLE_SINGLETON_MAX_MIDDLE_OBS,
                            min_edge_obs=FINAL_MIDDLE_SINGLETON_MIN_EDGE_OBS,
                            min_head_gap_frames=max(1, int(FINAL_MIDDLE_SINGLETON_MIN_HEAD_GAP_SECONDS * video_fps)),
                            max_tail_gap_frames=max(1, int(FINAL_MIDDLE_SINGLETON_MAX_TAIL_GAP_SECONDS * video_fps)),
                        )

                    if FINAL_SUCCESSOR_OWNS_PREDECESSOR_ENABLED:
                        self._final_merge_recent_predecessor_into_successor_profile(
                            track_to_profile=track_to_profile,
                            track_frame_bboxes=track_frame_bboxes,
                            track_observation_counts=track_observation_counts,
                            track_body_reid_samples=track_body_reid_samples,
                            track_best_identity_sample=track_best_identity_sample,
                            track_debug_status=track_debug_status,
                            max_gap_frames=max(1, int(FINAL_SUCCESSOR_PREDECESSOR_MAX_GAP_SECONDS * video_fps)),
                        )

                    realtime_tail_pair_allowed = (
                        len(track_observation_counts) <= int(FINAL_SEQUENTIAL_TAIL_PAIR_MAX_TRACK_COUNT)
                        and int(current_frame_index) <= int(FINAL_SEQUENTIAL_TAIL_PAIR_MAX_EXTRACTED_FRAMES)
                    )
                    if FINAL_SEQUENTIAL_TAIL_PAIR_SPLIT_ENABLED and realtime_tail_pair_allowed:
                        self._final_split_sequential_tail_pair_to_new_profile(
                            track_to_profile=track_to_profile,
                            track_frame_bboxes=track_frame_bboxes,
                            track_observation_counts=track_observation_counts,
                            track_body_reid_samples=track_body_reid_samples,
                            track_best_identity_sample=track_best_identity_sample,
                            track_debug_status=track_debug_status,
                            max_pair_gap_frames=max(1, int(FINAL_SEQUENTIAL_TAIL_PAIR_MAX_GAP_SECONDS * video_fps)),
                            min_source_gap_frames=max(1, int(FINAL_SEQUENTIAL_TAIL_PAIR_MIN_SOURCE_GAP_SECONDS * video_fps)),
                        )

                    # Sau mọi correction, enforce invariant ở mức publish/debug, không split tạo P_id mới.
                    self._mark_same_frame_profile_conflicts_no_split(
                        frame_index=current_frame_index,
                        active_track_ids=active_track_ids,
                        active_track_bboxes=active_track_bboxes,
                        track_to_profile=track_to_profile,
                        track_debug_status=track_debug_status,
                    )

                # V55: stable no-face/body-only tracks should not stay PENDING until export.
                # Keep the existing crop guard so partial legs/feet do not become profiles.
                self._assign_stable_no_face_tracks_to_new_profiles_realtime(
                    current_frame_index=current_frame_index,
                    current_frame=image,
                    active_track_ids=active_track_ids,
                    track_to_profile=track_to_profile,
                    track_frame_indices=track_frame_indices,
                    track_frame_bboxes=track_frame_bboxes,
                    track_observation_counts=track_observation_counts,
                    track_body_reid_samples=track_body_reid_samples,
                    track_best_identity_sample=track_best_identity_sample,
                    track_debug_status=track_debug_status,
                    profile_owner_track=profile_owner_track,
                    frame_profile_locks=frame_profile_locks,
                    min_obs=55,
                    min_actual_frames=50,
                    min_body_samples=6,
                    max_good_face_conf=0.70,
                    min_median_height_norm=0.18,
                    min_median_width_norm=0.035,
                    min_median_area_norm=0.012,
                    max_median_top_y_norm=0.78,
                )

                # V66: run short-video stitching once more after body-only profile creation,
                # before taking the stream snapshot. This keeps live/stream display aligned
                # with final short-video tracklet corrections.
                if SHORT_VIDEO_STITCHING_ENABLED and int(frame_result.extracted_count) <= int(SHORT_VIDEO_STITCHING_MAX_EXTRACTED_FRAMES):
                    self._apply_short_video_duplicate_fragment_linking(
                        active_track_ids=active_track_ids,
                        track_to_profile=track_to_profile,
                        track_frame_bboxes=track_frame_bboxes,
                        track_observation_counts=track_observation_counts,
                        track_body_reid_samples=track_body_reid_samples,
                        track_best_identity_sample=track_best_identity_sample,
                        track_debug_status=track_debug_status,
                        max_short_obs=SHORT_DUP_FRAGMENT_MAX_OBS,
                        max_short_face_conf=SHORT_DUP_FRAGMENT_MAX_FACE_CONF,
                        min_stable_obs=SHORT_DUP_STABLE_MIN_OBS,
                        min_overlap_frames=SHORT_DUP_MIN_OVERLAP_FRAMES,
                        max_near_gap_frames=max(4, int(0.85 * video_fps)),
                        max_center_norm=SHORT_DUP_MAX_CENTER_NORM,
                        min_iou=SHORT_DUP_MIN_IOU,
                        min_containment=SHORT_DUP_MIN_CONTAINMENT,
                        min_body_best=SHORT_DUP_MIN_BODY_BEST,
                        min_color_best=SHORT_DUP_MIN_COLOR_BEST,
                    )
                    self._apply_short_video_no_face_to_face_successor_linking(
                        active_track_ids=active_track_ids,
                        track_to_profile=track_to_profile,
                        track_frame_bboxes=track_frame_bboxes,
                        track_observation_counts=track_observation_counts,
                        track_body_reid_samples=track_body_reid_samples,
                        track_best_identity_sample=track_best_identity_sample,
                        track_debug_status=track_debug_status,
                        max_gap_frames=max(1, int(SHORT_NO_FACE_SUCCESSOR_MAX_GAP_SECONDS * video_fps)),
                        min_prev_obs=SHORT_NO_FACE_SUCCESSOR_MIN_PREV_OBS,
                        min_cur_obs=SHORT_NO_FACE_SUCCESSOR_MIN_CUR_OBS,
                        max_prev_face_conf=SHORT_NO_FACE_SUCCESSOR_MAX_PREV_FACE_CONF,
                        min_cur_face_conf=SHORT_NO_FACE_SUCCESSOR_MIN_CUR_FACE_CONF,
                        min_body_best=SHORT_NO_FACE_SUCCESSOR_MIN_BODY_BEST,
                        min_body_avg=SHORT_NO_FACE_SUCCESSOR_MIN_BODY_AVG,
                        min_color_best=SHORT_NO_FACE_SUCCESSOR_MIN_COLOR_BEST,
                        min_combined=SHORT_NO_FACE_SUCCESSOR_MIN_COMBINED,
                    )
                    # V69 rollback: track22 is a valid P04 fragment in the short-video case.
                    # Do not run the v69 overlap override that may move tiny fragments too aggressively.

                prof_identity_sec += time.perf_counter() - identity_t0

                # Snapshot cuối frame để debug video giống màn hình camera thực tế.
                stream_t0 = time.perf_counter()
                current_stream_records = self._snapshot_camera_debug_records(
                    frame_index=current_frame_index,
                    tracked_persons=tracked_persons,
                    track_to_profile=track_to_profile,
                    track_observation_counts=track_observation_counts,
                    track_frame_bboxes=track_frame_bboxes,
                    track_debug_status=track_debug_status,
                    delayed_display_min_frames=delayed_display_min_frames,
                    delayed_display_min_obs=DELAYED_DISPLAY_MIN_OBS,
                )
                if SHORT_VIDEO_STITCHING_ENABLED and int(frame_result.extracted_count) <= int(SHORT_VIDEO_STITCHING_MAX_EXTRACTED_FRAMES):
                    self._suppress_uncertain_short_stream_ids_v69(current_stream_records)
                debug_camera_records.extend(current_stream_records)

                emit_frame = (
                    stream_callback is not None or stream_frame_dir is not None
                ) and (
                    int(stream_emit_every_n_frames) <= 1
                    or int(frame_data.frame_index) % int(stream_emit_every_n_frames) == 0
                    or int(frame_data.frame_index) == int(frame_result.frames[-1].frame_index)
                )

                if emit_frame:
                    progress_percent = (
                        (float(stream_processed_frame_count) / max(1, int(frame_result.extracted_count))) * 100.0
                    )
                    annotated_frame = None
                    annotated_frame_path = None
                    if stream_send_annotated_frame or stream_frame_dir:
                        annotated_frame = self._draw_camera_stream_overlay(
                            image,
                            frame_index=current_frame_index,
                            frame_records=current_stream_records,
                            progress_percent=progress_percent,
                        )
                    if stream_frame_dir:
                        annotated_frame_path = os.path.join(
                            stream_frame_dir,
                            f"stream_frame_{int(current_frame_index):06d}.jpg",
                        )
                        cv2.imwrite(annotated_frame_path, annotated_frame)
                    payload = self._build_stream_payload(
                        frame_index=current_frame_index,
                        progress_percent=progress_percent,
                        frame_records=current_stream_records,
                        annotated_frame_path=annotated_frame_path,
                    )
                    if stream_callback is not None:
                        stream_callback(payload, annotated_frame)
                    if stream_realtime_sleep and target_fps and target_fps > 0:
                        time.sleep(max(0.0, 1.0 / float(target_fps)))

                prof_stream_sec += time.perf_counter() - stream_t0
                prof_frame_count += 1
                if PROFILE_EVERY_N_STREAM_FRAMES > 0 and prof_frame_count % PROFILE_EVERY_N_STREAM_FRAMES == 0:
                    elapsed = max(1e-6, time.perf_counter() - prof_wall_t0)
                    actual_fps = prof_frame_count / elapsed
                    print(
                        f"[PERF_V59] frames={prof_frame_count}/{frame_result.extracted_count} "
                        f"fps={actual_fps:.2f} "
                        f"track_ms={1000.0*prof_track_sec/prof_frame_count:.1f} "
                        f"identity_ms={1000.0*prof_identity_sec/prof_frame_count:.1f} "
                        f"stream_ms={1000.0*prof_stream_sec/prof_frame_count:.1f} "
                        f"heavy_calls={heavy_tracker_calls} light_frames={light_tracker_frames}"
                    )

            # ============================================================
            # EXPORT PROFILES
            # ============================================================
            # Không chạy final video pass. Mọi correction đã chạy theo periodic/track-closed event.
            print(f"[TrueDelayedRealtime] realtime_correction_ticks={realtime_correction_ticks}")

            # Tách episode muộn khỏi profile lớn trước khi export.
            # Đây không phải hard-code track id; nó dựa trên temporal gap + tail cluster.
            if RUN_FINAL_CLEANUP_AT_EXPORT and EPISODE_SPLIT_ENABLED:
                self._split_stale_profile_episodes(
                    track_to_profile=track_to_profile,
                    track_frame_bboxes=track_frame_bboxes,
                    track_observation_counts=track_observation_counts,
                    track_debug_status=track_debug_status,
                    stale_gap_frames=max(1, int(EPISODE_SPLIT_STALE_GAP_SECONDS * video_fps)),
                    min_profile_tracks=EPISODE_SPLIT_MIN_PROFILE_TRACKS,
                    min_tail_tracks=EPISODE_SPLIT_MIN_TAIL_TRACKS,
                    min_tail_total_obs=EPISODE_SPLIT_MIN_TAIL_TOTAL_OBS,
                    min_each_tail_obs=EPISODE_SPLIT_MIN_EACH_TAIL_OBS,
                    realtime_frame_index=None,
                )

            if RUN_FINAL_CLEANUP_AT_EXPORT and PROFILE_REFINE_ENABLED:
                self._apply_camera_ready_profile_refinements(
                    track_to_profile=track_to_profile,
                    track_frame_bboxes=track_frame_bboxes,
                    track_observation_counts=track_observation_counts,
                    track_body_reid_samples=track_body_reid_samples,
                    track_debug_status=track_debug_status,
                    min_track_obs=PROFILE_REFINE_MIN_TRACK_OBS,
                    min_track_samples=PROFILE_REFINE_MIN_TRACK_SAMPLES,
                    min_target_score=PROFILE_REFINE_MIN_TARGET_SCORE,
                    move_margin=PROFILE_REFINE_MOVE_MARGIN,
                    magnet_move_margin=PROFILE_REFINE_MAGNET_MOVE_MARGIN,
                    magnet_profile_tracks=PROFILE_REFINE_MAGNET_PROFILE_TRACKS,
                    color_split_min_profile_tracks=PROFILE_REFINE_COLOR_SPLIT_MIN_PROFILE_TRACKS,
                    color_split_min_track_obs=PROFILE_REFINE_COLOR_SPLIT_MIN_TRACK_OBS,
                    max_passes=PROFILE_REFINE_PASSES,
                    realtime_frame_index=None,
                )

            if RUN_FINAL_CLEANUP_AT_EXPORT and FINAL_PEER_OUTLIER_SPLIT_ENABLED:
                self._split_cohesive_peer_visual_outlier_tracks(
                    track_to_profile=track_to_profile,
                    track_body_reid_samples=track_body_reid_samples,
                    track_observation_counts=track_observation_counts,
                    track_debug_status=track_debug_status,
                    min_profile_tracks=FINAL_PEER_OUTLIER_MIN_PROFILE_TRACKS,
                    min_track_obs=FINAL_PEER_OUTLIER_MIN_TRACK_OBS,
                    min_track_samples=FINAL_PEER_OUTLIER_MIN_TRACK_SAMPLES,
                    min_peer_tracks=FINAL_PEER_OUTLIER_MIN_PEER_TRACKS,
                    min_peer_obs=FINAL_PEER_OUTLIER_MIN_PEER_OBS,
                    min_peer_samples=FINAL_PEER_OUTLIER_MIN_PEER_SAMPLES,
                    max_body_avg=FINAL_PEER_OUTLIER_MAX_BODY_AVG,
                    max_body_best=FINAL_PEER_OUTLIER_MAX_BODY_BEST,
                    max_color_avg=FINAL_PEER_OUTLIER_MAX_COLOR_AVG,
                    max_color_best=FINAL_PEER_OUTLIER_MAX_COLOR_BEST,
                    min_peer_cohesion_body=FINAL_PEER_OUTLIER_MIN_PEER_COHESION_BODY,
                    min_peer_cohesion_color=FINAL_PEER_OUTLIER_MIN_PEER_COHESION_COLOR,
                )

            if RUN_FINAL_CLEANUP_AT_EXPORT and FINAL_COHESIVE_SUBGROUP_SPLIT_ENABLED:
                self._split_cohesive_visual_subgroup_profiles(
                    track_to_profile=track_to_profile,
                    track_frame_bboxes=track_frame_bboxes,
                    track_body_reid_samples=track_body_reid_samples,
                    track_observation_counts=track_observation_counts,
                    track_debug_status=track_debug_status,
                    min_profile_tracks=FINAL_COHESIVE_SUBGROUP_MIN_PROFILE_TRACKS,
                    min_group_tracks=FINAL_COHESIVE_SUBGROUP_MIN_GROUP_TRACKS,
                    max_group_tracks=FINAL_COHESIVE_SUBGROUP_MAX_GROUP_TRACKS,
                    min_rest_tracks=FINAL_COHESIVE_SUBGROUP_MIN_REST_TRACKS,
                    min_track_obs=FINAL_COHESIVE_SUBGROUP_MIN_TRACK_OBS,
                    min_track_samples=FINAL_COHESIVE_SUBGROUP_MIN_TRACK_SAMPLES,
                    min_group_body=FINAL_COHESIVE_SUBGROUP_MIN_GROUP_BODY,
                    min_group_color=FINAL_COHESIVE_SUBGROUP_MIN_GROUP_COLOR,
                    max_rest_body=FINAL_COHESIVE_SUBGROUP_MAX_REST_BODY,
                    max_rest_color=FINAL_COHESIVE_SUBGROUP_MAX_REST_COLOR,
                    min_start_gap_frames=max(1, int(FINAL_COHESIVE_SUBGROUP_MIN_START_GAP_SECONDS * video_fps)),
                )

            if RUN_FINAL_CLEANUP_AT_EXPORT and FINAL_HEAD_SPLIT_ENABLED:
                self._split_early_head_episode_profiles(
                    track_to_profile=track_to_profile,
                    track_frame_bboxes=track_frame_bboxes,
                    track_observation_counts=track_observation_counts,
                    track_debug_status=track_debug_status,
                    stale_gap_frames=max(1, int(FINAL_HEAD_SPLIT_STALE_GAP_SECONDS * video_fps)),
                    min_profile_tracks=FINAL_HEAD_SPLIT_MIN_PROFILE_TRACKS,
                    max_head_tracks=FINAL_HEAD_SPLIT_MAX_HEAD_TRACKS,
                    min_head_total_obs=FINAL_HEAD_SPLIT_MIN_HEAD_TOTAL_OBS,
                    min_tail_tracks=FINAL_HEAD_SPLIT_MIN_TAIL_TRACKS,
                    min_tail_total_obs=FINAL_HEAD_SPLIT_MIN_TAIL_TOTAL_OBS,
                    min_each_tail_obs=FINAL_HEAD_SPLIT_MIN_EACH_TAIL_OBS,
                )

            if RUN_FINAL_CLEANUP_AT_EXPORT and FINAL_TAIL_GROUP_SPLIT_ENABLED:
                self._split_late_tail_group_profiles(
                    track_to_profile=track_to_profile,
                    track_frame_bboxes=track_frame_bboxes,
                    track_observation_counts=track_observation_counts,
                    track_debug_status=track_debug_status,
                    gap_frames=max(1, int(FINAL_TAIL_GROUP_SPLIT_GAP_SECONDS * video_fps)),
                    min_profile_tracks=FINAL_TAIL_GROUP_SPLIT_MIN_PROFILE_TRACKS,
                    max_head_tracks=FINAL_TAIL_GROUP_SPLIT_MAX_HEAD_TRACKS,
                    min_head_total_obs=FINAL_TAIL_GROUP_SPLIT_MIN_HEAD_TOTAL_OBS,
                    min_tail_tracks=FINAL_TAIL_GROUP_SPLIT_MIN_TAIL_TRACKS,
                    min_tail_total_obs=FINAL_TAIL_GROUP_SPLIT_MIN_TAIL_TOTAL_OBS,
                    min_each_tail_obs=FINAL_TAIL_GROUP_SPLIT_MIN_EACH_TAIL_OBS,
                )

            if RUN_FINAL_CLEANUP_AT_EXPORT and FINAL_SHORT_GAP_RETURN_REPAIR_ENABLED:
                self._final_move_late_track_to_short_gap_return_profile(
                    track_to_profile=track_to_profile,
                    track_frame_bboxes=track_frame_bboxes,
                    track_observation_counts=track_observation_counts,
                    track_body_reid_samples=track_body_reid_samples,
                    track_debug_status=track_debug_status,
                    min_track_obs=FINAL_SHORT_GAP_RETURN_REPAIR_MIN_TRACK_OBS,
                    max_candidate_gap_frames=max(1, int(FINAL_SHORT_GAP_RETURN_REPAIR_MAX_CANDIDATE_GAP_SECONDS * video_fps)),
                    min_current_profile_gap_frames=max(1, int(FINAL_SHORT_GAP_RETURN_REPAIR_MIN_CURRENT_GAP_SECONDS * video_fps)),
                )

            if RUN_FINAL_CLEANUP_AT_EXPORT and FINAL_EARLY_SINGLETON_SPLIT_ENABLED:
                self._split_late_tracks_from_early_singleton_profiles(
                    track_to_profile=track_to_profile,
                    track_frame_bboxes=track_frame_bboxes,
                    track_observation_counts=track_observation_counts,
                    track_debug_status=track_debug_status,
                    gap_frames=max(1, int(FINAL_EARLY_SINGLETON_SPLIT_GAP_SECONDS * video_fps)),
                    max_head_obs=FINAL_EARLY_SINGLETON_MAX_HEAD_OBS,
                    min_tail_total_obs=FINAL_EARLY_SINGLETON_MIN_TAIL_TOTAL_OBS,
                    min_long_tail_obs=FINAL_EARLY_SINGLETON_MIN_LONG_TAIL_OBS,
                )

            if RUN_FINAL_CLEANUP_AT_EXPORT and FINAL_MIDDLE_SINGLETON_SPLIT_ENABLED:
                self._split_middle_singleton_bridge_tracks(
                    track_to_profile=track_to_profile,
                    track_frame_bboxes=track_frame_bboxes,
                    track_observation_counts=track_observation_counts,
                    track_debug_status=track_debug_status,
                    max_middle_obs=FINAL_MIDDLE_SINGLETON_MAX_MIDDLE_OBS,
                    min_edge_obs=FINAL_MIDDLE_SINGLETON_MIN_EDGE_OBS,
                    min_head_gap_frames=max(1, int(FINAL_MIDDLE_SINGLETON_MIN_HEAD_GAP_SECONDS * video_fps)),
                    max_tail_gap_frames=max(1, int(FINAL_MIDDLE_SINGLETON_MAX_TAIL_GAP_SECONDS * video_fps)),
                )


            if RUN_FINAL_CLEANUP_AT_EXPORT and FINAL_SUCCESSOR_OWNS_PREDECESSOR_ENABLED:
                self._final_merge_recent_predecessor_into_successor_profile(
                    track_to_profile=track_to_profile,
                    track_frame_bboxes=track_frame_bboxes,
                    track_observation_counts=track_observation_counts,
                    track_body_reid_samples=track_body_reid_samples,
                    track_best_identity_sample=track_best_identity_sample,
                    track_debug_status=track_debug_status,
                    max_gap_frames=max(1, int(FINAL_SUCCESSOR_PREDECESSOR_MAX_GAP_SECONDS * video_fps)),
                )

            # IMPORTANT: v4.2.9 is the stable behavior for the first/long video.
            # Tail-pair split is only enabled for compact videos where the known failure
            # pattern is a late predecessor/successor pair (e.g. track30/33), so it cannot
            # break the correct long-video clusters. This is not track-id hardcoding.
            short_video_tail_pair_allowed = (
                len(track_observation_counts) <= int(FINAL_SEQUENTIAL_TAIL_PAIR_MAX_TRACK_COUNT)
                and int(getattr(frame_result, "extracted_count", 0) or 0) <= int(FINAL_SEQUENTIAL_TAIL_PAIR_MAX_EXTRACTED_FRAMES)
            )
            if RUN_FINAL_CLEANUP_AT_EXPORT and FINAL_SEQUENTIAL_TAIL_PAIR_SPLIT_ENABLED and short_video_tail_pair_allowed:
                self._final_split_sequential_tail_pair_to_new_profile(
                    track_to_profile=track_to_profile,
                    track_frame_bboxes=track_frame_bboxes,
                    track_observation_counts=track_observation_counts,
                    track_body_reid_samples=track_body_reid_samples,
                    track_best_identity_sample=track_best_identity_sample,
                    track_debug_status=track_debug_status,
                    max_pair_gap_frames=max(1, int(FINAL_SEQUENTIAL_TAIL_PAIR_MAX_GAP_SECONDS * video_fps)),
                    min_source_gap_frames=max(1, int(FINAL_SEQUENTIAL_TAIL_PAIR_MIN_SOURCE_GAP_SECONDS * video_fps)),
                )
            elif RUN_FINAL_CLEANUP_AT_EXPORT and FINAL_SEQUENTIAL_TAIL_PAIR_SPLIT_ENABLED:
                print(
                    f"[IDDBG_FINAL_TAIL_PAIR_SKIP_LONG_VIDEO] tracks={len(track_observation_counts)} "
                    f"frames={int(getattr(frame_result, 'extracted_count', 0) or 0)}"
                )

            online_profiles = self.online_identity.export_profiles()

            merged_profiles = self._build_export_profiles_from_current_mapping(
                online_profiles=online_profiles,
                track_to_profile=track_to_profile,
                track_frame_indices=track_frame_indices,
                track_frame_bboxes=track_frame_bboxes,
                track_observation_counts=track_observation_counts,
                track_best_face=track_best_face,
                track_best_identity_sample=track_best_identity_sample,
                skip_empty_or_tiny_profile=EXPORT_SKIP_EMPTY_OR_TINY_PROFILE,
                min_obs_without_face=EXPORT_MIN_PROFILE_OBS_WITHOUT_FACE,
            )

            # Không còn merge cuối video. Mọi relink/handoff phải xảy ra online
            # để debug video và kết quả terminal dùng cùng một track_to_profile.

            # ============================================================
            # DEBUG REPORT
            # ============================================================
            print("\n========== DEBUG ONLINE IDENTITY ==========")
            print(f"raw_track_count      : {len(track_observation_counts)}")
            print(f"assigned_tracks      : {len(track_to_profile)}")
            print(f"online_profiles      : {len(online_profiles)}")
            print(f"final_profiles       : {len(merged_profiles)}")
            print("final_merge_mode     : disabled_online_relink_only")
            print(f"faces_detected       : {len(debug_face_records)}")

            self._print_profile_pull_debug_summary(
                track_to_profile=track_to_profile,
                track_observation_counts=track_observation_counts,
                track_frame_bboxes=track_frame_bboxes,
                track_body_reid_samples=track_body_reid_samples,
            )

            for track_id, count in sorted(track_observation_counts.items()):
                profile_id = track_to_profile.get(track_id, "UNASSIGNED")
                status = track_debug_status.get(track_id, "NO_STATUS")
                face = track_best_face.get(track_id)

                if face is not None:
                    face_info = f"face_conf={face.confidence}"
                else:
                    face_info = "face=None"

                print(
                    f"Track {track_id}: "
                    f"obs={count}, "
                    f"profile={profile_id}, "
                    f"{face_info}, "
                    f"status={status}"
                )

            print("==========================================\n")

            # ============================================================
            # DEBUG VIDEO
            # ============================================================
            if debug_video_path and frame_result.frames:
                print(f"[Debug] Đang dựng video trực quan tại: {debug_video_path}")

                first_frame = cv2.imread(frame_result.frames[0].image_path)

                if first_frame is not None:
                    h, w = first_frame.shape[:2]

                    out_video = cv2.VideoWriter(
                        debug_video_path,
                        cv2.VideoWriter_fourcc(*"mp4v"),
                        target_fps,
                        (w, h),
                    )

                    records_by_frame = {}

                    camera_source_records = debug_camera_records if debug_camera_records else debug_person_records

                    for record in camera_source_records:
                        f_idx = record["frame_index"]

                        if f_idx not in records_by_frame:
                            records_by_frame[f_idx] = []

                        records_by_frame[f_idx].append(record)

                    # Camera mode: không dùng tổng/export cuối video để vẽ ngược lên các frame.
                    # Mỗi frame chỉ hiển thị đúng snapshot đã publish tại thời điểm realtime đó.
                    # Vì vậy counter bên dưới cũng là realtime counter, không phải final counter.

                    for frame_data in frame_result.frames:
                        img = cv2.imread(frame_data.image_path)

                        if img is None:
                            continue

                        frame_records = records_by_frame.get(frame_data.frame_index, [])
                        frame_records = self._collapse_duplicate_debug_records(
                            frame_records=frame_records,
                            track_to_profile=track_to_profile,
                            duplicate_iou_threshold=DUPLICATE_TRACK_IOU_TO_INHERIT_PROFILE,
                            containment_threshold=DUPLICATE_TRACK_CONTAINMENT_TO_INHERIT_PROFILE,
                            center_distance_norm_threshold=DUPLICATE_TRACK_CENTER_DISTANCE_NORM,
                            area_ratio_min=DUPLICATE_TRACK_AREA_RATIO_MIN,
                            area_ratio_max=DUPLICATE_TRACK_AREA_RATIO_MAX,
                        )

                        for record in frame_records:
                            x1, y1, x2, y2 = [int(v) for v in record["bbox"]]
                            track_id = record["track_id"]
                            final_profile_id = record.get("profile_id_snapshot") or track_to_profile.get(track_id, "PENDING")
                            # Camera mode: dùng profile_id_snapshot/display_stage tại thời điểm frame đó.
                            # V69: nếu live snapshot đã suppress P_id để tránh hiện sai, debug video phải tôn trọng suppression đó.
                            if (
                                record.get("display_stage") == "PENDING"
                                and record.get("display_profile_id") is None
                                and "final-only short-video stitch" in str(record.get("display_text") or "")
                            ):
                                display_profile_id, display_stage = "PENDING", "PENDING"
                            else:
                                display_profile_id, display_stage = self._delayed_debug_display_identity(
                                    record=record,
                                    final_profile_id=final_profile_id,
                                    track_frame_bboxes=track_frame_bboxes,
                                    delayed_display_min_frames=delayed_display_min_frames,
                                    delayed_display_min_obs=DELAYED_DISPLAY_MIN_OBS,
                                )

                            if str(display_profile_id).startswith("TEMP_"):
                                box_color = (0, 165, 255)   # orange: TEMP / track-only
                                text_color = (0, 165, 255)
                            elif display_profile_id == "PENDING":
                                box_color = (0, 0, 255)     # red: pending/no identity
                                text_color = (0, 0, 255)
                            elif display_profile_id == "RECHECK" or str(display_profile_id).startswith("CAND:"):
                                box_color = (0, 255, 255)   # yellow: tentative/recheck
                                text_color = (0, 255, 255)
                            else:
                                box_color = (0, 255, 0)     # green: confirmed P_id
                                text_color = (0, 255, 0)

                            cv2.rectangle(img, (x1, y1), (x2, y2), box_color, 2)

                            obs_dbg = int(record.get("observation_count", 0) or 0)
                            label = f"Trk:{track_id} | {display_profile_id} | obs:{obs_dbg}"
                            stage_label = f"{display_stage}"

                            cv2.putText(
                                img,
                                label,
                                (x1, max(0, y1 - 24)),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.55,
                                text_color,
                                2,
                            )
                            cv2.putText(
                                img,
                                stage_label[:58],
                                (x1, max(0, y1 - 6)),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.46,
                                text_color,
                                1,
                            )

                        # CAMERA REALTIME OVERLAY: counter theo snapshot hiện tại, không theo final export.
                        confirmed_ids = {
                            str(r.get("display_profile_id"))
                            for r in frame_records
                            if r.get("display_stage") == "CONFIRMED" and r.get("display_profile_id")
                        }
                        recheck_ids = {
                            str(r.get("display_profile_id"))
                            for r in frame_records
                            if r.get("display_stage") == "RECHECK" and r.get("display_profile_id")
                        }
                        tentative_count = sum(1 for r in frame_records if r.get("display_stage") == "TENTATIVE")
                        pending_count = sum(1 for r in frame_records if r.get("display_stage") in ("TEMP", "PENDING"))
                        visible_count = len(frame_records)
                        counter_label = (
                            f"LIVE CAMERA | frame:{frame_data.frame_index} | visible:{visible_count} | "
                            f"confirmed:{len(confirmed_ids)} | recheck:{len(recheck_ids)} | "
                            f"tentative:{tentative_count} | pending:{pending_count}"
                        )
                        legend_label = "green=CONFIRMED | yellow=TENTATIVE/RECHECK | red=PENDING | orange=TEMP"
                        cv2.putText(img, counter_label, (22, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.78, (0, 0, 0), 4)
                        cv2.putText(img, counter_label, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.78, (0, 255, 0), 2)
                        cv2.putText(img, legend_label, (22, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 0, 0), 3)
                        cv2.putText(img, legend_label, (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 1)

                        out_video.write(img)

                    out_video.release()

            person_paths = self._build_person_paths(
                track_to_profile=track_to_profile,
                track_frame_bboxes=track_frame_bboxes,
            )
            profile_track_ids = self._build_profile_track_ids_v69(
                track_to_profile,
                track_observation_counts=track_observation_counts,
                track_body_reid_samples=track_body_reid_samples,
                track_debug_status=track_debug_status,
                short_video=bool(int(frame_result.extracted_count) <= 900),
            )
            print("\n========== FINAL PROFILE TRACK IDS V69 ==========")
            for _pid, _tids in profile_track_ids.items():
                print(f"[FINAL_PROFILE_TRACK_IDS_V69] profile={_pid} tracks={_tids}")
            print("================================================")

            print("XỬ LÝ ONLINE PIPELINE HOÀN TẤT!")

            # Kết quả cuối dùng chung cho Python caller và UI.
            # Các field chính giữ cùng cấu trúc return của camera_pipeline_service.
            final_result = {
                "raw_track_count": len(track_observation_counts),
                "assigned_tracks": len(track_to_profile),
                "faces_detected": len(debug_face_records),
                "valid_tracklets": len(track_to_profile),
                "merged_profiles": merged_profiles,
                "track_to_profile": track_to_profile,
                "profile_track_ids": profile_track_ids,
                # Dùng cho camera/DB/UI: đường đi đã nhóm theo P_id,
                # nhưng từng điểm vẫn giữ track_id gốc.
                "person_paths": person_paths,
                "stream_mode": bool(stream_callback is not None or stream_frame_dir is not None),
                "stream_emit_every_n_frames": int(stream_emit_every_n_frames),
                "stream_send_annotated_frame": bool(stream_send_annotated_frame),
            }

            # UI đang nhận frame qua stream_callback nên cần thêm một event cuối.
            # annotated_frame=None để frontend phân biệt đây là dữ liệu tổng kết,
            # không phải một frame video mới.
            if stream_callback is not None:
                ui_final_payload = {
                    "type": "pipeline_result",
                    "status": "completed",
                    "progress_percent": 100.0,
                    **final_result,
                }
                stream_callback(ui_final_payload, None)

            return final_result



CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
YUNET_MODEL_PATH = os.path.join(CURRENT_DIR, "models", "face_detection_yunet_2023mar.onnx")
SFACE_MODEL_PATH = os.path.join(CURRENT_DIR, "models", "face_recognition_sface_2021dec.onnx")

video_pipeline_service = VideoProcessingPipelineService(
    yunet_model_path=YUNET_MODEL_PATH,
    sface_model_path=SFACE_MODEL_PATH,
)
