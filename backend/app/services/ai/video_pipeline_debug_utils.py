from typing import Dict, List, Optional

import cv2
import numpy as np


class VideoPipelineDebugMixin:
    def _format_candidate_short(self, c):
        if not c:
            return "None"
        return (
            f"{c.get('profile_id')}[tot={c.get('total', -1):.3f},"
            f"face={c.get('face', -1):.3f},app={c.get('app', 0):.3f},"
            f"m={c.get('margin', -1):.3f},risk={c.get('temporal_spatial_risk')},"
            f"gap={c.get('gap_frames')}]"
        )

    def _print_candidate_focus(self, event: str, track_id: int, frame_index: int,
                               obs_count: int, face_conf: float, candidates,
                               selected=None, current_profile_id=None, reason=None):
        """
        Log rút gọn để debug vì sao track bị kéo vào P_id.
        Chỉ in top-3 candidate + selected/reason, không in toàn bộ Compare.
        """
        top = list(candidates or [])[:3]
        top_text = " | ".join(self._format_candidate_short(c) for c in top) if top else "none"
        print(
            f"[IDDBG_{event}] frame={frame_index} track={track_id} obs={obs_count} "
            f"current={current_profile_id} face_conf={face_conf:.2f} "
            f"selected={self._format_candidate_short(selected)} reason={reason} "
            f"top3={top_text}"
        )

    def _is_suspicious_candidate(self, c) -> bool:
        if not c:
            return False
        # Những case cần xem kỹ: margin mỏng, app/quần áo thấp, risk không gian-thời gian,
        # hoặc face cao nhưng app thấp => mắt thường thấy khác tóc/quần áo nhưng face kéo vào.
        return (
            c.get('margin', 1.0) < 0.04
            or c.get('app', 1.0) < 0.70
            or c.get('temporal_spatial_risk') is not None
            or (c.get('face', 0.0) >= 0.92 and c.get('app', 1.0) < 0.75)
        )

    def _print_multi_profile_if_needed(self, frame_index: int, active_track_ids, track_to_profile):
        groups = {}
        for tid in sorted(int(t) for t in active_track_ids):
            pid = track_to_profile.get(tid)
            if pid:
                groups.setdefault(pid, []).append(tid)
        for pid, tids in groups.items():
            if len(tids) > 1:
                print(f"[IDDBG_MULTI_ACTIVE_PROFILE] frame={frame_index} profile={pid} active_tracks={tids}")

    def _dominant_color_name_from_hsv(self, hue: float, sat: float, val: float) -> str:
        """
        Nhãn màu rất thô cho log debug, không dùng để quyết định identity.
        hue: OpenCV HSV 0..180, sat/val: 0..255.
        """
        if val < 45:
            return "black/dark"
        if sat < 35:
            if val > 190:
                return "white/light"
            return "gray/low_sat"

        h = hue % 180.0
        if h < 10 or h >= 170:
            return "red"
        if h < 22:
            return "orange"
        if h < 35:
            return "yellow"
        if h < 85:
            return "green"
        if h < 100:
            return "cyan"
        if h < 128:
            return "blue"
        if h < 155:
            return "purple"
        return "pink/red"

    def _track_body_color_summary(self, track_id: int, track_body_reid_samples: Dict[int, List[Dict]]) -> str:
        samples = track_body_reid_samples.get(int(track_id), []) or []
        sigs = [s.get("signature") for s in samples if s.get("signature")]
        if not sigs:
            return "body_samples=0,color=unknown"

        hsv_values = []
        lab_values = []
        dominant_hues = []
        sat_fracs = []
        for sig in sigs:
            hsv = sig.get("torso_hsv_mean") or []
            lab = sig.get("torso_lab_mean") or []
            if len(hsv) == 3:
                hsv_values.append(hsv)
            if len(lab) == 3:
                lab_values.append(lab)
            dh = float(sig.get("dominant_hue", -1.0) or -1.0)
            if dh >= 0:
                dominant_hues.append(dh)
            sat_fracs.append(float(sig.get("saturated_fraction", 0.0) or 0.0))

        if not hsv_values:
            return f"body_samples={len(sigs)},color=unknown"

        hsv_mean = np.mean(np.array(hsv_values, dtype=np.float32), axis=0)
        lab_mean = np.mean(np.array(lab_values, dtype=np.float32), axis=0) if lab_values else np.array([0, 0, 0], dtype=np.float32)
        hue = float(np.mean(dominant_hues)) if dominant_hues else float(hsv_mean[0])
        sat = float(hsv_mean[1])
        val = float(hsv_mean[2])
        color_name = self._dominant_color_name_from_hsv(hue, sat, val)
        sat_frac = float(np.mean(sat_fracs)) if sat_fracs else 0.0
        return (
            f"body_samples={len(sigs)},color={color_name},"
            f"hsv=({hue:.1f},{sat:.0f},{val:.0f}),"
            f"lab=({float(lab_mean[0]):.0f},{float(lab_mean[1]):.0f},{float(lab_mean[2]):.0f}),"
            f"sat_frac={sat_frac:.2f}"
        )

    def _print_profile_pull_debug_summary(
        self,
        track_to_profile: Dict[int, str],
        track_observation_counts: Dict[int, int],
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
        track_body_reid_samples: Dict[int, List[Dict]],
    ) -> None:
        """
        Tổng hợp cuối run: mỗi P_id đang kéo những track nào, màu/body từng track,
        và track nào là outlier so với phần còn lại của cùng P_id.
        Log này chỉ để đọc nguyên nhân, không tham gia quyết định matching.
        """
        if not track_to_profile:
            return

        profile_to_tracks: Dict[str, List[int]] = {}
        for tid, pid in track_to_profile.items():
            if pid:
                profile_to_tracks.setdefault(pid, []).append(int(tid))

        print("\n========== IDDBG PROFILE PULL / COLOR SUMMARY ==========")
        for profile_id, tracks in sorted(profile_to_tracks.items()):
            tracks = sorted(set(int(t) for t in tracks))
            if len(tracks) <= 1:
                continue

            print(f"[IDDBG_PROFILE_PULL] profile={profile_id} tracks={tracks} track_count={len(tracks)}")

            for tid in tracks:
                span = self._track_span(track_frame_bboxes, tid)
                span_text = f"{span[0]}->{span[1]}" if span else "unknown"
                obs = int(track_observation_counts.get(tid, 0))
                color_text = self._track_body_color_summary(tid, track_body_reid_samples)

                peer_samples = []
                peer_tracks = []
                for other_tid in tracks:
                    if int(other_tid) == int(tid):
                        continue
                    samples = track_body_reid_samples.get(int(other_tid), []) or []
                    if samples:
                        peer_samples.extend(samples)
                        peer_tracks.append(int(other_tid))

                current_samples = track_body_reid_samples.get(int(tid), []) or []
                if current_samples and peer_samples:
                    body_info = self.person_reid_service.compare_tracklets(peer_samples, current_samples)
                    avg_top = float(body_info.get("avg_top", 0.0))
                    best = float(body_info.get("best", 0.0))
                    color_avg = float(body_info.get("color_avg_top", 0.0))
                    color_best = float(body_info.get("color_best", 0.0))
                    flag = ""
                    if avg_top <= 0.52 or best <= 0.64 or color_avg <= 0.48 or color_best <= 0.62:
                        flag = " <<< POSSIBLE_VISUAL_OUTLIER"
                    print(
                        f"  - track={tid} obs={obs} span={span_text} {color_text} | "
                        f"vs_peers={peer_tracks} body_avg={avg_top:.3f}, body_best={best:.3f}, "
                        f"color_avg={color_avg:.3f}, color_best={color_best:.3f}{flag}"
                    )
                else:
                    print(
                        f"  - track={tid} obs={obs} span={span_text} {color_text} | "
                        f"vs_peers=not_enough_body_samples"
                    )
        print("========================================================\n")

    def _delayed_debug_display_identity(
        self,
        record: Dict,
        final_profile_id: str,
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
        delayed_display_min_frames: int,
        delayed_display_min_obs: int,
    ) -> tuple[str, str]:
        """
        Chỉ điều khiển phần HIỂN THỊ/DEBUG cho true delayed realtime.

        Identity core vẫn xử lý event-based. Camera/debug chỉ publish P_id sau khi
        track đã có đủ tuổi/obs, để người xem thấy rõ quá trình:
        TRACK_ONLY/TEMP -> COMMIT P_id.
        """
        track_id = int(record.get("track_id"))
        frame_index = int(record.get("frame_index", 0) or 0)
        obs = int(record.get("observation_count", 0) or 0)

        if not final_profile_id or final_profile_id == "PENDING":
            return f"TEMP_{track_id}", "TRACK_ONLY / PENDING"

        boxes = track_frame_bboxes.get(track_id) or {}
        first_frame = min((int(f) for f in boxes.keys()), default=frame_index)
        age_frames = max(0, frame_index - first_frame + 1)

        if obs < int(delayed_display_min_obs) or age_frames < int(delayed_display_min_frames):
            return (
                f"TEMP_{track_id}",
                f"COLLECTING -> candidate {final_profile_id} "
                f"({obs}/{delayed_display_min_obs} obs, {age_frames}/{delayed_display_min_frames}f)",
            )

        return final_profile_id, f"COMMITTED {final_profile_id}"

    def _collapse_duplicate_debug_records(
        self,
        frame_records: List[Dict],
        track_to_profile: Dict[int, str],
        duplicate_iou_threshold: float = 0.55,
        containment_threshold: float = 0.70,
        center_distance_norm_threshold: float = 0.12,
        area_ratio_min: float = 0.40,
        area_ratio_max: float = 2.80,
    ) -> List[Dict]:
        """
        Chỉ dùng khi dựng debug video.

        Nếu cùng frame có 2 bbox gần như trùng nhau, trong đó một bbox đã có
        personid còn bbox còn lại pending, giữ bbox đã có personid. Như vậy
        video debug không còn hiện cùng một người thành 2 trạng thái.
        """
        if len(frame_records) <= 1:
            return frame_records

        kept = []
        removed = set()

        def profile_of(record):
            return track_to_profile.get(record.get("track_id"), "PENDING")

        ordered = sorted(
            enumerate(frame_records),
            key=lambda item: 0 if profile_of(item[1]) != "PENDING" else 1,
        )

        for idx, record in ordered:
            if idx in removed:
                continue

            record_profile = profile_of(record)

            for other_idx, other in ordered:
                if other_idx == idx or other_idx in removed:
                    continue

                other_profile = profile_of(other)
                if record_profile == "PENDING" and other_profile == "PENDING":
                    continue

                iou = self._bbox_iou(record.get("bbox"), other.get("bbox"))
                if iou < duplicate_iou_threshold:
                    continue

                ratio = self._bbox_area_ratio(record.get("bbox"), other.get("bbox"))
                if ratio < area_ratio_min or ratio > area_ratio_max:
                    continue

                if record_profile != "PENDING" and other_profile == "PENDING":
                    removed.add(other_idx)
                elif record_profile == "PENDING" and other_profile != "PENDING":
                    removed.add(idx)
                    break

            if idx not in removed:
                kept.append(record)

        return kept

