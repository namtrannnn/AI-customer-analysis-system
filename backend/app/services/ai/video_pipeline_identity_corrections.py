from typing import Dict, List, Optional

import cv2
import numpy as np


class VideoPipelineIdentityCorrectionMixin:
    def _split_same_frame_active_profile_conflicts(
        self,
        frame_index: int,
        active_track_ids,
        active_track_bboxes: Dict[int, List[float]],
        track_to_profile: Dict[int, str],
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
        track_debug_status: Dict[int, str],
        profile_owner_track: Optional[Dict[str, int]] = None,
        duplicate_iou_threshold: float = 0.45,
        duplicate_center_norm_threshold: float = 0.18,
    ) -> int:
        """
        Camera-safe invariant hẹp: một P_id không được xuất hiện trên 2 bbox khác nhau
        trong cùng frame. Chỉ tách khi hai bbox thật sự là hai người khác nhau; nếu là
        duplicate track cùng một người thì giữ nguyên.

        Đây là guard realtime duy nhất được thêm lại vào nền v4.2.9/v4.2.18, không kéo
        theo các guard face-ready/entry-reuse đã làm vỡ video 1.
        """
        groups: Dict[str, List[int]] = {}
        for tid in sorted(int(t) for t in active_track_ids):
            pid = track_to_profile.get(int(tid))
            if pid:
                groups.setdefault(pid, []).append(int(tid))

        split_count = 0
        for profile_id, tids in list(groups.items()):
            tids = sorted(set(int(t) for t in tids))
            if len(tids) <= 1:
                continue

            conflict_pairs = []
            for i, a in enumerate(tids):
                box_a = active_track_bboxes.get(int(a))
                if box_a is None:
                    continue
                for b in tids[i + 1:]:
                    box_b = active_track_bboxes.get(int(b))
                    if box_b is None:
                        continue
                    iou = self._bbox_iou(box_a, box_b)
                    containment = self._bbox_containment(box_a, box_b)
                    center_norm = self._bbox_center_distance_norm(box_a, box_b)
                    area_ratio = self._bbox_area_ratio(box_a, box_b)

                    duplicate_like = (
                        iou >= duplicate_iou_threshold
                        or containment >= 0.60
                        or (
                            center_norm <= duplicate_center_norm_threshold
                            and 0.35 <= area_ratio <= 3.20
                            and containment >= 0.12
                        )
                    )
                    if not duplicate_like:
                        conflict_pairs.append((int(a), int(b), iou, containment, center_norm, area_ratio))

            if not conflict_pairs:
                continue

            def first_seen(tid: int) -> int:
                boxes = track_frame_bboxes.get(int(tid)) or {}
                return min((int(f) for f in boxes.keys()), default=int(frame_index))

            # Ưu tiên giữ track đã tạo profile gốc. Nếu không biết owner thì giữ track xuất hiện sớm hơn.
            owner_tid = None
            if profile_owner_track is not None:
                cand_owner = profile_owner_track.get(profile_id)
                if cand_owner in tids:
                    owner_tid = int(cand_owner)
            keep_tid = owner_tid if owner_tid is not None else min(tids, key=lambda t: (first_seen(int(t)), int(t)))

            # Chỉ tách một track mỗi frame để tránh cascade gây nhiễu.
            split_candidates = [t for t in tids if int(t) != int(keep_tid)]
            split_candidates.sort(key=lambda t: (first_seen(int(t)), int(t)), reverse=True)
            for tid in split_candidates:
                tid = int(tid)
                new_pid = self.online_identity.split_track_to_new_profile(
                    track_id=tid,
                    source_profile_id=profile_id,
                )
                if not new_pid:
                    continue
                track_to_profile[tid] = new_pid
                self.online_identity.track_to_profile[tid] = new_pid
                if profile_owner_track is not None:
                    profile_owner_track[new_pid] = tid
                track_debug_status[tid] = f"SAME_FRAME_ACTIVE_SPLIT: Track {tid} {profile_id} -> {new_pid}"
                a, b, iou, containment, center_norm, area_ratio = conflict_pairs[0]
                print(
                    f"[IDDBG_SAME_FRAME_ACTIVE_SPLIT] frame={frame_index} track={tid} "
                    f"{profile_id}->{new_pid}, keep_track={keep_tid}, active_tracks={tids}, "
                    f"conflict_pair=({a},{b}), iou={iou:.3f}, containment={containment:.3f}, "
                    f"center_norm={center_norm:.3f}, area_ratio={area_ratio:.3f}"
                )
                split_count += 1
                break

        return split_count

    def _split_early_head_episode_profiles(
        self,
        track_to_profile: Dict[int, str],
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
        track_observation_counts: Dict[int, int],
        track_debug_status: Dict[int, str],
        stale_gap_frames: int,
        min_profile_tracks: int = 3,
        max_head_tracks: int = 2,
        min_head_total_obs: int = 60,
        min_tail_tracks: int = 2,
        min_tail_total_obs: int = 120,
        min_each_tail_obs: int = 40,
    ) -> bool:
        """
        Final-only generic head split.

        Mục tiêu chính: xử lý profile dạng [early_anchor, tail_1, tail_2, ...]
        khi early_anchor xuất hiện rất sớm, rời frame lâu, sau đó một cụm tail ổn định
        bị kéo chung profile. Ví dụ tổng quát của case P_0008=[1,31,59,63].

        Đây là rule split-only:
        - không hard-code track_id/P_id;
        - không merge vào profile cũ;
        - không chạy realtime nên không tạo vòng lặp split/refine;
        - chỉ tách khi tail có ít nhất nhiều track ổn định và gap thời gian lớn.
        """
        if not track_to_profile:
            return False

        profile_to_tracks: Dict[str, List[int]] = {}
        for tid, pid in list(track_to_profile.items()):
            if pid is not None:
                profile_to_tracks.setdefault(pid, []).append(int(tid))

        changed = False

        for profile_id, raw_tracks in sorted(profile_to_tracks.items()):
            tracks = []
            for tid in sorted(set(int(t) for t in raw_tracks)):
                span = self._track_span(track_frame_bboxes, tid)
                if span is None:
                    continue
                obs = int(track_observation_counts.get(tid, 0))
                tracks.append({
                    "track_id": tid,
                    "start": int(span[0]),
                    "end": int(span[1]),
                    "obs": obs,
                })

            if len(tracks) < int(min_profile_tracks):
                continue

            tracks.sort(key=lambda x: (x["start"], x["end"], x["track_id"]))

            best_split_idx = None
            best_gap = -1
            for i in range(len(tracks) - 1):
                left_end = max(t["end"] for t in tracks[: i + 1])
                right_start = min(t["start"] for t in tracks[i + 1 :])
                gap = int(right_start - left_end)
                if gap > best_gap:
                    best_gap = gap
                    best_split_idx = i

            if best_split_idx is None or best_gap < int(stale_gap_frames):
                continue

            head = tracks[: best_split_idx + 1]
            tail = tracks[best_split_idx + 1 :]

            # Chỉ tách cụm đầu nhỏ khỏi cụm sau ổn định.
            # Nếu cả hai phía đều lớn, đây có thể là hai episode phức tạp hơn;
            # không xử lý ở rule hẹp này để tránh phá video khác.
            if len(head) > int(max_head_tracks):
                continue
            if len(tail) < int(min_tail_tracks):
                continue

            head_total_obs = sum(int(t["obs"]) for t in head)
            tail_total_obs = sum(int(t["obs"]) for t in tail)

            if head_total_obs < int(min_head_total_obs):
                continue
            if tail_total_obs < int(min_tail_total_obs):
                continue
            if any(int(t["obs"]) < int(min_each_tail_obs) for t in tail):
                continue

            # Cụm đầu phải thật sự kết thúc trước cụm sau.
            # Không split nếu có overlap đáng kể giữa head và tail.
            head_end = max(int(t["end"]) for t in head)
            tail_start = min(int(t["start"]) for t in tail)
            if tail_start - head_end < int(stale_gap_frames):
                continue

            head_track_ids = [int(t["track_id"]) for t in head]
            tail_track_ids = [int(t["track_id"]) for t in tail]

            # Split track đầu tiên để tạo profile mới, rồi chuyển các head track còn lại vào đó.
            first_tid = head_track_ids[0]
            new_pid = self.online_identity.split_track_to_new_profile(
                track_id=first_tid,
                source_profile_id=profile_id,
            )
            if not new_pid:
                continue

            track_to_profile[first_tid] = new_pid
            self.online_identity.track_to_profile[int(first_tid)] = new_pid

            for tid in head_track_ids[1:]:
                ok = self.online_identity.reassign_track_to_profile(
                    track_id=int(tid),
                    source_profile_id=profile_id,
                    target_profile_id=new_pid,
                )
                if ok:
                    track_to_profile[int(tid)] = new_pid
                    self.online_identity.track_to_profile[int(tid)] = new_pid

            for tid in head_track_ids:
                old_status = track_debug_status.get(int(tid), "")
                track_debug_status[int(tid)] = (
                    f"FINAL_HEAD_SPLIT: Track {tid} {profile_id} -> {new_pid}, "
                    f"gap_frames={best_gap}, head_tracks={head_track_ids}, "
                    f"tail_tracks={tail_track_ids}; prev_status={old_status}"
                )

            print(
                f"[IDDBG_FINAL_HEAD_SPLIT] {profile_id} -> {new_pid} | "
                f"moved_head_tracks={head_track_ids} | kept_tail_tracks={tail_track_ids} | "
                f"head_total_obs={head_total_obs} | tail_total_obs={tail_total_obs} | "
                f"gap_frames={best_gap}"
            )
            changed = True

        return changed

    def _move_tracks_to_new_final_profile(
        self,
        *,
        track_ids: List[int],
        source_profile_id: str,
        track_to_profile: Dict[int, str],
        track_debug_status: Dict[int, str],
        reason: str,
    ) -> Optional[str]:
        """
        Final cleanup helper: chỉ tách một nhóm track ra profile mới.
        Không merge vào profile có sẵn để tránh phá các cụm đã đúng.
        """
        clean_track_ids = [int(t) for t in track_ids if int(t) in track_to_profile]
        clean_track_ids = [t for t in clean_track_ids if track_to_profile.get(t) == source_profile_id]
        if not clean_track_ids:
            return None

        first_tid = int(clean_track_ids[0])
        new_pid = self.online_identity.split_track_to_new_profile(
            track_id=first_tid,
            source_profile_id=source_profile_id,
        )
        if not new_pid:
            return None

        track_to_profile[first_tid] = new_pid
        self.online_identity.track_to_profile[first_tid] = new_pid

        for tid in clean_track_ids[1:]:
            ok = self.online_identity.reassign_track_to_profile(
                track_id=int(tid),
                source_profile_id=source_profile_id,
                target_profile_id=new_pid,
            )
            if ok:
                track_to_profile[int(tid)] = new_pid
                self.online_identity.track_to_profile[int(tid)] = new_pid

        for tid in clean_track_ids:
            old_status = track_debug_status.get(int(tid), "")
            track_debug_status[int(tid)] = (
                f"{reason}: Track {tid} {source_profile_id} -> {new_pid}; "
                f"group={clean_track_ids}; prev_status={old_status}"
            )
        return new_pid

    def _split_late_tail_group_profiles(
        self,
        *,
        track_to_profile: Dict[int, str],
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
        track_observation_counts: Dict[int, int],
        track_debug_status: Dict[int, str],
        gap_frames: int,
        min_profile_tracks: int,
        max_head_tracks: int,
        min_head_total_obs: int,
        min_tail_tracks: int,
        min_tail_total_obs: int,
        min_each_tail_obs: int,
    ) -> bool:
        """
        Tách cụm tail xuất hiện muộn ra profile mới khi profile có dạng:
        head nhỏ/ổn định -> gap -> tail nhiều track ổn định.
        Dùng cho lỗi generic kiểu một nhóm khách muộn bị dính vào P_id đã có.
        """
        profile_to_tracks: Dict[str, List[int]] = {}
        for tid, pid in list(track_to_profile.items()):
            if pid is not None:
                profile_to_tracks.setdefault(pid, []).append(int(tid))

        changed = False
        for profile_id, raw_tracks in sorted(profile_to_tracks.items()):
            tracks = []
            for tid in sorted(set(int(t) for t in raw_tracks)):
                span = self._track_span(track_frame_bboxes, tid)
                if span is None:
                    continue
                tracks.append({
                    "track_id": tid,
                    "start": int(span[0]),
                    "end": int(span[1]),
                    "obs": int(track_observation_counts.get(tid, 0)),
                })

            if len(tracks) < int(min_profile_tracks):
                continue
            tracks.sort(key=lambda x: (x["start"], x["end"], x["track_id"]))

            best = None
            for i in range(len(tracks) - 1):
                head = tracks[: i + 1]
                tail = tracks[i + 1 :]
                # v4.2.9 tail-group split logic, with one generic tolerance:
                # ignore very short head bridge fragments when counting head tracks.
                # This restores the old behavior for profiles like:
                #   stable head [long, tiny_fragment, short_head] -> late tail group
                # without hardcoding P_id/track_id.
                tiny_head_tracks = [t for t in head if int(t.get("obs", 0)) <= 15]
                effective_head_tracks = [t for t in head if int(t.get("obs", 0)) > 15]
                if len(effective_head_tracks) > int(max_head_tracks):
                    continue
                if len(tiny_head_tracks) > 2:
                    continue
                if len(tail) < int(min_tail_tracks):
                    continue
                head_end = max(int(t["end"]) for t in head)
                tail_start = min(int(t["start"]) for t in tail)
                gap = int(tail_start - head_end)
                if gap < int(gap_frames):
                    continue
                head_obs = sum(int(t["obs"]) for t in head)
                tail_obs = sum(int(t["obs"]) for t in tail)
                if head_obs < int(min_head_total_obs) or tail_obs < int(min_tail_total_obs):
                    continue
                if any(int(t["obs"]) < int(min_each_tail_obs) for t in tail):
                    continue
                if best is None or gap > best["gap"]:
                    best = {"head": head, "tail": tail, "gap": gap, "head_obs": head_obs, "tail_obs": tail_obs}

            if not best:
                continue

            tail_ids = [int(t["track_id"]) for t in best["tail"]]
            new_pid = self._move_tracks_to_new_final_profile(
                track_ids=tail_ids,
                source_profile_id=profile_id,
                track_to_profile=track_to_profile,
                track_debug_status=track_debug_status,
                reason="FINAL_TAIL_GROUP_SPLIT",
            )
            if not new_pid:
                continue
            tiny_head_ids = [int(t["track_id"]) for t in best["head"] if int(t.get("obs", 0)) <= 15]
            print(
                f"[IDDBG_FINAL_TAIL_GROUP_SPLIT] {profile_id} -> {new_pid} | "
                f"moved_tail_tracks={tail_ids} | kept_head_tracks={[int(t['track_id']) for t in best['head']]} | "
                f"tiny_head_ignored_for_count={tiny_head_ids} | "
                f"head_total_obs={best['head_obs']} | tail_total_obs={best['tail_obs']} | gap_frames={best['gap']}"
            )
            changed = True
        return changed

    def _split_late_tracks_from_early_singleton_profiles(
        self,
        *,
        track_to_profile: Dict[int, str],
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
        track_observation_counts: Dict[int, int],
        track_debug_status: Dict[int, str],
        gap_frames: int,
        max_head_obs: int,
        min_tail_total_obs: int,
        min_long_tail_obs: int,
    ) -> bool:
        """
        Nếu profile bắt đầu bằng một track rất ngắn/sớm, sau đó có track muộn dài,
        giữ profile gốc cho early singleton và tách phần muộn ra P mới.
        Rule này giúp tránh profile đầu video bị bẩn bởi người xuất hiện về sau.
        """
        profile_to_tracks: Dict[str, List[int]] = {}
        for tid, pid in list(track_to_profile.items()):
            if pid is not None:
                profile_to_tracks.setdefault(pid, []).append(int(tid))

        changed = False
        for profile_id, raw_tracks in sorted(profile_to_tracks.items()):
            tracks = []
            for tid in sorted(set(int(t) for t in raw_tracks)):
                span = self._track_span(track_frame_bboxes, tid)
                if span is None:
                    continue
                tracks.append({
                    "track_id": tid,
                    "start": int(span[0]),
                    "end": int(span[1]),
                    "obs": int(track_observation_counts.get(tid, 0)),
                })
            if len(tracks) < 2:
                continue
            tracks.sort(key=lambda x: (x["start"], x["end"], x["track_id"]))
            head = tracks[0]
            tail = tracks[1:]
            if int(head["obs"]) > int(max_head_obs):
                continue
            gap = min(int(t["start"]) for t in tail) - int(head["end"])
            if gap < int(gap_frames):
                continue
            tail_total = sum(int(t["obs"]) for t in tail)
            if tail_total < int(min_tail_total_obs):
                continue
            if max(int(t["obs"]) for t in tail) < int(min_long_tail_obs):
                continue

            tail_ids = [int(t["track_id"]) for t in tail]
            new_pid = self._move_tracks_to_new_final_profile(
                track_ids=tail_ids,
                source_profile_id=profile_id,
                track_to_profile=track_to_profile,
                track_debug_status=track_debug_status,
                reason="FINAL_EARLY_SINGLETON_LATE_SPLIT",
            )
            if not new_pid:
                continue
            print(
                f"[IDDBG_FINAL_EARLY_SINGLETON_LATE_SPLIT] {profile_id} -> {new_pid} | "
                f"kept_head_track={int(head['track_id'])} | moved_late_tracks={tail_ids} | "
                f"head_obs={int(head['obs'])} | tail_total_obs={tail_total} | gap_frames={gap}"
            )
            changed = True
        return changed

    def _split_middle_singleton_bridge_tracks(
        self,
        *,
        track_to_profile: Dict[int, str],
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
        track_observation_counts: Dict[int, int],
        track_debug_status: Dict[int, str],
        max_middle_obs: int,
        min_edge_obs: int,
        min_head_gap_frames: int,
        max_tail_gap_frames: int,
    ) -> bool:
        """
        Tách track ngắn nằm giữa hai track dài trong cùng profile.
        Đây là split-only guard cho case một người thứ ba đi ngang giữa hai lần xuất hiện.
        """
        profile_to_tracks: Dict[str, List[int]] = {}
        for tid, pid in list(track_to_profile.items()):
            if pid is not None:
                profile_to_tracks.setdefault(pid, []).append(int(tid))

        changed = False
        for profile_id, raw_tracks in sorted(profile_to_tracks.items()):
            tracks = []
            for tid in sorted(set(int(t) for t in raw_tracks)):
                span = self._track_span(track_frame_bboxes, tid)
                if span is None:
                    continue
                tracks.append({
                    "track_id": tid,
                    "start": int(span[0]),
                    "end": int(span[1]),
                    "obs": int(track_observation_counts.get(tid, 0)),
                })
            if len(tracks) != 3:
                continue
            tracks.sort(key=lambda x: (x["start"], x["end"], x["track_id"]))
            first, middle, last = tracks
            if int(first["obs"]) < int(min_edge_obs) or int(last["obs"]) < int(min_edge_obs):
                continue
            if int(middle["obs"]) > int(max_middle_obs):
                continue
            head_gap = int(middle["start"]) - int(first["end"])
            tail_gap = int(last["start"]) - int(middle["end"])
            if head_gap < int(min_head_gap_frames):
                continue
            if tail_gap < 0 or tail_gap > int(max_tail_gap_frames):
                continue

            middle_id = int(middle["track_id"])
            new_pid = self._move_tracks_to_new_final_profile(
                track_ids=[middle_id],
                source_profile_id=profile_id,
                track_to_profile=track_to_profile,
                track_debug_status=track_debug_status,
                reason="FINAL_MIDDLE_SINGLETON_SPLIT",
            )
            if not new_pid:
                continue
            print(
                f"[IDDBG_FINAL_MIDDLE_SINGLETON_SPLIT] {profile_id} -> {new_pid} | "
                f"moved_middle_track={middle_id} | kept_edge_tracks={[int(first['track_id']), int(last['track_id'])]} | "
                f"middle_obs={int(middle['obs'])} | head_gap={head_gap} | tail_gap={tail_gap}"
            )
            changed = True
        return changed

    def _final_split_sequential_tail_pair_to_new_profile(
        self,
        track_to_profile: Dict[int, str],
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
        track_observation_counts: Dict[int, int],
        track_body_reid_samples: Dict[int, List[Dict]],
        track_best_identity_sample: Dict[int, Dict],
        track_debug_status: Dict[int, str],
        max_pair_gap_frames: int,
        min_source_gap_frames: int = 40,
        min_track_obs: int = 45,
        max_center_norm: float = 1.60,
        min_body_avg: float = 0.70,
        min_body_best: float = 0.76,
        min_score: float = 0.70,
    ) -> bool:
        """
        Final-only correction trên nền v4.2.3:
        tách 2 tail tracks liên tiếp đang bị dính vào 2 profile cũ khác nhau
        ra một P_id mới riêng.

        Mục tiêu generic cho case kiểu:
            P_old_A = [old_track, tail_A]
            P_old_B = [old_track, tail_B]
            tail_A kết thúc rồi tail_B xuất hiện ngay sau đó,
            tail_A/tail_B giống nhau hơn theo body/không gian/thời gian.

        Không chạy online, không thay đổi delayed realtime gate. Chỉ sửa mapping cuối
        để giữ logic/cách xử lý của v4.2.3 nhưng loại bỏ cụm bẩn kiểu track30/33.
        """
        if not track_to_profile or not track_frame_bboxes:
            return False

        profile_to_tracks: Dict[str, List[int]] = {}
        for tid, pid in list(track_to_profile.items()):
            if pid:
                profile_to_tracks.setdefault(pid, []).append(int(tid))

        def face_score(a: int, b: int) -> float:
            sa = track_best_identity_sample.get(int(a)) or {}
            sb = track_best_identity_sample.get(int(b)) or {}
            ea = sa.get("embedding")
            eb = sb.get("embedding")
            if ea is None or eb is None:
                return 0.0
            va = self._normalize_vector(np.array(ea, dtype=np.float32))
            vb = self._normalize_vector(np.array(eb, dtype=np.float32))
            if va is None or vb is None:
                return 0.0
            return float(np.dot(va, vb))

        def late_tail_candidate(tid: int, pid: str):
            if int(track_observation_counts.get(int(tid), 0)) < int(min_track_obs):
                return None
            span = self._track_span(track_frame_bboxes, int(tid))
            if span is None:
                return None
            start, end = int(span[0]), int(span[1])
            peers = [int(t) for t in profile_to_tracks.get(pid, []) if int(t) != int(tid)]
            # Singleton successor is allowed: this is exactly the case after
            # _rescue_stable_pending_tracks creates an own P for track33.
            if not peers:
                return {
                    "track": int(tid),
                    "pid": pid,
                    "start": start,
                    "end": end,
                    "source_gap": 10**9,
                    "obs": int(track_observation_counts.get(int(tid), 0)),
                    "singleton": True,
                }

            earlier_gaps = []
            for other in peers:
                other_span = self._track_span(track_frame_bboxes, int(other))
                if other_span is None:
                    continue
                o_start, o_end = int(other_span[0]), int(other_span[1])
                # Nếu có peer bắt đầu sau candidate thì candidate không phải tail sạch.
                if o_start > start:
                    return None
                # Nếu có overlap rõ với peer thì không phải episode kế tiếp.
                if not (o_end < start or end < o_start):
                    return None
                if o_end < start:
                    earlier_gaps.append(start - o_end)

            if not earlier_gaps:
                return None
            source_gap = min(earlier_gaps)
            if source_gap < int(min_source_gap_frames):
                return None
            return {
                "track": int(tid),
                "pid": pid,
                "start": start,
                "end": end,
                "source_gap": int(source_gap),
                "obs": int(track_observation_counts.get(int(tid), 0)),
                "singleton": False,
            }

        candidates = []
        for pid, tids in sorted(profile_to_tracks.items()):
            for tid in sorted(set(tids)):
                c = late_tail_candidate(int(tid), pid)
                if c is not None:
                    candidates.append(c)

        # v4.2.14: include stable unassigned/pending tail tracks as clean singleton successors.
        # This handles cases like track33 staying PENDING until it closes: it can still form
        # a final tail pair with a predecessor such as track30, then we create a real P_id for it.
        assigned_tids = {int(t) for t in track_to_profile.keys()}
        for tid, obs in sorted(track_observation_counts.items()):
            tid = int(tid)
            if tid in assigned_tids:
                continue
            if int(obs or 0) < int(min_track_obs):
                continue
            span = self._track_span(track_frame_bboxes, tid)
            if span is None:
                continue
            if not (track_body_reid_samples.get(tid) or []):
                continue
            sample = track_best_identity_sample.get(tid) or {}
            if sample.get("embedding") is None:
                continue
            if float(sample.get("face_confidence", -1.0) or -1.0) < 0.72:
                continue
            start, end = int(span[0]), int(span[1])
            candidates.append({
                "track": tid,
                "pid": f"__PENDING_TAIL_{tid}",
                "start": start,
                "end": end,
                "source_gap": 10**9,
                "obs": int(obs or 0),
                "singleton": True,
                "pending_tail": True,
            })

        if len(candidates) < 2:
            return False

        best = None
        for a in candidates:
            for b in candidates:
                if a["track"] == b["track"] or a["pid"] == b["pid"]:
                    continue
                if bool(a.get("singleton")) and bool(b.get("singleton")):
                    continue
                first, second = (a, b) if a["end"] <= b["start"] else (b, a)
                # Only split a polluted predecessor into a clean successor profile.
                # Do not move a clean singleton predecessor into a polluted later profile.
                if bool(first.get("singleton")) and not bool(second.get("singleton")):
                    continue
                gap = int(second["start"] - first["end"])
                if gap < 0 or gap > int(max_pair_gap_frames):
                    continue

                first_bbox = self._track_bbox_at(track_frame_bboxes, int(first["track"]), int(first["end"]))
                second_bbox = self._track_bbox_at(track_frame_bboxes, int(second["track"]), int(second["start"]))
                if first_bbox is None or second_bbox is None:
                    continue
                center_norm = self._bbox_center_distance_norm(first_bbox, second_bbox)
                area_ratio = self._bbox_area_ratio(first_bbox, second_bbox)
                if not (0.20 <= area_ratio <= 5.00):
                    continue

                first_samples = track_body_reid_samples.get(int(first["track"]), []) or []
                second_samples = track_body_reid_samples.get(int(second["track"]), []) or []
                if not first_samples or not second_samples:
                    continue
                body_info = self.person_reid_service.compare_tracklets(first_samples, second_samples)
                body_avg = float(body_info.get("avg_top", 0.0))
                body_best = float(body_info.get("best", 0.0))
                color_avg = float(body_info.get("color_avg_top", 0.0))
                color_best = float(body_info.get("color_best", 0.0))
                face = face_score(int(first["track"]), int(second["track"]))

                # Body/color/face là chính cho final tail-pair. Vị trí bbox chỉ là guard mềm,
                # vì predecessor/successor có thể lệch nhẹ khi camera/tracker cắt khác nhau.
                body_ok = (body_avg >= float(min_body_avg) and body_best >= float(min_body_best))
                color_body_ok = (body_avg >= float(min_body_avg) - 0.03 and color_avg >= 0.82 and body_best >= float(min_body_best) - 0.03)
                face_body_ok = (face >= 0.86 and body_avg >= 0.66)
                strong_visual_pair = (
                    (body_avg >= 0.76 and body_best >= 0.80)
                    or (body_avg >= 0.70 and color_avg >= 0.88 and color_best >= 0.90)
                    or (face >= 0.90 and body_avg >= 0.68)
                )
                if center_norm > float(max_center_norm) and not (strong_visual_pair and center_norm <= 2.20):
                    continue
                if not (body_ok or color_body_ok or face_body_ok or strong_visual_pair):
                    continue

                spatial = max(0.0, 1.0 - center_norm / max(float(max_center_norm), 1e-6))
                temporal = max(0.0, 1.0 - gap / max(int(max_pair_gap_frames), 1))
                score = (
                    0.38 * body_avg
                    + 0.18 * body_best
                    + 0.16 * color_avg
                    + 0.10 * color_best
                    + 0.08 * max(face, 0.0)
                    + 0.06 * spatial
                    + 0.04 * temporal
                )
                if score < float(min_score):
                    continue

                item = {
                    "score": float(score),
                    "first": first,
                    "second": second,
                    "gap": gap,
                    "center_norm": center_norm,
                    "area_ratio": area_ratio,
                    "body_avg": body_avg,
                    "body_best": body_best,
                    "color_avg": color_avg,
                    "color_best": color_best,
                    "face": face,
                }
                if best is None or item["score"] > best["score"]:
                    best = item

        if best is None:
            return False

        first = best["first"]
        second = best["second"]
        first_tid = int(first["track"])
        second_tid = int(second["track"])
        first_pid = first["pid"]
        second_pid = second["pid"]

        # If the selected successor is an unassigned pending tail, create a real profile for it now.
        if bool(second.get("pending_tail")):
            second_sample = track_best_identity_sample.get(second_tid) or {}
            if second_sample.get("embedding") is None:
                return False
            second_pid = self.online_identity.create_new_profile(
                track_id=second_tid,
                embedding=second_sample["embedding"],
                face_image_path=second_sample.get("face_image_path"),
                face_confidence=second_sample.get("face_confidence"),
                frame_index=second_sample.get("frame_index", int(second.get("start", 0))),
                observation_count=int(track_observation_counts.get(second_tid, second.get("obs", 0)) or 0),
                observed_frame_indices=sorted(list((track_frame_bboxes.get(second_tid) or {}).keys())),
                appearance_signature=second_sample.get("appearance_signature"),
                bbox=second_sample.get("bbox"),
            )
            track_to_profile[second_tid] = second_pid
            self.online_identity.track_to_profile[second_tid] = second_pid
            second["pid"] = second_pid
            print(
                f"[IDDBG_FINAL_PENDING_TAIL_CREATE_PROFILE] track={second_tid} -> {second_pid}, "
                f"obs={track_observation_counts.get(second_tid, 0)}, pair_predecessor={first_tid}"
            )

        # If successor is a clean singleton, make successor's P_id own the pair.
        # This matches the desired behavior for tail pairs: track30 -> P(track33),
        # not track33 -> old polluted profile and not both into arbitrary stale P.
        if bool(second.get("singleton")):
            new_pid = second_pid
            ok = self.online_identity.reassign_track_to_profile(
                track_id=first_tid,
                source_profile_id=first_pid,
                target_profile_id=new_pid,
            )
            if not ok:
                # Fallback: split first then move second into that new profile.
                new_pid = self.online_identity.split_track_to_new_profile(
                    track_id=first_tid,
                    source_profile_id=first_pid,
                )
                if not new_pid:
                    return False
                track_to_profile[first_tid] = new_pid
                self.online_identity.track_to_profile[first_tid] = new_pid
                ok = self.online_identity.reassign_track_to_profile(
                    track_id=second_tid,
                    source_profile_id=second_pid,
                    target_profile_id=new_pid,
                )
                if not ok:
                    print(
                        f"[IDDBG_FINAL_TAIL_PAIR_REASSIGN_FAILED] first={first_tid} second={second_tid} "
                        f"second_pid={second_pid} target={new_pid}"
                    )
                    return True
                track_to_profile[second_tid] = new_pid
                self.online_identity.track_to_profile[second_tid] = new_pid
            else:
                track_to_profile[first_tid] = new_pid
                self.online_identity.track_to_profile[first_tid] = new_pid
        else:
            new_pid = self.online_identity.split_track_to_new_profile(
                track_id=first_tid,
                source_profile_id=first_pid,
            )
            if not new_pid:
                return False

            track_to_profile[first_tid] = new_pid
            self.online_identity.track_to_profile[first_tid] = new_pid

            ok = self.online_identity.reassign_track_to_profile(
                track_id=second_tid,
                source_profile_id=second_pid,
                target_profile_id=new_pid,
            )
            if not ok:
                # Nếu reassign thất bại, giữ tối thiểu first đã tách riêng; nhưng báo rõ.
                print(
                    f"[IDDBG_FINAL_TAIL_PAIR_REASSIGN_FAILED] first={first_tid} second={second_tid} "
                    f"second_pid={second_pid} target={new_pid}"
                )
                return True

            track_to_profile[second_tid] = new_pid
            self.online_identity.track_to_profile[second_tid] = new_pid

        for tid, old_pid in [(first_tid, first_pid), (second_tid, second_pid)]:
            old_status = track_debug_status.get(int(tid), "")
            track_debug_status[int(tid)] = (
                f"FINAL_SEQUENTIAL_TAIL_PAIR_SPLIT: Track {tid} {old_pid}->{new_pid}; "
                f"pair=[{first_tid},{second_tid}], score={best['score']:.3f}, "
                f"body_avg={best['body_avg']:.3f}, body_best={best['body_best']:.3f}, "
                f"color_avg={best['color_avg']:.3f}, face={best['face']:.3f}, "
                f"gap={best['gap']}, center={best['center_norm']:.3f}; prev_status={old_status}"
            )

        print(
            f"[IDDBG_FINAL_SEQUENTIAL_TAIL_PAIR_SPLIT] new_profile={new_pid} "
            f"tracks=[{first_tid},{second_tid}] from=[{first_pid},{second_pid}] "
            f"score={best['score']:.3f}, body_avg={best['body_avg']:.3f}, "
            f"body_best={best['body_best']:.3f}, color_avg={best['color_avg']:.3f}, "
            f"face={best['face']:.3f}, gap={best['gap']}, center={best['center_norm']:.3f}, second_singleton={bool(second.get('singleton'))}"
        )
        return True

    def _final_merge_recent_predecessor_into_successor_profile(
        self,
        track_to_profile: Dict[int, str],
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
        track_observation_counts: Dict[int, int],
        track_body_reid_samples: Dict[int, List[Dict]],
        track_best_identity_sample: Dict[int, Dict],
        track_debug_status: Dict[int, str],
        max_gap_frames: int,
        min_predecessor_obs: int = 60,
        min_successor_obs: int = 45,
        max_center_norm: float = 0.75,
        min_body_avg: float = 0.74,
        min_body_best: float = 0.80,
        min_color_avg: float = 0.78,
        min_face: float = 0.82,
    ) -> None:
        """
        Final-only correction giữ nguyên logic v4.2.3.

        Dùng cho case một track kế tiếp/successor đã tạo được P_id riêng sạch,
        còn track ngay trước đó bị kéo nhầm vào profile cũ vì body-tracklet gần vị trí cũ.

        Quan trọng:
        - Không chạy online, không đổi delayed realtime gate.
        - Không hard-code track_id/P_id.
        - Chỉ kéo predecessor vào profile successor nếu successor là singleton sạch.
        - Không merge profile lớn vào nhau; chỉ di chuyển đúng 1 track predecessor.
        """
        if not track_to_profile or not track_frame_bboxes:
            return

        profile_to_tracks: Dict[str, List[int]] = {}
        for tid, pid in list(track_to_profile.items()):
            if pid:
                profile_to_tracks.setdefault(pid, []).append(int(tid))

        def face_score(a: int, b: int) -> float:
            sa = track_best_identity_sample.get(int(a)) or {}
            sb = track_best_identity_sample.get(int(b)) or {}
            ea = sa.get("embedding")
            eb = sb.get("embedding")
            if ea is None or eb is None:
                return 0.0
            va = self._normalize_vector(np.array(ea, dtype=np.float32))
            vb = self._normalize_vector(np.array(eb, dtype=np.float32))
            if va is None or vb is None:
                return 0.0
            return float(np.dot(va, vb))

        moved_any = True
        passes = 0
        while moved_any and passes < 2:
            moved_any = False
            passes += 1

            profile_to_tracks = {}
            for tid, pid in list(track_to_profile.items()):
                if pid:
                    profile_to_tracks.setdefault(pid, []).append(int(tid))

            singleton_successors = []
            for pid, tids in sorted(profile_to_tracks.items()):
                unique_tids = sorted(set(int(t) for t in tids))
                if len(unique_tids) != 1:
                    continue
                succ = unique_tids[0]
                if int(track_observation_counts.get(succ, 0)) < int(min_successor_obs):
                    continue
                span = self._track_span(track_frame_bboxes, succ)
                if span is None:
                    continue
                singleton_successors.append((pid, succ, span[0], span[1]))

            for successor_pid, successor_track, successor_start, successor_end in singleton_successors:
                successor_samples = track_body_reid_samples.get(int(successor_track), []) or []
                successor_first_bbox = self._track_bbox_at(track_frame_bboxes, successor_track, successor_start)
                if successor_first_bbox is None:
                    continue

                best_candidate = None
                for prev_track, prev_pid in list(track_to_profile.items()):
                    prev_track = int(prev_track)
                    if prev_track == successor_track or prev_pid == successor_pid:
                        continue
                    if int(track_observation_counts.get(prev_track, 0)) < int(min_predecessor_obs):
                        continue

                    prev_span = self._track_span(track_frame_bboxes, prev_track)
                    if prev_span is None:
                        continue
                    prev_start, prev_end = prev_span
                    gap = int(successor_start - prev_end)
                    if gap < 0 or gap > int(max_gap_frames):
                        continue

                    # Chỉ cho kéo track tail/latest ra khỏi source profile. Điều này tránh phá
                    # một cụm đã đúng ở đầu/giữa profile.
                    source_tracks = [int(t) for t in profile_to_tracks.get(prev_pid, []) if int(t) != prev_track]
                    if not source_tracks:
                        # Nếu predecessor vốn đã singleton, merge 2 singleton vẫn an toàn.
                        pass
                    else:
                        other_later = False
                        for other in source_tracks:
                            other_span = self._track_span(track_frame_bboxes, other)
                            if other_span is None:
                                continue
                            # Nếu source profile có track khác bắt đầu sau predecessor,
                            # predecessor không phải tail sạch => không di chuyển.
                            if int(other_span[0]) > int(prev_start):
                                other_later = True
                                break
                        if other_later:
                            continue

                    prev_last_bbox = self._track_bbox_at(track_frame_bboxes, prev_track, prev_end)
                    if prev_last_bbox is None:
                        continue
                    center_norm = self._bbox_center_distance_norm(prev_last_bbox, successor_first_bbox)
                    if center_norm > float(max_center_norm):
                        continue
                    area_ratio = self._bbox_area_ratio(prev_last_bbox, successor_first_bbox)
                    if not (0.25 <= area_ratio <= 4.50):
                        continue

                    prev_samples = track_body_reid_samples.get(int(prev_track), []) or []
                    body_avg = 0.0
                    body_best = 0.0
                    color_avg = 0.0
                    color_best = 0.0
                    if prev_samples and successor_samples:
                        body_info = self.person_reid_service.compare_tracklets(prev_samples, successor_samples)
                        body_avg = float(body_info.get("avg_top", 0.0))
                        body_best = float(body_info.get("best", 0.0))
                        color_avg = float(body_info.get("color_avg_top", 0.0))
                        color_best = float(body_info.get("color_best", 0.0))

                    face = face_score(prev_track, successor_track)
                    spatial = max(0.0, 1.0 - (center_norm / max(float(max_center_norm), 1e-6)))
                    temporal = max(0.0, 1.0 - (max(gap, 0) / max(int(max_gap_frames), 1)))

                    strong_face_body = bool(face >= float(min_face) and body_avg >= 0.66)
                    strong_body = bool(body_avg >= float(min_body_avg) and body_best >= float(min_body_best))
                    strong_color_body = bool(color_avg >= float(min_color_avg) and body_avg >= (float(min_body_avg) - 0.04))
                    if not (strong_face_body or strong_body or strong_color_body):
                        continue

                    score = (
                        0.34 * max(face, 0.0)
                        + 0.30 * body_avg
                        + 0.12 * body_best
                        + 0.12 * color_avg
                        + 0.08 * spatial
                        + 0.04 * temporal
                    )
                    candidate = {
                        "score": float(score),
                        "prev_track": prev_track,
                        "prev_pid": prev_pid,
                        "successor_track": successor_track,
                        "successor_pid": successor_pid,
                        "gap": gap,
                        "face": face,
                        "body_avg": body_avg,
                        "body_best": body_best,
                        "color_avg": color_avg,
                        "color_best": color_best,
                        "center_norm": center_norm,
                        "area_ratio": area_ratio,
                    }
                    if best_candidate is None or candidate["score"] > best_candidate["score"]:
                        best_candidate = candidate

                if best_candidate is None:
                    continue

                prev_track = int(best_candidate["prev_track"])
                prev_pid = best_candidate["prev_pid"]
                successor_pid = best_candidate["successor_pid"]
                successor_track = int(best_candidate["successor_track"])

                # Move predecessor into successor profile at final mapping level.
                # Không gọi profile refine/relink online, tránh phá logic v4.2.3.
                track_to_profile[prev_track] = successor_pid
                track_debug_status[prev_track] = (
                    f"FINAL_SUCCESSOR_OWNS_PREDECESSOR: Track {prev_track} "
                    f"{prev_pid}->{successor_pid} with successor_track={successor_track}, "
                    f"score={best_candidate['score']:.3f}, face={best_candidate['face']:.3f}, "
                    f"body_avg={best_candidate['body_avg']:.3f}, color_avg={best_candidate['color_avg']:.3f}, "
                    f"gap={best_candidate['gap']}"
                )
                print(
                    f"[IDDBG_FINAL_SUCCESSOR_OWNS_PREDECESSOR] "
                    f"track={prev_track} {prev_pid}->{successor_pid} "
                    f"successor_track={successor_track}, score={best_candidate['score']:.3f}, "
                    f"face={best_candidate['face']:.3f}, body_avg={best_candidate['body_avg']:.3f}, "
                    f"body_best={best_candidate['body_best']:.3f}, color_avg={best_candidate['color_avg']:.3f}, "
                    f"gap={best_candidate['gap']}, center={best_candidate['center_norm']:.3f}"
                )
                moved_any = True
                break

    def _find_duplicate_locked_profile_in_frame(
        self,
        frame_profile_locks: Dict[int, Dict[str, Dict]],
        frame_index: int,
        current_track_id: int,
        current_bbox: List[float],
        duplicate_iou_threshold: float = 0.55,
        containment_threshold: float = 0.70,
        center_distance_norm_threshold: float = 0.12,
        area_ratio_min: float = 0.40,
        area_ratio_max: float = 2.80,
    ) -> Optional[str]:
        """
        Tìm profile đã được gán trong cùng frame có bbox gần như trùng bbox hiện tại.

        Mục tiêu không phải re-id người mới, mà xử lý duplicate tracker/detection:
        cùng một người có 2 track trong cùng frame, một track đã có personid,
        track còn lại pending do face đổi góc.
        """
        frame_locks = frame_profile_locks.get(frame_index, {})
        if not frame_locks:
            return None

        best_profile_id = None
        best_iou = 0.0

        for profile_id, locked in frame_locks.items():
            locked_track_id = locked.get("track_id")
            locked_bbox = locked.get("bbox")

            if locked_track_id == current_track_id or locked_bbox is None:
                continue

            duplicate_like, duplicate_score = self._is_duplicate_like_bbox(
                current_bbox,
                locked_bbox,
                duplicate_iou_threshold=duplicate_iou_threshold,
                containment_threshold=containment_threshold,
                center_distance_norm_threshold=center_distance_norm_threshold,
                area_ratio_min=area_ratio_min,
                area_ratio_max=area_ratio_max,
            )

            if not duplicate_like:
                continue

            if duplicate_score > best_iou:
                best_iou = duplicate_score
                best_profile_id = profile_id

        if best_profile_id is not None:
            print(
                f"[DuplicateTrackBridge] Track {current_track_id} inherits "
                f"profile={best_profile_id} at frame={frame_index}, iou={best_iou:.3f}"
            )

        return best_profile_id

    def _apply_final_track_lineage_corrections(
        self,
        track_to_profile: Dict[int, str],
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
        track_observation_counts: Dict[int, int],
        track_debug_status: Dict[int, str],
        max_gap_frames: int = 150,
    ) -> None:
        """
        Sửa identity switch theo LINEAGE của track, không neo theo vùng.

        Mục tiêu chính: case Track 31/59 đúng P_0008, sau đó tracker đứt và sinh
        Track 63 gần như cùng bbox/tư thế nhưng gallery kéo sang P_0006.

        Hàm này chỉ chuyển RIÊNG track hiện tại về profile của old_track cụ thể khi:
        - old_track kết thúc ngay trước/sát lúc current_track bắt đầu;
        - old_track đủ dài và current_track cũng đủ dài để không phải rác;
        - bbox cuối old_track và bbox đầu current_track có continuity rõ;
        - cả old_track đoạn cuối và current_track đoạn đầu không di chuyển mạnh;
        - target profile không có bbox khác-người cùng frame với current_track.

        Đây không phải final merge: không gộp profile, chỉ reassign track bị switch.
        """
        if not track_to_profile or not track_frame_bboxes:
            return

        assigned_tracks = [int(t) for t in track_to_profile.keys() if t in track_frame_bboxes]
        if len(assigned_tracks) < 2:
            return

        def first_frame(t: int) -> Optional[int]:
            b = track_frame_bboxes.get(t) or {}
            return min((int(f) for f in b.keys()), default=None)

        def last_frame(t: int) -> Optional[int]:
            b = track_frame_bboxes.get(t) or {}
            return max((int(f) for f in b.keys()), default=None)

        def bbox_at(t: int, f: int) -> Optional[List[float]]:
            b = track_frame_bboxes.get(t) or {}
            return b.get(f) or b.get(str(f))

        def window_bboxes(t: int, start: Optional[int] = None, end: Optional[int] = None) -> Dict[int, List[float]]:
            out = {}
            for k, v in (track_frame_bboxes.get(t) or {}).items():
                fi = int(k)
                if start is not None and fi < start:
                    continue
                if end is not None and fi > end:
                    continue
                out[fi] = v
            return out

        def has_target_same_frame_conflict(current_track: int, target_profile: str) -> bool:
            current_boxes = track_frame_bboxes.get(current_track) or {}
            current_frames = set(int(f) for f in current_boxes.keys())
            for other_track, other_profile in track_to_profile.items():
                other_track = int(other_track)
                if other_track == int(current_track) or other_profile != target_profile:
                    continue
                other_boxes = track_frame_bboxes.get(other_track) or {}
                overlap = current_frames.intersection(int(f) for f in other_boxes.keys())
                for f in overlap:
                    cb = current_boxes.get(f) or current_boxes.get(str(f))
                    ob = other_boxes.get(f) or other_boxes.get(str(f))
                    duplicate_like, _ = self._is_duplicate_like_bbox(
                        cb,
                        ob,
                        duplicate_iou_threshold=0.72,
                        containment_threshold=0.84,
                        center_distance_norm_threshold=0.075,
                        area_ratio_min=0.60,
                        area_ratio_max=1.75,
                    )
                    if not duplicate_like:
                        return True
            return False

        for current_track in sorted(assigned_tracks, key=lambda t: first_frame(t) or 10**12):
            current_profile = track_to_profile.get(current_track)
            current_start = first_frame(current_track)
            current_end = last_frame(current_track)
            if current_profile is None or current_start is None or current_end is None:
                continue

            current_obs = int(track_observation_counts.get(current_track, 0) or len(track_frame_bboxes.get(current_track, {})))
            if current_obs < 20:
                continue

            current_first_bbox = bbox_at(current_track, current_start)
            if current_first_bbox is None:
                continue

            # Nếu đầu track mới đã di chuyển mạnh thì nhiều khả năng là người đi ngang, không lineage-correct.
            current_initial_motion = self._track_motion_norm(
                window_bboxes(current_track, current_start, min(current_start + 20, current_end)),
                max_points=12,
            )
            if current_initial_motion > 0.22:
                continue

            best = None
            best_score = -1.0

            for old_track in assigned_tracks:
                if int(old_track) == int(current_track):
                    continue

                old_profile = track_to_profile.get(old_track)
                if old_profile is None or old_profile == current_profile:
                    continue

                old_obs = int(track_observation_counts.get(old_track, 0) or len(track_frame_bboxes.get(old_track, {})))
                if old_obs < 20:
                    continue

                old_end = last_frame(old_track)
                old_start = first_frame(old_track)
                if old_end is None or old_start is None:
                    continue

                gap = int(current_start) - int(old_end)
                # Cho phép overlap 1-2 frame do tracker split, nhưng không cho overlap dài.
                if gap < -2 or gap > max_gap_frames:
                    continue

                old_last_bbox = bbox_at(old_track, old_end)
                if old_last_bbox is None:
                    continue

                old_tail_motion = self._track_motion_norm(
                    window_bboxes(old_track, max(old_start, old_end - 20), old_end),
                    max_points=12,
                )
                if old_tail_motion > 0.22:
                    continue

                area_ratio = self._bbox_area_ratio(current_first_bbox, old_last_bbox)
                if not (0.35 <= area_ratio <= 3.0):
                    continue

                iou = self._bbox_iou(current_first_bbox, old_last_bbox)
                containment = self._bbox_containment(current_first_bbox, old_last_bbox)
                center_norm = self._bbox_center_distance_norm(current_first_bbox, old_last_bbox)

                continuity_ok = (
                    iou >= 0.04
                    or containment >= 0.22
                    or center_norm <= 0.18
                )
                if not continuity_ok:
                    continue

                if has_target_same_frame_conflict(current_track, old_profile):
                    continue

                # Ưu tiên predecessor kết thúc gần nhất. Điều này khác neo vùng:
                # profile cũ xa thời gian dù cùng vị trí sẽ không thắng được old_track vừa đứt.
                gap_penalty = max(0, gap) / max(float(max_gap_frames), 1.0)
                overlap_penalty = abs(min(gap, 0)) * 0.08
                score = (
                    iou * 1.20
                    + containment * 0.85
                    + max(0.0, 1.0 - center_norm) * 0.42
                    + min(old_obs / 200.0, 1.0) * 0.10
                    - gap_penalty * 0.45
                    - overlap_penalty
                )

                if score > best_score:
                    best_score = score
                    best = {
                        "old_track": old_track,
                        "old_profile": old_profile,
                        "gap": gap,
                        "iou": iou,
                        "containment": containment,
                        "center_norm": center_norm,
                        "area_ratio": area_ratio,
                        "score": score,
                    }

            if best is None:
                continue

            target_profile = best["old_profile"]
            if target_profile == current_profile:
                continue

            moved = self.online_identity.reassign_track_to_profile(
                track_id=current_track,
                source_profile_id=current_profile,
                target_profile_id=target_profile,
            )
            if moved:
                track_to_profile[current_track] = target_profile
                track_debug_status[current_track] = (
                    f"LINEAGE_CORRECTED_FINAL: Track {current_track} "
                    f"{current_profile} -> {target_profile}, from_track={best['old_track']}, "
                    f"gap={best['gap']}, iou={best['iou']:.3f}, "
                    f"containment={best['containment']:.3f}, center={best['center_norm']:.3f}"
                )
                print(
                    f"[LineageCorrectedFinal] Track {current_track}: {current_profile} -> {target_profile}, "
                    f"from_old_track={best['old_track']}, gap={best['gap']}, "
                    f"iou={best['iou']:.3f}, containment={best['containment']:.3f}, "
                    f"center={best['center_norm']:.3f}, area_ratio={best['area_ratio']:.3f}, "
                    f"score={best['score']:.3f}"
                )

    def _find_strong_bbox_fragment_profile(
        self,
        last_assigned_track_states: Dict[int, Dict],
        frame_profile_locks: Dict[int, Dict[str, Dict]],
        current_frame_index: int,
        current_track_id: int,
        current_bbox: List[float],
        max_gap_frames: int = 90,
        min_old_obs: int = 20,
        iou_threshold: float = 0.08,
        containment_threshold: float = 0.30,
        center_distance_norm_threshold: float = 0.20,
        area_ratio_min: float = 0.35,
        area_ratio_max: float = 3.00,
    ) -> Optional[str]:
        """
        Strong handoff theo TRACK CỤ THỂ, không phải neo vùng.

        Chỉ nối track mới với một old_track_id vừa tồn tại gần đây nếu bbox continuity
        rất rõ. Người đi ngang qua cùng vị trí sau đó thường không pass vì gap lớn hoặc
        bbox/center/area không khớp với old_track cụ thể.
        """
        if not last_assigned_track_states:
            return None

        frame_locks = frame_profile_locks.get(current_frame_index, {})
        best_profile_id = None
        best_track_id = None
        best_score = -1.0
        best_debug = None

        for old_track_id, state in last_assigned_track_states.items():
            if int(old_track_id) == int(current_track_id):
                continue

            profile_id = state.get("profile_id")
            last_frame = state.get("frame_index")
            last_bbox = state.get("bbox")
            old_obs = int(state.get("observation_count", 0) or 0)
            if profile_id is None or last_frame is None or last_bbox is None:
                continue
            if old_obs < min_old_obs:
                continue

            gap = int(current_frame_index) - int(last_frame)
            if gap < 0 or gap > max_gap_frames:
                continue

            # Nếu profile đó đang lock bởi track khác trong cùng frame, chỉ cho nối khi
            # bbox hiện tại là duplicate thật sự của bbox đang lock. Nếu không thì là 2 người.
            if profile_id in frame_locks:
                locked_track_id = frame_locks[profile_id].get("track_id")
                locked_bbox = frame_locks[profile_id].get("bbox")
                if locked_track_id is not None and int(locked_track_id) != int(old_track_id):
                    locked_like, _ = self._is_duplicate_like_bbox(
                        current_bbox,
                        locked_bbox,
                        duplicate_iou_threshold=max(iou_threshold, 0.18),
                        containment_threshold=max(containment_threshold, 0.45),
                        center_distance_norm_threshold=min(center_distance_norm_threshold, 0.16),
                        area_ratio_min=area_ratio_min,
                        area_ratio_max=area_ratio_max,
                    )
                    if not locked_like:
                        continue

            iou = self._bbox_iou(current_bbox, last_bbox)
            containment = self._bbox_containment(current_bbox, last_bbox)
            center_norm = self._bbox_center_distance_norm(current_bbox, last_bbox)
            area_ratio = self._bbox_area_ratio(current_bbox, last_bbox)

            if not (area_ratio_min <= area_ratio <= area_ratio_max):
                continue

            strong_like = (
                iou >= iou_threshold
                or containment >= containment_threshold
                or center_norm <= center_distance_norm_threshold
            )
            if not strong_like:
                continue

            # Score ưu tiên bbox continuity + old track lâu + gap ngắn.
            gap_score = 1.0 - min(gap / max(max_gap_frames, 1), 1.0)
            obs_score = min(old_obs / 120.0, 1.0)
            score = (iou * 1.20) + (containment * 0.90) + ((1.0 - min(center_norm, 1.0)) * 0.55) + (gap_score * 0.35) + (obs_score * 0.20)

            if score > best_score:
                best_score = score
                best_profile_id = profile_id
                best_track_id = old_track_id
                best_debug = (gap, iou, containment, center_norm, area_ratio, old_obs)

        if best_profile_id is not None:
            gap, iou, containment, center_norm, area_ratio, old_obs = best_debug
            print(
                f"[StrongFragmentCandidate] current_track={current_track_id} -> profile={best_profile_id} "
                f"from_old_track={best_track_id}, gap={gap}, old_obs={old_obs}, "
                f"iou={iou:.3f}, containment={containment:.3f}, center={center_norm:.3f}, "
                f"area_ratio={area_ratio:.3f}, score={best_score:.3f}"
            )

        return best_profile_id

    def _find_recent_track_handoff_profile(
        self,
        last_assigned_track_states: Dict[int, Dict],
        frame_profile_locks: Dict[int, Dict[str, Dict]],
        profiles: Dict[str, Dict],
        current_frame_index: int,
        current_track_id: int,
        current_bbox: List[float],
        current_track_frame_bboxes: Optional[Dict[int, List[float]]] = None,
        current_appearance_signature=None,
        appearance_service=None,
        max_gap_frames: int = 60,
        duplicate_iou_threshold: float = 0.18,
        containment_threshold: float = 0.34,
        center_distance_norm_threshold: float = 0.18,
        area_ratio_min: float = 0.35,
        area_ratio_max: float = 2.80,
        old_max_motion_norm: float = 0.055,
        current_max_motion_norm: float = 0.120,
        min_appearance_score: float = 0.46,
    ) -> Optional[str]:
        """
        Nối track mới với TRACK cũ vừa bị đứt, không neo theo vùng/profile.

        Mục tiêu:
        - Cho phép track_id nhảy khi người đứng yên đổi góc mặt.
        - Giữ person_id ổn định nếu fragment mới thật sự là tiếp nối của track vừa mất.
        - Tránh người đi ngang bị kéo nhầm: yêu cầu track cũ gần như đứng yên, track mới
          chưa thể hiện chuyển động đi ngang, thời gian đứt rất ngắn, bbox gần nhau và
          appearance phải đủ giống khi có thể trích được body crop.
        """
        if not last_assigned_track_states:
            return None

        frame_locks = frame_profile_locks.get(current_frame_index, {})
        locked_profiles = set(frame_locks.keys())
        current_track_frame_bboxes = current_track_frame_bboxes or {}

        current_motion = self._track_motion_norm(current_track_frame_bboxes)
        if current_motion > current_max_motion_norm:
            # Track mới đang di chuyển rõ rệt => giống người đi ngang hơn là fragment đứng yên.
            return None

        best_profile_id = None
        best_score = -1.0

        for old_track_id, state in last_assigned_track_states.items():
            if old_track_id == current_track_id:
                continue

            profile_id = state.get("profile_id")
            last_frame = state.get("frame_index")
            last_bbox = state.get("bbox")
            old_track_bboxes = state.get("track_bboxes") or {}

            if profile_id is None or last_frame is None or last_bbox is None:
                continue

            gap = int(current_frame_index) - int(last_frame)
            # Cho phép gap == 0 vì tracker có thể tạo track mới chồng lên track cũ
            # trong cùng frame trước khi track cũ biến mất hoàn toàn.
            if gap < 0 or gap > max_gap_frames:
                continue

            old_obs = int(state.get("observation_count", 0) or 0)
            if old_obs < 8:
                # Track cũ quá ngắn thì không đủ tin cậy để làm lineage source.
                continue

            # Chỉ bridge nếu track cũ là một track đang đứng yên.
            # Đây là điểm khác với neo vùng: người đi ngang bị đứt track sẽ có motion lớn nên bị loại.
            old_motion = self._track_motion_norm(old_track_bboxes)
            if old_motion > old_max_motion_norm:
                continue

            duplicate_like, duplicate_score = self._is_duplicate_like_bbox(
                current_bbox,
                last_bbox,
                duplicate_iou_threshold=duplicate_iou_threshold,
                containment_threshold=containment_threshold,
                center_distance_norm_threshold=center_distance_norm_threshold,
                area_ratio_min=area_ratio_min,
                area_ratio_max=area_ratio_max,
            )
            if not duplicate_like:
                continue

            # Nếu profile vẫn đang được lock bởi track khác ở frame hiện tại, chỉ cho nối nếu
            # bbox hiện tại thực sự là duplicate của bbox đang lock; nếu không là 2 người khác nhau.
            if profile_id in locked_profiles:
                locked_bbox = frame_locks[profile_id].get("bbox")
                locked_like, _ = self._is_duplicate_like_bbox(
                    current_bbox,
                    locked_bbox,
                    duplicate_iou_threshold=0.45,
                    containment_threshold=0.60,
                    center_distance_norm_threshold=0.14,
                    area_ratio_min=0.35,
                    area_ratio_max=3.00,
                )
                if not locked_like:
                    continue

            appearance_score = -1.0
            profile = profiles.get(profile_id) or {}
            if current_appearance_signature is not None and appearance_service is not None:
                scores = []
                for known_sig in profile.get("appearance_signatures", []) or []:
                    try:
                        scores.append(float(appearance_service.compare(current_appearance_signature, known_sig)))
                    except Exception:
                        pass
                if scores:
                    appearance_score = max(scores)

            # Có body appearance thì phải đủ giống. Không có appearance chỉ cho qua khi bbox cực kỳ sát
            # và gap cực ngắn, để không kéo nhầm người đi ngang.
            strict_like, strict_score = self._is_duplicate_like_bbox(
                current_bbox,
                last_bbox,
                duplicate_iou_threshold=0.10,
                containment_threshold=0.42,
                center_distance_norm_threshold=0.24,
                area_ratio_min=0.30,
                area_ratio_max=3.40,
            )

            if appearance_score >= 0.0:
                # Appearance có thể thấp khi người xoay mặt/thân bị crop khác hoặc bị che bởi người phía trước.
                # Vì vậy chỉ loại nếu appearance thấp VÀ bbox không thật sự là fragment liên tục.
                if appearance_score < min_appearance_score and not strict_like:
                    continue
                if strict_like:
                    duplicate_score = max(duplicate_score, strict_score)
            else:
                # Không có appearance: chỉ cho lineage khi bbox rất giống và gap không quá xa.
                if not strict_like or gap > max(6, int(max_gap_frames * 0.70)):
                    continue
                duplicate_score = max(duplicate_score, strict_score)

            # Ưu tiên gap ngắn + bbox giống + appearance giống; không ưu tiên profile theo vùng.
            app_bonus = max(appearance_score, 0.0) * 0.35
            gap_penalty = min(gap / max(max_gap_frames, 1), 1.0) * 0.25
            score = duplicate_score + app_bonus - gap_penalty

            if score > best_score:
                best_score = score
                best_profile_id = profile_id

        if best_profile_id is not None:
            print(
                f"[RecentTrackFragmentBridge] Track {current_track_id} inherits "
                f"profile={best_profile_id} at frame={current_frame_index}, score={best_score:.3f}"
            )

        return best_profile_id

    def _find_recent_stationary_handoff_profile(
        self,
        profiles: Dict[str, Dict],
        current_frame_index: int,
        current_track_id: int,
        current_bbox: List[float],
        max_gap_frames: int = 60,
        duplicate_iou_threshold: float = 0.55,
        containment_threshold: float = 0.70,
        center_distance_norm_threshold: float = 0.12,
        area_ratio_min: float = 0.40,
        area_ratio_max: float = 2.80,
    ) -> Optional[str]:
        """
        Bridge cho tracker-fragment khi một người đứng yên nhưng bị sinh track mới.

        Khác với re-id theo vị trí vào màn hình, hàm này chỉ xét profile vừa được
        thấy rất gần đây và bbox hiện tại gần như cùng một người với bbox cuối.
        Nó giúp tránh việc cùng một người đứng lâu bị tạo personid mới khi mặt đổi góc.
        """
        best_profile_id = None
        best_score = -1.0

        for profile_id, profile in profiles.items():
            if current_track_id in profile.get("track_ids", []):
                continue

            last_frame = profile.get("last_frame_index")
            last_bbox = profile.get("last_bbox")
            if last_frame is None or last_bbox is None:
                continue

            gap = int(current_frame_index) - int(last_frame)
            if gap < 0 or gap > max_gap_frames:
                continue

            duplicate_like, duplicate_score = self._is_duplicate_like_bbox(
                current_bbox,
                last_bbox,
                duplicate_iou_threshold=duplicate_iou_threshold,
                containment_threshold=containment_threshold,
                center_distance_norm_threshold=center_distance_norm_threshold,
                area_ratio_min=area_ratio_min,
                area_ratio_max=area_ratio_max,
            )
            if not duplicate_like:
                continue

            # Ưu tiên profile vừa mất track gần nhất; sau đó mới đến độ giống bbox.
            score = duplicate_score - min(gap / max(max_gap_frames, 1), 1.0) * 0.10
            if score > best_score:
                best_score = score
                best_profile_id = profile_id

        if best_profile_id is not None:
            print(
                f"[StationaryHandoffBridge] Track {current_track_id} inherits "
                f"profile={best_profile_id} at frame={current_frame_index}, score={best_score:.3f}"
            )

        return best_profile_id

    def _find_online_relink_candidate(
        self,
        ranked_candidates: List[Dict],
        current_profile_id: str,
        track_id: int,
        bbox: List[float],
        frame_index: int,
        frame_profile_locks: Dict[int, Dict[str, Dict]],
        face_conf: float,
        stale_strong_face: float,
        stale_strong_total: float,
        stale_strong_margin: float,
        entry_reuse_strong_face: float,
        entry_reuse_strong_face_conf: float,
        entry_reuse_strong_margin: float,
        min_face: float,
        min_total: float,
        min_face_conf: float,
    ) -> Optional[Dict]:
        """
        Tìm profile khác để sửa lại một track đã assigned nhầm.

        Lưu ý: Không so với current_profile theo score nữa, vì current_profile
        có thể đã bị nhiễm embedding của chính track hiện tại. Nếu so trực tiếp,
        P006 sẽ luôn thắng nhờ self-match với track56. Do đó chỉ xét candidate
        khác profile hiện tại và yêu cầu ngưỡng face/total/conf đủ cao.
        """
        if not ranked_candidates or face_conf < min_face_conf:
            return None

        for candidate in ranked_candidates:
            candidate_profile_id = candidate.get("profile_id")
            if candidate_profile_id is None or candidate_profile_id == current_profile_id:
                continue

            if candidate.get("face", -1.0) < min_face:
                continue
            if candidate.get("total", -1.0) < min_total:
                continue

            # ------------------------------------------------------------
            # STABLE RELINK GUARD
            # ------------------------------------------------------------
            # V4 đã đạt nhiều cụm đúng nhưng vẫn còn lỗi ping-pong:
            # một track đã có P_id bị kéo qua lại giữa nhiều profile chỉ vì
            # face score rất cao trong vài frame, trong khi margin/app thấp.
            # Với camera realtime, đổi P_id liên tục sẽ phá overlay và
            # trajectory P_id -> track_id[]. Vì vậy relink online phải rất
            # bảo thủ; các sửa body/tracklet/refine sẽ xử lý các case còn lại.
            cand_margin = float(candidate.get("margin", -1.0))
            cand_app = float(candidate.get("app", 0.0))
            cand_face = float(candidate.get("face", -1.0))
            cand_total = float(candidate.get("total", -1.0))
            cand_risk = candidate.get("temporal_spatial_risk")

            # Ambiguous candidate: top profiles quá sát nhau. Không relink bằng
            # face-only khi app/margin chưa đủ rõ, vì đây là nguyên nhân chính
            # khiến track84/83/87 nhảy qua lại P_0002/P_0003/P_0005/P_0008.
            #
            # V4.2.21: chặn thêm "fake margin". Trong log track29 đã vào đúng
            # P_0002, nhưng bị kéo qua P_0006/P_0001 vì selected candidate có
            # margin=1.000 trong khi app thấp/vừa. Đây không phải bằng chứng mạnh,
            # chỉ là artifact của ranked candidate sau khi bỏ qua current profile.
            super_strong = (
                cand_face >= 0.985
                and cand_total >= 0.965
                and cand_app >= 0.86
                and cand_margin >= 0.030
                and face_conf >= 0.88
            )
            fake_margin = cand_margin >= 0.999
            if fake_margin and not (
                cand_face >= 0.985
                and cand_total >= 0.965
                and cand_app >= 0.90
                and face_conf >= 0.86
            ):
                print(
                    f"[IDDBG_RELINK_REJECT] track={track_id} candidate={candidate_profile_id} "
                    f"reason=stable_relink_fake_margin_not_strong_enough, total={cand_total:.3f}, "
                    f"face={cand_face:.3f}, app={cand_app:.3f}, margin={cand_margin:.3f}, "
                    f"risk={cand_risk}"
                )
                continue

            if not super_strong:
                if cand_margin < 0.018:
                    print(
                        f"[IDDBG_RELINK_REJECT] track={track_id} candidate={candidate_profile_id} "
                        f"reason=stable_relink_too_ambiguous, total={cand_total:.3f}, "
                        f"face={cand_face:.3f}, app={cand_app:.3f}, margin={cand_margin:.3f}, "
                        f"risk={cand_risk}"
                    )
                    continue
                if cand_margin < 0.045 and cand_app < 0.82:
                    print(
                        f"[IDDBG_RELINK_REJECT] track={track_id} candidate={candidate_profile_id} "
                        f"reason=stable_relink_requires_app_or_margin, total={cand_total:.3f}, "
                        f"face={cand_face:.3f}, app={cand_app:.3f}, margin={cand_margin:.3f}, "
                        f"risk={cand_risk}"
                    )
                    continue
                if cand_risk is not None and (cand_margin < 0.075 or cand_app < 0.84):
                    print(
                        f"[IDDBG_RELINK_REJECT] track={track_id} candidate={candidate_profile_id} "
                        f"reason=stable_relink_risk_requires_strong_app_margin, total={cand_total:.3f}, "
                        f"face={cand_face:.3f}, app={cand_app:.3f}, margin={cand_margin:.3f}, "
                        f"risk={cand_risk}"
                    )
                    continue

            if self._is_profile_locked_by_other_track_in_frame(
                frame_profile_locks=frame_profile_locks,
                frame_index=frame_index,
                profile_id=candidate_profile_id,
                current_track_id=track_id,
                current_bbox=bbox,
                duplicate_iou_threshold=0.45,
            ):
                continue

            allowed, reason = self._is_temporal_spatial_reid_allowed(
                candidate=candidate,
                face_conf=face_conf,
                stale_strong_face=stale_strong_face,
                stale_strong_total=stale_strong_total,
                stale_strong_margin=stale_strong_margin,
                entry_reuse_strong_face=entry_reuse_strong_face,
                entry_reuse_strong_face_conf=entry_reuse_strong_face_conf,
                entry_reuse_strong_margin=entry_reuse_strong_margin,
            )

            if not allowed:
                if self._is_suspicious_candidate(candidate):
                    print(
                        f"[IDDBG_RELINK_REJECT] track={track_id} candidate={candidate_profile_id} "
                        f"reason={reason}, total={candidate.get('total', -1.0):.3f}, "
                        f"face={candidate.get('face', -1.0):.3f}, app={candidate.get('app', 0.0):.3f}, "
                        f"margin={candidate.get('margin', -1.0):.3f}, risk={candidate.get('temporal_spatial_risk')}"
                    )
                continue

            return candidate

        return None

    def _update_and_check_candidate_confirmation(
        self,
        track_candidate_history: Dict[int, List[Dict]],
        track_id: int,
        candidate: Dict,
        frame_index: int,
        obs_count: int,
        min_samples: int,
        min_obs: int,
        min_avg_face: float,
        min_avg_total: float,
        max_history: int,
    ) -> bool:
        history = track_candidate_history.setdefault(track_id, [])
        history.append({
            "profile_id": candidate.get("profile_id"),
            "frame_index": frame_index,
            "face": float(candidate.get("face", -1.0)),
            "total": float(candidate.get("total", -1.0)),
        })
        if len(history) > max_history:
            del history[:-max_history]

        same_profile = [
            h for h in history
            if h.get("profile_id") == candidate.get("profile_id")
        ]
        if len(same_profile) < min_samples or obs_count < min_obs:
            return False

        recent = same_profile[-min_samples:]
        avg_face = sum(h["face"] for h in recent) / len(recent)
        avg_total = sum(h["total"] for h in recent) / len(recent)
        return avg_face >= min_avg_face and avg_total >= min_avg_total

    def _update_and_check_profile_reassignment_confirmation(
        self,
        track_reassignment_history: Dict[int, List[Dict]],
        track_id: int,
        candidate: Dict,
        frame_index: int,
        min_samples: int,
        min_avg_face: float,
        min_avg_total: float,
        max_history: int,
    ) -> bool:
        history = track_reassignment_history.setdefault(track_id, [])
        history.append({
            "profile_id": candidate.get("profile_id"),
            "frame_index": frame_index,
            "face": float(candidate.get("face", -1.0)),
            "total": float(candidate.get("total", -1.0)),
        })
        if len(history) > max_history:
            del history[:-max_history]

        same_profile = [
            h for h in history
            if h.get("profile_id") == candidate.get("profile_id")
        ]
        if len(same_profile) < min_samples:
            return False

        recent = same_profile[-min_samples:]
        avg_face = sum(h["face"] for h in recent) / len(recent)
        avg_total = sum(h["total"] for h in recent) / len(recent)
        return avg_face >= min_avg_face and avg_total >= min_avg_total

    def _is_short_gap_strong_entry_return_candidate(
        self,
        candidate: Dict,
        face_conf: float,
        *,
        max_gap_frames: int = 90,
        min_face: float = 0.94,
        min_total: float = 0.90,
        min_app: float = 0.72,
        min_face_conf: float = 0.80,
    ) -> bool:
        """
        Cho phép một case rất hẹp của entry_reuse_after_absence.

        Lý do: ở video 2, track29 là khách quay lại đúng profile cũ nhưng candidate
        đúng bị gắn risk=entry_reuse_after_absence do xuất hiện gần điểm vào cũ.
        Nếu block candidate đúng rồi fallback sang profile không-risk như P001 thì còn sai hơn.

        Rule này không dùng track id/P id:
        - chỉ áp dụng khi gap rất ngắn;
        - face/total cực cao;
        - appearance đủ tốt;
        - face crop hiện tại đủ rõ.
        Margin không bắt buộc cao vì top candidate đúng thường bị margin mỏng khi gallery có
        nhiều face rất giống nhau.
        """
        if not candidate:
            return False
        if candidate.get("temporal_spatial_risk") != "entry_reuse_after_absence":
            return False
        gap = candidate.get("gap_frames")
        try:
            gap_ok = gap is not None and 0 <= int(gap) <= int(max_gap_frames)
        except Exception:
            gap_ok = False
        return bool(
            gap_ok
            and float(candidate.get("face", -1.0)) >= float(min_face)
            and float(candidate.get("total", -1.0)) >= float(min_total)
            and float(candidate.get("app", 0.0)) >= float(min_app)
            and float(face_conf) >= float(min_face_conf)
        )


    def _select_short_gap_entry_return_over_far_candidate(
        self,
        selected_candidate: Dict,
        ranked_candidates: List[Dict],
        face_conf: float,
        *,
        max_short_gap_frames: int = 90,
        min_selected_far_gap_frames: int = 180,
        min_face: float = 0.94,
        min_total: float = 0.90,
        min_app: float = 0.72,
        max_total_drop: float = 0.025,
        min_app_advantage: float = -0.03,
        max_selected_margin: float = 0.020,
        min_face_conf: float = 0.80,
    ) -> Optional[Dict]:
        """
        Khi track mới có candidate đúng bị gắn risk=entry_reuse_after_absence vì gap ngắn,
        nhưng một profile no-risk rất xa lại đứng top hơn rất ít, không được fallback sang
        profile xa đó. Đây là lỗi track29: P đúng có gap ngắn/app tốt, P001 thắng rất mỏng
        nhờ face vector.

        Rule này không hardcode track/P:
        - selected hiện tại phải là profile xa hoặc margin rất mỏng;
        - candidate thay thế phải là entry_reuse_after_absence/stale_entry_reuse với gap ngắn;
        - face/total/app đủ tốt;
        - không thua selected quá nhiều, hoặc app tốt hơn selected.
        """
        if not selected_candidate or not ranked_candidates:
            return None
        if float(face_conf or 0.0) < float(min_face_conf):
            return None

        try:
            selected_gap = selected_candidate.get("gap_frames")
            selected_gap = int(selected_gap) if selected_gap is not None else 10**9
        except Exception:
            selected_gap = 10**9
        selected_risk = selected_candidate.get("temporal_spatial_risk")
        selected_total = float(selected_candidate.get("total", -1.0) or -1.0)
        selected_app = float(selected_candidate.get("app", 0.0) or 0.0)
        selected_margin = float(selected_candidate.get("margin", 1.0) or 1.0)

        # Chỉ can thiệp khi selected là lựa chọn không chắc: gap xa hoặc margin rất mỏng.
        selected_is_weak_far_choice = (
            selected_risk is None
            and (
                selected_gap >= int(min_selected_far_gap_frames)
                or selected_margin <= float(max_selected_margin)
            )
        )
        if not selected_is_weak_far_choice:
            return None

        best_alt = None
        best_alt_key = None
        for cand in ranked_candidates:
            if not cand or cand is selected_candidate:
                continue
            risk = cand.get("temporal_spatial_risk")
            if risk not in ("entry_reuse_after_absence", "stale_entry_reuse"):
                continue
            try:
                gap = cand.get("gap_frames")
                gap = int(gap) if gap is not None else 10**9
            except Exception:
                gap = 10**9
            if gap < 0 or gap > int(max_short_gap_frames):
                continue
            face = float(cand.get("face", -1.0) or -1.0)
            total = float(cand.get("total", -1.0) or -1.0)
            app = float(cand.get("app", 0.0) or 0.0)
            if face < float(min_face) or total < float(min_total) or app < float(min_app):
                continue
            if total < selected_total - float(max_total_drop):
                continue
            if app < selected_app + float(min_app_advantage):
                continue
            key = (app - selected_app, total, face, -gap)
            if best_alt is None or key > best_alt_key:
                best_alt = cand
                best_alt_key = key

        if best_alt is not None:
            print(
                f"[IDDBG_SHORT_GAP_ENTRY_RETURN_OVERRIDE] "
                f"selected={selected_candidate.get('profile_id')}[tot={selected_total:.3f},"
                f"face={float(selected_candidate.get('face', -1.0)):.3f},"
                f"app={selected_app:.3f},gap={selected_gap},risk={selected_risk}] -> "
                f"alt={best_alt.get('profile_id')}[tot={float(best_alt.get('total', -1.0)):.3f},"
                f"face={float(best_alt.get('face', -1.0)):.3f},"
                f"app={float(best_alt.get('app', 0.0)):.3f},"
                f"gap={best_alt.get('gap_frames')},risk={best_alt.get('temporal_spatial_risk')}]"
            )
        return best_alt

    def _is_temporal_spatial_reid_allowed(
        self,
        candidate: Dict,
        face_conf: float,
        stale_strong_face: float,
        stale_strong_total: float,
        stale_strong_margin: float,
        entry_reuse_strong_face: float = 0.62,
        entry_reuse_strong_face_conf: float = 0.82,
        entry_reuse_strong_margin: float = 0.10,
    ):
        """
        Generic gate cho profile đã vắng mặt lâu.

        Không hard-code lane/camera position. Chỉ xét:
        - candidate đã stale chưa;
        - track mới bắt đầu gần điểm vào cũ hay điểm ra cũ;
        - face/total/margin có đủ mạnh để override spatial risk không.
        """

        risk = candidate.get("temporal_spatial_risk")

        strong_entry_reuse_reid = (
            candidate.get("face", -1.0) >= entry_reuse_strong_face
            and candidate.get("margin", -1.0) >= entry_reuse_strong_margin
            and face_conf >= entry_reuse_strong_face_conf
        )

        short_gap_strong_return = self._is_short_gap_strong_entry_return_candidate(
            candidate,
            face_conf,
        )

        # Cực kỳ quan trọng: entry-overlap sau khi người trước đã rời đi
        # phải bị chặn kể cả khi chưa đủ stale 45s. Nếu không, video có nhiều người
        # đi vào cùng cửa/vùng bắt đầu sẽ bị reuse nhầm profile cũ.
        # Ngoại lệ hẹp: short-gap strong return, để không fallback sang P không-risk sai.
        if risk == "entry_reuse_after_absence" and not (strong_entry_reuse_reid or short_gap_strong_return):
            return False, "entry_reuse_after_absence_requires_face_only_strong_match"

        if not candidate.get("is_stale", False):
            return True, None

        strong_stale_reid = (
            candidate.get("face", -1.0) >= stale_strong_face
            and candidate.get("total", -1.0) >= stale_strong_total
            and candidate.get("margin", -1.0) >= stale_strong_margin
            and face_conf >= 0.78
        )

        if risk == "stale_entry_reuse" and not (strong_entry_reuse_reid and strong_stale_reid):
            return False, "stale_entry_reuse_requires_very_strong_face"

        if risk == "stale_far_from_last_seen" and not strong_stale_reid:
            return False, "stale_far_from_last_seen_requires_strong_face"

        # Ngay cả khi xuất hiện gần điểm ra cũ, profile đã vắng mặt lâu vẫn phải
        # có face/total/margin đủ rõ, tránh P004 thật bị kéo thành P006 chỉ vì
        # P006 cũng rời ở góc dưới phải trước đó.
        if risk == "stale_return_candidate" and not strong_stale_reid:
            return False, "stale_return_requires_strong_face"

        return True, None

    def _is_ambiguous_ranked_match(
        self,
        ranked_candidates: List[Dict],
        ambiguous_margin: float,
        min_total: float,
        strong_face: float,
    ) -> bool:
        if len(ranked_candidates) < 2:
            return False

        first = ranked_candidates[0]
        second = ranked_candidates[1]

        if first.get("total", -1.0) < min_total:
            return False

        if first.get("face", -1.0) >= strong_face:
            return False

        if (first.get("total", -1.0) - second.get("total", -1.0)) < ambiguous_margin:
            return True

        # Hai candidate đều stale/return risk thì không auto-pick khi face chưa mạnh.
        if (
            first.get("is_stale", False)
            and second.get("is_stale", False)
            and first.get("face", -1.0) < strong_face
        ):
            return True

        return False

    def _safe_handoff_merge_profiles(self, profiles: List[Dict]) -> List[Dict]:
        """
        Merge nhẹ cuối video cho các profile có khả năng là cùng người
        nhưng bị tách do tracker handoff.

        Chỉ xử lý case:
        - Không overlap frame.
        - Khoảng cách thời gian giữa profile A kết thúc và profile B bắt đầu không quá lớn.
        - Điểm face/app không cần quá cao, nhưng phải có tín hiệu vừa đủ.
        - Không dùng merge đại trà.
        """

        if len(profiles) <= 1:
            return profiles

        HANDOFF_MAX_GAP_FRAMES = 80
        HANDOFF_MIN_TOTAL = 0.35
        HANDOFF_MIN_FACE = 0.30
        HANDOFF_MIN_APP = 0.50

        changed = True

        while changed:
            changed = False
            removed_ids = set()

            profiles = sorted(
                profiles,
                key=lambda p: min(p.get("observed_frame_indices", [10**9]))
            )

            for i, profile_a in enumerate(profiles):
                if profile_a["profile_id"] in removed_ids:
                    continue

                frames_a = profile_a.get("observed_frame_indices", [])
                if not frames_a:
                    continue

                end_a = max(frames_a)

                best_j = None
                best_score = -1.0

                for j, profile_b in enumerate(profiles):
                    if i == j or profile_b["profile_id"] in removed_ids:
                        continue

                    frames_b = profile_b.get("observed_frame_indices", [])
                    if not frames_b:
                        continue

                    start_b = min(frames_b)

                    # Chỉ xét profile B xuất hiện sau A
                    gap = start_b - end_a
                    if gap < 0 or gap > HANDOFF_MAX_GAP_FRAMES:
                        continue

                    # Nếu overlap frame thì không merge ở bước handoff
                    if set(frames_a).intersection(set(frames_b)):
                        continue

                    total, face, app = self._profile_pair_score(profile_a, profile_b)

                    print(
                        f"[SafeHandoffMerge] {profile_a['profile_id']} "
                        f"vs {profile_b['profile_id']} | "
                        f"gap={gap}, total={total:.3f}, face={face:.3f}, app={app:.3f}"
                    )

                    if (
                        total >= HANDOFF_MIN_TOTAL
                        and face >= HANDOFF_MIN_FACE
                        and app >= HANDOFF_MIN_APP
                        and total > best_score
                    ):
                        best_score = total
                        best_j = j

                if best_j is not None:
                    target = profile_a
                    source = profiles[best_j]

                    print(
                        f"[SafeHandoffMerge] MERGE {source['profile_id']} "
                        f"-> {target['profile_id']} | score={best_score:.3f}"
                    )

                    self._merge_profile_dict(target, source)
                    removed_ids.add(source["profile_id"])
                    changed = True

            if removed_ids:
                profiles = [
                    p for p in profiles
                    if p["profile_id"] not in removed_ids
                ]

        return profiles

    def _profile_pair_score(self, profile_a: Dict, profile_b: Dict):
        best_face = -1.0
        best_app = 0.0

        embeddings_a = profile_a.get("embeddings", [])
        embeddings_b = profile_b.get("embeddings", [])

        for emb_a in embeddings_a:
            vec_a = self._normalize_vector(np.array(emb_a, dtype=np.float32))
            if vec_a is None:
                continue

            for emb_b in embeddings_b:
                vec_b = self._normalize_vector(np.array(emb_b, dtype=np.float32))
                if vec_b is None:
                    continue

                score = float(np.dot(vec_a, vec_b))
                best_face = max(best_face, score)

        app_sigs_a = profile_a.get("appearance_signatures", [])
        app_sigs_b = profile_b.get("appearance_signatures", [])

        for sig_a in app_sigs_a:
            for sig_b in app_sigs_b:
                score = self.appearance_service.compare(sig_a, sig_b)
                best_app = max(best_app, score)

        if best_face < 0:
            best_face = 0.0

        total = best_face * 0.70 + best_app * 0.30

        return total, best_face, best_app

    def _merge_profile_dict(self, target: Dict, source: Dict) -> None:
        target["merged_track_ids"] = sorted(
            list(set(target.get("merged_track_ids", []) + source.get("merged_track_ids", [])))
        )

        target["total_observations"] = (
            target.get("total_observations", 0)
            + source.get("total_observations", 0)
        )

        target["embeddings"] = (
            target.get("embeddings", []) + source.get("embeddings", [])
        )[-5:]

        target["appearance_signatures"] = (
            target.get("appearance_signatures", []) + source.get("appearance_signatures", [])
        )[-5:]

        frames = set(target.get("observed_frame_indices", []))
        frames.update(source.get("observed_frame_indices", []))
        target["observed_frame_indices"] = sorted(list(frames))

        if source.get("best_face_confidence", 0) > target.get("best_face_confidence", 0):
            target["best_face_confidence"] = source.get("best_face_confidence")
            target["best_face_image_path"] = source.get("best_face_image_path")
            target["primary_embedding"] = source.get("primary_embedding")

        target.setdefault("match_scores", [])
        target["match_scores"].extend(source.get("match_scores", []))

    def _normalize_vector(self, vec: np.ndarray):
        norm = np.linalg.norm(vec)
        if norm == 0:
            return None
        return vec / norm

    def _rescue_stable_pending_tracks(
        self,
        track_observation_counts: Dict[int, int],
        track_to_profile: Dict[int, str],
        track_best_identity_sample: Dict[int, Dict],
        track_frame_indices: Dict[int, set],
        track_frame_bboxes: Dict[int, Dict],
        track_debug_status: Dict[int, str],
        min_obs: int = 30,
        min_best_face_conf: float = 0.70,
    ) -> None:
        """
        Cứu các track dài, ổn định, có best face tốt nhưng cuối video bị pending
        vì frame cuối không detect được face.

        Ví dụ:
        Track 2 obs=357, best_face_conf=0.926, nhưng status cuối là
        PENDING: YuNet did not detect face.
        """

        for track_id, obs_count in sorted(track_observation_counts.items()):
            if track_id in track_to_profile:
                continue

            if obs_count < min_obs:
                continue

            best_sample = track_best_identity_sample.get(track_id)

            if not best_sample:
                track_debug_status[track_id] = (
                    f"PENDING: stable track but no best identity sample, "
                    f"obs={obs_count}"
                )
                continue

            best_conf = best_sample.get("face_confidence", 0.0)

            if best_conf < min_best_face_conf:
                track_debug_status[track_id] = (
                    f"PENDING: stable track but best_conf too low, "
                    f"best_conf={best_conf:.2f}, obs={obs_count}"
                )
                continue

            current_track_frames = sorted(list(track_frame_indices.get(track_id, set())))
            current_track_frame_bboxes = track_frame_bboxes.get(track_id, {})

            (
                best_profile_id,
                best_total_score,
                best_face_score,
                best_app_score,
                best_margin,
            ) = self.online_identity.find_best_profile(
                embedding=best_sample["embedding"],
                appearance_signature=best_sample.get("appearance_signature"),
                current_frame_index=best_sample["frame_index"],
                current_track_frames=current_track_frames,
                current_track_frame_bboxes=current_track_frame_bboxes,
                appearance_service=self.appearance_service,
            )

            # Nếu nó rất gần profile cũ thì không tạo mới vội.
            # Nhưng nếu không gần ai thì tạo profile riêng.
            near_existing_profile = (
                best_profile_id is not None
                and best_total_score >= 0.38
            )

            if near_existing_profile:
                track_debug_status[track_id] = (
                    f"PENDING: stable track near existing profile, "
                    f"best_profile={best_profile_id}, "
                    f"total={best_total_score:.3f}, "
                    f"face={best_face_score:.3f}, "
                    f"app={best_app_score:.3f}, "
                    f"margin={best_margin:.3f}, "
                    f"best_conf={best_conf:.2f}, "
                    f"obs={obs_count}"
                )
                continue

            profile_id = self.online_identity.create_new_profile(
                track_id=track_id,
                embedding=best_sample["embedding"],
                face_image_path=best_sample["face_image_path"],
                face_confidence=best_sample["face_confidence"],
                frame_index=best_sample["frame_index"],
                observation_count=obs_count,
                observed_frame_indices=current_track_frames,
                appearance_signature=best_sample.get("appearance_signature"),
                bbox=best_sample.get("bbox"),
            )

            track_to_profile[track_id] = profile_id

            track_debug_status[track_id] = (
                f"RESCUED_NEW: Track {track_id} -> {profile_id}, "
                f"best_conf={best_conf:.2f}, "
                f"obs={obs_count}, "
                f"reason=stable pending track"
            )

            print(
                f"[RescueStableTrack] Track {track_id} -> new {profile_id}, "
                f"best_conf={best_conf:.2f}, obs={obs_count}"
            )

    def _is_profile_locked_by_other_track_in_frame(
        self,
        frame_profile_locks: Dict[int, Dict[str, Dict]],
        frame_index: int,
        profile_id: str,
        current_track_id: int,
        current_bbox: List[float],
        duplicate_iou_threshold: float = 0.45,
    ) -> bool:
        """
        Chặn case:
        - cùng 1 frame
        - 2 track_id khác nhau
        - bbox khác nhau rõ ràng
        - nhưng online matching muốn gán cùng profile_id

        Cho phép nếu bbox overlap cao vì có thể là tracker duplicate cùng một người.
        """

        frame_locks = frame_profile_locks.get(frame_index, {})
        locked = frame_locks.get(profile_id)

        if not locked:
            return False

        locked_track_id = locked.get("track_id")
        locked_bbox = locked.get("bbox")

        if locked_track_id == current_track_id:
            return False

        iou = self._bbox_iou(current_bbox, locked_bbox)
        containment = self._bbox_containment(current_bbox, locked_bbox)
        center_norm = self._bbox_center_distance_norm(current_bbox, locked_bbox)
        area_ratio = self._bbox_area_ratio(current_bbox, locked_bbox)

        duplicate_like = (
            iou >= duplicate_iou_threshold
            or containment >= 0.55
            or (center_norm <= 0.20 and 0.35 <= area_ratio <= 3.20 and containment >= 0.12)
        )

        if duplicate_like:
            # Có thể là duplicate/fragment cùng một người trong cùng frame.
            return False

        print(
            f"[FrameProfileLock] BLOCK profile={profile_id} "
            f"for track={current_track_id} at frame={frame_index}. "
            f"Already used by track={locked_track_id}, bbox_iou={iou:.3f}, "
            f"containment={containment:.3f}, center_norm={center_norm:.3f}, area_ratio={area_ratio:.3f}"
        )

        return True

    def _is_visual_contradiction_with_profile(
        self,
        current_track: int,
        candidate_profile_id: str,
        track_to_profile: Dict[int, str],
        track_body_reid_samples: Dict[int, List[Dict]],
        candidate_face_score: float,
        candidate_margin: float,
        min_current_samples: int,
        min_profile_samples: int,
        max_avg_top: float,
        max_best: float,
        color_max_avg_top: float,
        color_max_best: float,
        face_override: float,
        margin_override: float,
    ):
        """
        Chặn match một track mới vào profile cũ khi body/clothes mâu thuẫn rõ.
        Đây là guard cho case người áo đỏ bị kéo vào P006 áo trắng.

        Không block nếu face thật sự cực mạnh + margin cao, vì khi đó có thể là cùng người
        thay áo hoặc body crop nhiễu.
        """
        current_samples = track_body_reid_samples.get(current_track, []) or []
        if len(current_samples) < int(min_current_samples):
            return False, {"reason": "not_enough_current_samples", "current_samples": len(current_samples)}

        if candidate_face_score >= face_override and candidate_margin >= margin_override:
            return False, {"reason": "strong_face_override"}

        profile_samples = []
        for old_track, profile_id in (track_to_profile or {}).items():
            old_track = int(old_track)
            if old_track == current_track or profile_id != candidate_profile_id:
                continue
            profile_samples.extend(track_body_reid_samples.get(old_track, []) or [])

        if len(profile_samples) < int(min_profile_samples):
            return False, {
                "reason": "not_enough_profile_samples",
                "current_samples": len(current_samples),
                "profile_samples": len(profile_samples),
            }

        body_info = self.person_reid_service.compare_tracklets(profile_samples, current_samples)
        avg_top = float(body_info.get("avg_top", 0.0))
        best = float(body_info.get("best", 0.0))
        color_avg_top = float(body_info.get("color_avg_top", 0.0))
        color_best = float(body_info.get("color_best", 0.0))

        histogram_conflict = bool(avg_top <= max_avg_top and best <= max_best)
        color_conflict = bool(color_avg_top <= color_max_avg_top and color_best <= color_max_best)
        blocked = bool(histogram_conflict or color_conflict)
        return blocked, {
            "reason": "visual_body_contradiction" if blocked else "body_ok",
            "avg_top": avg_top,
            "best": best,
            "color_avg_top": color_avg_top,
            "color_best": color_best,
            "histogram_conflict": histogram_conflict,
            "color_conflict": color_conflict,
            "current_samples": len(current_samples),
            "profile_samples": len(profile_samples),
        }

    def _split_body_visual_outlier_tracks(
        self,
        track_to_profile: Dict[int, str],
        track_body_reid_samples: Dict[int, List[Dict]],
        track_observation_counts: Dict[int, int],
        track_debug_status: Dict[int, str],
        min_profile_tracks: int,
        min_obs: int,
        min_current_samples: int,
        min_peer_samples: int,
        max_avg_top: float,
        max_best: float,
        color_max_avg_top: float,
        color_max_best: float,
    ) -> None:
        """
        Cuối video, tách một track ra profile mới nếu body/áo quần của nó mâu thuẫn
        rõ với các track còn lại trong cùng profile. Dùng cho case track54 áo đỏ bị
        nhét vào P006 áo trắng. Không merge profile, chỉ split riêng track outlier.
        """
        if not track_to_profile or not track_body_reid_samples:
            return

        changed = True
        pass_index = 0
        while changed and pass_index < 2:
            changed = False
            pass_index += 1

            profile_to_tracks: Dict[str, List[int]] = {}
            for tid, pid in list(track_to_profile.items()):
                if pid:
                    profile_to_tracks.setdefault(pid, []).append(int(tid))

            for profile_id, tracks in sorted(profile_to_tracks.items()):
                if len(tracks) < int(min_profile_tracks):
                    continue

                for tid in sorted(tracks):
                    if track_observation_counts.get(tid, 0) < int(min_obs):
                        continue
                    current_samples = track_body_reid_samples.get(tid, []) or []
                    if len(current_samples) < int(min_current_samples):
                        continue

                    peer_samples = []
                    peer_tracks = []
                    for other_tid in tracks:
                        other_tid = int(other_tid)
                        if other_tid == tid:
                            continue
                        samples = track_body_reid_samples.get(other_tid, []) or []
                        if len(samples) >= int(min_peer_samples):
                            peer_samples.extend(samples)
                            peer_tracks.append(other_tid)

                    if len(peer_samples) < int(min_peer_samples):
                        continue
                    # v4.2.26: không tách outlier khi chỉ có 1 peer đủ samples.
                    # Log v4.2.25 đã tách nhầm track17 chỉ vì so với peer=[33].
                    # Body outlier cần ít nhất 2 track peer ổn định để tạo consensus thật.
                    if len(peer_tracks) < 2:
                        continue

                    body_info = self.person_reid_service.compare_tracklets(peer_samples, current_samples)
                    avg_top = float(body_info.get("avg_top", 0.0))
                    best = float(body_info.get("best", 0.0))
                    color_avg_top = float(body_info.get("color_avg_top", 0.0))
                    color_best = float(body_info.get("color_best", 0.0))

                    histogram_outlier = bool(avg_top <= max_avg_top and best <= max_best)
                    color_outlier = bool(color_avg_top <= color_max_avg_top and color_best <= color_max_best)
                    if not (histogram_outlier or color_outlier):
                        continue

                    new_profile_id = self.online_identity.split_track_to_new_profile(
                        track_id=tid,
                        source_profile_id=profile_id,
                    )
                    if not new_profile_id:
                        continue

                    track_to_profile[tid] = new_profile_id
                    changed = True
                    track_debug_status[tid] = (
                        f"BODY_VISUAL_OUTLIER_SPLIT: Track {tid} "
                        f"{profile_id} -> {new_profile_id}, "
                        f"avg_top={avg_top:.3f}, best={best:.3f}, color_avg={color_avg_top:.3f}, color_best={color_best:.3f}, peers={peer_tracks}"
                    )
                    print(
                        f"[BodyVisualOutlierSplit] Track {tid}: "
                        f"{profile_id} -> {new_profile_id} | "
                        f"avg_top={avg_top:.3f}, best={best:.3f}, color_avg={color_avg_top:.3f}, color_best={color_best:.3f}, peers={peer_tracks}"
                    )
                    break
                if changed:
                    break

    def _split_cohesive_visual_subgroup_profiles(
        self,
        *,
        track_to_profile: Dict[int, str],
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
        track_body_reid_samples: Dict[int, List[Dict]],
        track_observation_counts: Dict[int, int],
        track_debug_status: Dict[int, str],
        min_profile_tracks: int,
        min_group_tracks: int,
        max_group_tracks: int,
        min_rest_tracks: int,
        min_track_obs: int,
        min_track_samples: int,
        min_group_body: float,
        min_group_color: float,
        max_rest_body: float,
        max_rest_color: float,
        min_start_gap_frames: int,
    ) -> bool:
        """
        Final-only split cho profile bị trộn thành 2 cụm visual/temporal rõ rệt.

        Khác với single outlier split, rule này tách nguyên một subgroup tự đồng nhất
        gồm nhiều track khỏi phần còn lại. Không hardcode P_id/track_id; dùng:
        - subgroup có nhiều track đủ body samples;
        - các track trong subgroup giống nhau;
        - subgroup khác phần còn lại theo body/color;
        - subgroup bắt đầu sau phần còn lại một khoảng đủ lớn, để tránh phá các track
          cùng lúc thật sự thuộc cùng người.
        """
        if not track_to_profile or not track_body_reid_samples:
            return False

        import itertools

        profile_to_tracks: Dict[str, List[int]] = {}
        for tid, pid in list(track_to_profile.items()):
            if pid:
                profile_to_tracks.setdefault(pid, []).append(int(tid))

        def _span_start(tid: int) -> int:
            span = self._track_span(track_frame_bboxes, int(tid))
            return int(span[0]) if span is not None else -1

        best_move = None
        for profile_id, raw_tracks in sorted(profile_to_tracks.items()):
            tracks = sorted(set(int(t) for t in raw_tracks))
            if len(tracks) < int(min_profile_tracks):
                continue

            eligible = []
            for tid in tracks:
                if int(track_observation_counts.get(tid, 0) or 0) < int(min_track_obs):
                    continue
                samples = track_body_reid_samples.get(int(tid), []) or []
                if len(samples) < int(min_track_samples):
                    continue
                if _span_start(tid) < 0:
                    continue
                eligible.append(int(tid))

            if len(eligible) < int(min_group_tracks) + int(min_rest_tracks):
                continue

            for group_size in range(int(min_group_tracks), min(int(max_group_tracks), len(eligible) - int(min_rest_tracks)) + 1):
                for group in itertools.combinations(eligible, group_size):
                    group = sorted(int(x) for x in group)
                    rest = sorted(int(t) for t in tracks if int(t) not in set(group))
                    rest_eligible = [t for t in rest if t in eligible]
                    if len(rest_eligible) < int(min_rest_tracks):
                        continue

                    group_start = min(_span_start(t) for t in group)
                    rest_start = min(_span_start(t) for t in rest_eligible)
                    # Chỉ tách subgroup xuất hiện muộn hơn anchor/rest. Điều này giúp tránh
                    # tách nhầm các track song song trong cùng một episode.
                    if group_start - rest_start < int(min_start_gap_frames):
                        continue

                    # Cohesion nội bộ của subgroup.
                    pair_bodies = []
                    pair_colors = []
                    for i, a in enumerate(group):
                        for b in group[i + 1:]:
                            ab = self.person_reid_service.compare_tracklets(
                                track_body_reid_samples.get(int(a), []) or [],
                                track_body_reid_samples.get(int(b), []) or [],
                            )
                            pair_bodies.append(float(ab.get("avg_top", 0.0) or 0.0))
                            pair_colors.append(float(ab.get("color_avg_top", 0.0) or 0.0))
                    if not pair_bodies or not pair_colors:
                        continue
                    group_body = float(min(pair_bodies))
                    group_color = float(min(pair_colors))
                    if group_body < float(min_group_body) or group_color < float(min_group_color):
                        continue

                    group_samples = []
                    rest_samples = []
                    for tid in group:
                        group_samples.extend(track_body_reid_samples.get(int(tid), []) or [])
                    for tid in rest_eligible:
                        rest_samples.extend(track_body_reid_samples.get(int(tid), []) or [])
                    if len(group_samples) < int(min_track_samples) * len(group):
                        continue
                    if len(rest_samples) < int(min_track_samples) * int(min_rest_tracks):
                        continue

                    cross = self.person_reid_service.compare_tracklets(rest_samples, group_samples)
                    cross_body = float(cross.get("avg_top", 0.0) or 0.0)
                    cross_best = float(cross.get("best", 0.0) or 0.0)
                    cross_color = float(cross.get("color_avg_top", 0.0) or 0.0)
                    cross_color_best = float(cross.get("color_best", 0.0) or 0.0)

                    # Cần subgroup khác rest rõ ràng. Dùng avg chính vì best có thể cao do
                    # một vài crop nhiễu/ánh sáng giống nhau.
                    if not (cross_body <= float(max_rest_body) or cross_color <= float(max_rest_color)):
                        continue

                    score = (group_body + group_color) - (0.5 * cross_body + 0.5 * cross_color)
                    cand = {
                        "score": score,
                        "profile_id": profile_id,
                        "group": group,
                        "rest": rest,
                        "rest_eligible": rest_eligible,
                        "group_body": group_body,
                        "group_color": group_color,
                        "cross_body": cross_body,
                        "cross_best": cross_best,
                        "cross_color": cross_color,
                        "cross_color_best": cross_color_best,
                        "group_start": group_start,
                        "rest_start": rest_start,
                    }
                    if best_move is None or cand["score"] > best_move["score"]:
                        best_move = cand

        if best_move is None:
            return False

        new_pid = self._move_tracks_to_new_final_profile(
            track_ids=list(best_move["group"]),
            source_profile_id=str(best_move["profile_id"]),
            track_to_profile=track_to_profile,
            track_debug_status=track_debug_status,
            reason="FINAL_COHESIVE_SUBGROUP_SPLIT",
        )
        if not new_pid:
            return False

        for tid in best_move["group"]:
            old_status = track_debug_status.get(int(tid), "")
            track_debug_status[int(tid)] = (
                f"FINAL_COHESIVE_SUBGROUP_SPLIT: Track {tid} "
                f"{best_move['profile_id']} -> {new_pid}, group={best_move['group']}, "
                f"rest={best_move['rest']}, group_body={best_move['group_body']:.3f}, "
                f"group_color={best_move['group_color']:.3f}, cross_body={best_move['cross_body']:.3f}, "
                f"cross_best={best_move['cross_best']:.3f}, cross_color={best_move['cross_color']:.3f}, "
                f"cross_color_best={best_move['cross_color_best']:.3f}; prev_status={old_status}"
            )
        print(
            f"[IDDBG_FINAL_COHESIVE_SUBGROUP_SPLIT] {best_move['profile_id']}->{new_pid} "
            f"group={best_move['group']} rest={best_move['rest']} "
            f"group_body={best_move['group_body']:.3f}, group_color={best_move['group_color']:.3f}, "
            f"cross_body={best_move['cross_body']:.3f}, cross_best={best_move['cross_best']:.3f}, "
            f"cross_color={best_move['cross_color']:.3f}, cross_color_best={best_move['cross_color_best']:.3f}, "
            f"start_gap={best_move['group_start'] - best_move['rest_start']}"
        )
        return True

    def _split_cohesive_peer_visual_outlier_tracks(
        self,
        *,
        track_to_profile: Dict[int, str],
        track_body_reid_samples: Dict[int, List[Dict]],
        track_observation_counts: Dict[int, int],
        track_debug_status: Dict[int, str],
        min_profile_tracks: int,
        min_track_obs: int,
        min_track_samples: int,
        min_peer_tracks: int,
        min_peer_obs: int,
        min_peer_samples: int,
        max_body_avg: float,
        max_body_best: float,
        max_color_avg: float,
        max_color_best: float,
        min_peer_cohesion_body: float,
        min_peer_cohesion_color: float,
    ) -> bool:
        """
        Final-only split hẹp cho profile có một track visual outlier rõ:
        - Profile có ít nhất 3 track.
        - Track cần tách đủ dài và có đủ body samples.
        - Phần peer còn lại phải có ít nhất 2 track dài, đủ samples, và tự chúng khá đồng nhất.
        - Track hiện tại khác peer group theo body/color.

        Mục tiêu: loại các case như track17 bị face kéo vào P001, trong khi
        track1/track10 là cùng cụm áo vàng còn track17 là blue. Không hardcode track id.
        """
        if not track_to_profile or not track_body_reid_samples:
            return False

        profile_to_tracks: Dict[str, List[int]] = {}
        for tid, pid in list(track_to_profile.items()):
            if pid:
                profile_to_tracks.setdefault(pid, []).append(int(tid))

        changed = False
        for profile_id, raw_tracks in sorted(profile_to_tracks.items()):
            tracks = sorted(set(int(t) for t in raw_tracks))
            if len(tracks) < int(min_profile_tracks):
                continue

            for tid in tracks:
                if int(track_observation_counts.get(tid, 0) or 0) < int(min_track_obs):
                    continue
                current_samples = track_body_reid_samples.get(int(tid), []) or []
                if len(current_samples) < int(min_track_samples):
                    continue

                peer_tracks = []
                peer_samples = []
                for other_tid in tracks:
                    other_tid = int(other_tid)
                    if other_tid == int(tid):
                        continue
                    if int(track_observation_counts.get(other_tid, 0) or 0) < int(min_peer_obs):
                        continue
                    samples = track_body_reid_samples.get(other_tid, []) or []
                    if len(samples) < int(min_peer_samples):
                        continue
                    peer_tracks.append(other_tid)
                    peer_samples.extend(samples)

                if len(peer_tracks) < int(min_peer_tracks):
                    continue
                if len(peer_samples) < int(min_peer_tracks) * int(min_peer_samples):
                    continue

                # Peer group phải tự đồng nhất. Nếu peer group vốn đã lẫn nhiều người,
                # không dùng nó làm chuẩn để tách outlier.
                peer_cohesion_ok = True
                for i, a in enumerate(peer_tracks):
                    for b in peer_tracks[i + 1:]:
                        a_samples = track_body_reid_samples.get(int(a), []) or []
                        b_samples = track_body_reid_samples.get(int(b), []) or []
                        if not a_samples or not b_samples:
                            peer_cohesion_ok = False
                            break
                        ab = self.person_reid_service.compare_tracklets(a_samples, b_samples)
                        ab_body = float(ab.get("avg_top", 0.0) or 0.0)
                        ab_color = float(ab.get("color_avg_top", 0.0) or 0.0)
                        if ab_body < float(min_peer_cohesion_body) or ab_color < float(min_peer_cohesion_color):
                            peer_cohesion_ok = False
                            break
                    if not peer_cohesion_ok:
                        break
                if not peer_cohesion_ok:
                    continue

                body_info = self.person_reid_service.compare_tracklets(peer_samples, current_samples)
                avg_top = float(body_info.get("avg_top", 0.0) or 0.0)
                best = float(body_info.get("best", 0.0) or 0.0)
                color_avg = float(body_info.get("color_avg_top", 0.0) or 0.0)
                color_best = float(body_info.get("color_best", 0.0) or 0.0)

                body_outlier = avg_top <= float(max_body_avg) and best <= float(max_body_best)
                color_outlier = color_avg <= float(max_color_avg) and color_best <= float(max_color_best)
                # Cần body hoặc color outlier rõ; ưu tiên case cả hai cùng yếu.
                if not (body_outlier or color_outlier or (avg_top <= float(max_body_avg) and color_avg <= float(max_color_avg))):
                    continue

                new_profile_id = self.online_identity.split_track_to_new_profile(
                    track_id=int(tid),
                    source_profile_id=profile_id,
                )
                if not new_profile_id:
                    continue

                track_to_profile[int(tid)] = new_profile_id
                self.online_identity.track_to_profile[int(tid)] = new_profile_id
                old_status = track_debug_status.get(int(tid), "")
                track_debug_status[int(tid)] = (
                    f"FINAL_COHESIVE_PEER_OUTLIER_SPLIT: Track {tid} "
                    f"{profile_id} -> {new_profile_id}, peers={peer_tracks}, "
                    f"avg_top={avg_top:.3f}, best={best:.3f}, "
                    f"color_avg={color_avg:.3f}, color_best={color_best:.3f}; "
                    f"prev_status={old_status}"
                )
                print(
                    f"[IDDBG_FINAL_COHESIVE_PEER_OUTLIER_SPLIT] track={tid} "
                    f"{profile_id}->{new_profile_id}, peers={peer_tracks}, "
                    f"avg_top={avg_top:.3f}, best={best:.3f}, "
                    f"color_avg={color_avg:.3f}, color_best={color_best:.3f}"
                )
                changed = True
                break
            if changed:
                break
        return changed

    def _apply_camera_ready_profile_refinements(
        self,
        track_to_profile: Dict[int, str],
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
        track_observation_counts: Dict[int, int],
        track_body_reid_samples: Dict[int, List[Dict]],
        track_debug_status: Dict[int, str],
        min_track_obs: int,
        min_track_samples: int,
        min_target_score: float,
        move_margin: float,
        magnet_move_margin: float,
        magnet_profile_tracks: int,
        color_split_min_profile_tracks: int,
        color_split_min_track_obs: int,
        max_passes: int = 2,
        realtime_frame_index: Optional[int] = None,
    ) -> None:
        """
        Camera-ready profile refinement.

        Mục tiêu của bản này:
        - Không hard-code track id.
        - Không sửa riêng ở cuối video; chạy được theo realtime correction tick.
        - Giữ nguyên track_id gốc để vẽ trajectory theo mapping P_id -> track_id[].

        Hai lớp sửa:
        1) Color-family split: nếu profile trộn một track màu đỏ rõ vào nhóm blue/cyan
           hoặc white/light rõ vào nhóm blue/cyan, tách minority ra trước.
           Đây xử lý case kiểu P_0007=[54(red),76(blue),84(blue)].
        2) Better-profile reassignment: sau split, nếu một track hợp với profile khác
           rõ hơn profile hiện tại theo body-tracklet score và không có same-frame conflict,
           chuyển riêng track đó sang profile tốt hơn. Đây xử lý các case như:
           - track84 hợp P_0003 hơn P_0007,
           - track83 hợp cụm chứa track76 hơn profile chứa track4/84,
           - track87 hợp P_0005 hơn profile magnet P_0004.
        """
        if not track_to_profile or not getattr(self, "online_identity", None):
            return
        if not self.online_identity.profiles:
            return

        mode = "REALTIME" if realtime_frame_index is not None else "EXPORT_SAFETY"

        def _track_color_family(tid: int) -> str:
            samples = track_body_reid_samples.get(int(tid), []) or []
            if not samples:
                return "unknown"
            hsvs = []
            fracs = []
            for s in samples:
                hsv = s.get("torso_hsv_mean") or []
                if len(hsv) >= 3:
                    hsvs.append(hsv[:3])
                fracs.append(float(s.get("saturated_fraction", 0.0) or 0.0))
            if not hsvs:
                return "unknown"
            arr = np.array(hsvs, dtype=np.float32)
            hue, sat, val = np.median(arr, axis=0).tolist()
            sat_frac = float(np.median(fracs)) if fracs else 0.0
            name = self._dominant_color_name_from_hsv(float(hue), float(sat), float(val))
            if name in ("red", "orange", "yellow"):
                return "warm_red"
            if name in ("white/light", "gray", "black/dark"):
                return name
            if name in ("blue", "cyan", "purple"):
                return "cool_blue"
            return name or "unknown"

        def _new_profile_for_tracks(source_profile_id: str, tids: List[int], reason: str) -> Optional[str]:
            source_profile = self.online_identity.profiles.get(source_profile_id)
            if not source_profile:
                return None
            new_pid = None
            for idx, tid in enumerate(list(tids)):
                if track_to_profile.get(int(tid)) != source_profile_id:
                    continue
                if idx == 0:
                    new_pid = self.online_identity.split_track_to_new_profile(source_profile_id, int(tid))
                    if not new_pid:
                        continue
                else:
                    ok = self.online_identity.reassign_track_to_profile(int(tid), source_profile_id, new_pid)
                    if not ok:
                        continue
                track_to_profile[int(tid)] = new_pid
                self.online_identity.track_to_profile[int(tid)] = new_pid
                old_status = track_debug_status.get(int(tid), "")
                track_debug_status[int(tid)] = (
                    f"PROFILE_REFINE_SPLIT: Track {tid} {source_profile_id} -> {new_pid}, "
                    f"reason={reason}; prev_status={old_status}"
                )
            return new_pid

        def _score_track_to_profile(tid: int, pid: str, exclude_track: Optional[int] = None) -> Dict:
            cur_samples = track_body_reid_samples.get(int(tid), []) or []
            if len(cur_samples) < min_track_samples:
                return {"score": 0.0, "avg_top": 0.0, "best": 0.0, "color_avg": 0.0, "peers": []}
            peer_tracks = []
            peer_samples = []
            for other_tid, other_pid in track_to_profile.items():
                other_tid = int(other_tid)
                if other_pid != pid or other_tid == int(tid) or (exclude_track is not None and other_tid == int(exclude_track)):
                    continue
                samples = track_body_reid_samples.get(other_tid, []) or []
                if len(samples) < min_track_samples:
                    continue
                peer_tracks.append(other_tid)
                peer_samples.extend(samples)
            if not peer_samples:
                return {"score": 0.0, "avg_top": 0.0, "best": 0.0, "color_avg": 0.0, "peers": []}
            info = self.person_reid_service.compare_tracklets(cur_samples, peer_samples)
            avg_top = float(info.get("avg_top", 0.0))
            best = float(info.get("best", 0.0))
            color_avg = float(info.get("color_avg_top", 0.0))
            # Body is primary; color gets a smaller vote because color is noisy in this camera.
            score = 0.72 * avg_top + 0.18 * best + 0.10 * color_avg
            return {
                "score": float(score),
                "avg_top": avg_top,
                "best": best,
                "color_avg": color_avg,
                "peers": peer_tracks,
            }

        def _move_track(tid: int, source_pid: str, target_pid: str, reason: str, details: str) -> bool:
            if source_pid == target_pid:
                return False
            if source_pid not in self.online_identity.profiles or target_pid not in self.online_identity.profiles:
                return False
            if self._profile_has_same_frame_conflict_with_track(
                target_profile=target_pid,
                current_track=int(tid),
                track_to_profile=track_to_profile,
                track_frame_bboxes=track_frame_bboxes,
            ):
                return False
            ok = self.online_identity.reassign_track_to_profile(int(tid), source_pid, target_pid)
            if not ok:
                return False
            track_to_profile[int(tid)] = target_pid
            self.online_identity.track_to_profile[int(tid)] = target_pid
            old_status = track_debug_status.get(int(tid), "")
            track_debug_status[int(tid)] = (
                f"PROFILE_REFINE_MOVE: Track {tid} {source_pid} -> {target_pid}, "
                f"reason={reason}, {details}; prev_status={old_status}"
            )
            print(
                f"[IDDBG_PROFILE_REFINE_{mode}] frame={realtime_frame_index} "
                f"track={tid} {source_pid}->{target_pid} reason={reason} {details}"
            )
            return True

        # Pass 0: split obvious minority color family out of mixed profiles.
        # This is intentionally conservative: only split warm_red or white/light/black/dark
        # when the profile has a dominant group with >=2 tracks. Blue/cyan/purple are one family.
        for profile_id, profile in list(self.online_identity.profiles.items()):
            tids = sorted(set(int(t) for t in profile.get("track_ids", []) if t is not None))
            if len(tids) < color_split_min_profile_tracks:
                continue
            groups: Dict[str, List[int]] = {}
            for tid in tids:
                if int(track_observation_counts.get(tid, 0)) < color_split_min_track_obs:
                    continue
                fam = _track_color_family(tid)
                if fam == "unknown":
                    continue
                groups.setdefault(fam, []).append(tid)
            if len(groups) < 2:
                continue
            dominant_family, dominant_tracks = max(groups.items(), key=lambda kv: len(kv[1]))
            if len(dominant_tracks) < 2:
                continue
            for fam, fam_tracks in list(groups.items()):
                if fam == dominant_family:
                    continue
                # red is highly reliable as an outlier. white/light is reliable when isolated.
                incompatible = (
                    (fam == "warm_red" and dominant_family != "warm_red")
                    or (dominant_family == "warm_red" and fam != "warm_red")
                    or (fam in ("white/light", "black/dark") and dominant_family == "cool_blue" and len(fam_tracks) == 1)
                )
                if not incompatible:
                    continue
                new_pid = _new_profile_for_tracks(
                    source_profile_id=profile_id,
                    tids=fam_tracks,
                    reason=f"color_family_outlier {fam} vs dominant {dominant_family}",
                )
                if new_pid:
                    print(
                        f"[IDDBG_COLOR_FAMILY_SPLIT_{mode}] frame={realtime_frame_index} "
                        f"{profile_id}->{new_pid} moved_tracks={fam_tracks} "
                        f"family={fam} dominant={dominant_family}"
                    )
                # One split per original profile per tick is safer for realtime display.
                break

        # Pass 1..N: move tracks to the profile whose body tracklet support is clearly better.
        for _ in range(max(1, int(max_passes))):
            changed = False
            all_tracks = sorted(int(t) for t in list(track_to_profile.keys()))
            for tid in all_tracks:
                source_pid = track_to_profile.get(tid)
                if not source_pid or source_pid not in self.online_identity.profiles:
                    continue
                if int(track_observation_counts.get(tid, 0)) < min_track_obs:
                    continue
                if len(track_body_reid_samples.get(tid, []) or []) < min_track_samples:
                    continue

                source_tracks = self.online_identity.profiles.get(source_pid, {}).get("track_ids", []) or []
                current_info = _score_track_to_profile(tid, source_pid, exclude_track=tid)
                current_score = float(current_info.get("score", 0.0))

                best_pid = None
                best_info = None
                best_score = 0.0
                for candidate_pid, candidate_profile in list(self.online_identity.profiles.items()):
                    if candidate_pid == source_pid:
                        continue
                    candidate_tracks = candidate_profile.get("track_ids", []) or []
                    if not candidate_tracks:
                        continue
                    if self._profile_has_same_frame_conflict_with_track(
                        target_profile=candidate_pid,
                        current_track=tid,
                        track_to_profile=track_to_profile,
                        track_frame_bboxes=track_frame_bboxes,
                    ):
                        continue
                    info = _score_track_to_profile(tid, candidate_pid, exclude_track=None)
                    score = float(info.get("score", 0.0))
                    if score > best_score:
                        best_score = score
                        best_pid = candidate_pid
                        best_info = info

                if best_pid is None or best_info is None:
                    continue

                source_is_magnet = len(source_tracks) >= magnet_profile_tracks
                required_margin = magnet_move_margin if source_is_magnet else move_margin

                # If source support is weak/empty because the source profile is a wrong singleton/mixed fragment,
                # require a strong absolute target score. Otherwise require margin over current support.
                enough_absolute = best_score >= min_target_score
                enough_margin = (best_score - current_score) >= required_margin
                if not (enough_absolute and enough_margin):
                    continue

                details = (
                    f"target_score={best_score:.3f}, current_score={current_score:.3f}, "
                    f"margin={best_score-current_score:.3f}, target_avg={best_info.get('avg_top',0):.3f}, "
                    f"target_best={best_info.get('best',0):.3f}, target_color={best_info.get('color_avg',0):.3f}, "
                    f"target_peers={best_info.get('peers', [])}, current_peers={current_info.get('peers', [])}"
                )
                if _move_track(tid, source_pid, best_pid, "better_body_profile", details):
                    changed = True
                    break
            if not changed:
                break

    def _split_stale_profile_episodes(
        self,
        track_to_profile: Dict[int, str],
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
        track_observation_counts: Dict[int, int],
        track_debug_status: Dict[int, str],
        stale_gap_frames: int,
        min_profile_tracks: int,
        min_tail_tracks: int,
        min_tail_total_obs: int,
        min_each_tail_obs: int,
        realtime_frame_index: Optional[int] = None,
    ) -> None:
        """
        Split a late temporal episode out of an over-large profile.

        Why this exists:
        - In the provided log, track76 and track83 look like the same person to the eye.
        - The system should NOT force track83 back to P0005 just because it was once there.
        - But profile P0001 became too broad: [1,14,31,59,63,76,83].
        - Body/color histogram was not enough because many crops become blue/cyan.

        Generic rule:
        - only consider large profiles,
        - sort their concrete tracklets by time,
        - when there is a long stale gap,
        - if the tail after that gap contains multiple stable tracklets,
          move that tail to a fresh P_id.

        This is a sub-profile split, not a merge and not a hard-coded track-id rule.
        """
        if not track_to_profile or not getattr(self, "online_identity", None):
            return

        profiles = self.online_identity.profiles
        if not profiles:
            return

        def _new_profile_id() -> str:
            if isinstance(self.online_identity.next_profile_index, tuple):
                self.online_identity.next_profile_index = self.online_identity.next_profile_index[0]
            pid = f"P_{self.online_identity.next_profile_index:04d}"
            self.online_identity.next_profile_index += 1
            return pid

        def _span(tid: int):
            return self._track_span(track_frame_bboxes, tid)

        # Iterate over a snapshot because we may modify profiles.
        for profile_id, profile in list(profiles.items()):
            track_ids = sorted(set(int(t) for t in profile.get("track_ids", []) if t is not None))
            if len(track_ids) < min_profile_tracks:
                continue

            spans = []
            for tid in track_ids:
                sp = _span(tid)
                if sp is None:
                    continue
                spans.append((int(sp[0]), int(sp[1]), tid))
            if len(spans) < min_profile_tracks:
                continue
            spans.sort(key=lambda x: (x[0], x[1], x[2]))

            # Find the last meaningful stale break. Using the last break keeps
            # old continuous fragments together and extracts the late branch.
            split_index = None
            for i in range(1, len(spans)):
                prev_end = max(s[1] for s in spans[:i])
                cur_start = spans[i][0]
                gap = cur_start - prev_end
                if gap >= stale_gap_frames:
                    split_index = i

            if split_index is None:
                continue

            head = spans[:split_index]
            tail = spans[split_index:]
            tail_tracks = [tid for _, _, tid in tail]
            head_tracks = [tid for _, _, tid in head]

            if len(tail_tracks) < min_tail_tracks:
                continue
            tail_total_obs = sum(int(track_observation_counts.get(t, 0)) for t in tail_tracks)
            if tail_total_obs < min_tail_total_obs:
                continue
            stable_tail_tracks = [
                t for t in tail_tracks
                if int(track_observation_counts.get(t, 0)) >= min_each_tail_obs
            ]
            if len(stable_tail_tracks) < min_tail_tracks:
                continue

            # Avoid destructive split if the head itself is tiny/noisy.
            head_total_obs = sum(int(track_observation_counts.get(t, 0)) for t in head_tracks)
            if head_total_obs < min_tail_total_obs:
                continue

            source_samples = profile.setdefault("track_samples", {})
            moving_samples = {}
            for tid in tail_tracks:
                key = str(tid)
                sample = source_samples.pop(key, None)
                if sample is not None:
                    moving_samples[key] = sample

            if len(moving_samples) < min_tail_tracks:
                # Restore if not enough actual samples were movable.
                source_samples.update(moving_samples)
                continue

            new_profile_id = _new_profile_id()
            new_profile = {
                "profile_id": new_profile_id,
                "track_samples": moving_samples,
            }
            profiles[new_profile_id] = new_profile

            # Rebuild both source and new profile from concrete track samples.
            self.online_identity._rebuild_profile_from_track_samples(profile)
            self.online_identity._rebuild_profile_from_track_samples(new_profile)

            for tid in tail_tracks:
                track_to_profile[tid] = new_profile_id
                self.online_identity.track_to_profile[int(tid)] = new_profile_id
                old_status = track_debug_status.get(tid, "")
                track_debug_status[tid] = (
                    f"EPISODE_SPLIT: Track {tid} {profile_id} -> {new_profile_id}, "
                    f"stale_gap_frames>={stale_gap_frames}, tail_tracks={tail_tracks}; "
                    f"prev_status={old_status}"
                )

            mode = "REALTIME" if realtime_frame_index is not None else "EXPORT_SAFETY"
            print(
                f"[IDDBG_EPISODE_SPLIT_{mode}] frame={realtime_frame_index} "
                f"{profile_id} -> {new_profile_id} | "
                f"moved_tail_tracks={tail_tracks} | kept_head_tracks={head_tracks} | "
                f"tail_total_obs={tail_total_obs} | stale_gap_frames={stale_gap_frames}"
            )

            # Remove empty profile if all tracks moved, though normally head remains.
            if not profile.get("track_ids"):
                profiles.pop(profile_id, None)

    def _apply_body_tracklet_reid_corrections(
        self,
        track_to_profile: Dict[int, str],
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
        track_observation_counts: Dict[int, int],
        track_body_reid_samples: Dict[int, List[Dict]],
        track_debug_status: Dict[int, str],
        max_gap_frames: int,
        min_old_obs: int,
        min_new_obs: int,
        min_avg_top: float,
        min_best: float,
        min_combined: float,
        margin: float,
        center_norm_limit: float,
        allow_overlap_frames: int,
    ) -> None:
        """
        Tracklet-level body ReID correction.

        This is the new direction: do not rely on a single face embedding when
        a standing customer changes face angle. Instead, after tracklets have
        enough samples, move only the wrong track to the profile of a concrete
        previous tracklet if body ReID + temporal continuity are stronger.

        It is not a region anchor. It compares current_track to old_track ids.
        """
        if not track_to_profile or not track_body_reid_samples:
            return

        moved_any = True
        pass_index = 0
        while moved_any and pass_index < 2:
            moved_any = False
            pass_index += 1

            assigned_tracks = sorted(int(t) for t in track_to_profile.keys())

            for current_track in assigned_tracks:
                current_profile = track_to_profile.get(current_track)
                if not current_profile:
                    continue
                if track_observation_counts.get(current_track, 0) < min_new_obs:
                    continue
                if current_track not in track_body_reid_samples:
                    continue

                current_span = self._track_span(track_frame_bboxes, current_track)
                if current_span is None:
                    continue
                current_start, current_end = current_span

                # Evaluate every other profile by its best concrete old_track.
                best_candidate = None
                current_profile_score = 0.0

                profiles = sorted(set(pid for pid in track_to_profile.values() if pid))
                for candidate_profile in profiles:
                    if candidate_profile == current_profile:
                        score_info = self._best_body_tracklet_link_to_profile(
                            current_track=current_track,
                            candidate_profile=candidate_profile,
                            track_to_profile=track_to_profile,
                            track_frame_bboxes=track_frame_bboxes,
                            track_observation_counts=track_observation_counts,
                            track_body_reid_samples=track_body_reid_samples,
                            max_gap_frames=max_gap_frames,
                            min_old_obs=min_old_obs,
                            center_norm_limit=center_norm_limit,
                            allow_overlap_frames=allow_overlap_frames,
                        )
                        current_profile_score = max(current_profile_score, score_info.get("combined", 0.0))
                        continue

                    if self._profile_has_same_frame_conflict_with_track(
                        target_profile=candidate_profile,
                        current_track=current_track,
                        track_to_profile=track_to_profile,
                        track_frame_bboxes=track_frame_bboxes,
                    ):
                        continue

                    score_info = self._best_body_tracklet_link_to_profile(
                        current_track=current_track,
                        candidate_profile=candidate_profile,
                        track_to_profile=track_to_profile,
                        track_frame_bboxes=track_frame_bboxes,
                        track_observation_counts=track_observation_counts,
                        track_body_reid_samples=track_body_reid_samples,
                        max_gap_frames=max_gap_frames,
                        min_old_obs=min_old_obs,
                        center_norm_limit=center_norm_limit,
                        allow_overlap_frames=allow_overlap_frames,
                    )

                    if score_info.get("old_track") is None:
                        continue
                    if score_info.get("avg_top", 0.0) < min_avg_top and score_info.get("best", 0.0) < min_best:
                        continue
                    if score_info.get("combined", 0.0) < min_combined:
                        continue

                    if best_candidate is None or score_info["combined"] > best_candidate["combined"]:
                        best_candidate = {
                            **score_info,
                            "target_profile": candidate_profile,
                        }

                if best_candidate is None:
                    continue

                target_profile = best_candidate["target_profile"]
                target_score = float(best_candidate.get("combined", 0.0))

                # Do not switch if the current profile has equally good concrete tracklet support.
                if target_score < current_profile_score + margin:
                    continue

                old_profile = current_profile
                moved = self.online_identity.reassign_track_to_profile(
                    track_id=current_track,
                    source_profile_id=old_profile,
                    target_profile_id=target_profile,
                )
                if not moved:
                    continue

                track_to_profile[current_track] = target_profile
                moved_any = True
                track_debug_status[current_track] = (
                    f"BODY_TRACKLET_REID_CORRECTED: Track {current_track} "
                    f"{old_profile} -> {target_profile}, "
                    f"from_old_track={best_candidate.get('old_track')}, "
                    f"combined={target_score:.3f}, avg_top={best_candidate.get('avg_top', 0.0):.3f}, "
                    f"best={best_candidate.get('best', 0.0):.3f}, spatial={best_candidate.get('spatial', 0.0):.3f}, "
                    f"gap={best_candidate.get('gap')}"
                )
                print(
                    f"[BodyTrackletReIDCorrected] Track {current_track}: "
                    f"{old_profile} -> {target_profile} | "
                    f"old_track={best_candidate.get('old_track')} | "
                    f"combined={target_score:.3f}, current_support={current_profile_score:.3f}, "
                    f"avg_top={best_candidate.get('avg_top', 0.0):.3f}, "
                    f"best={best_candidate.get('best', 0.0):.3f}, "
                    f"spatial={best_candidate.get('spatial', 0.0):.3f}, "
                    f"gap={best_candidate.get('gap')}"
                )

    def _best_body_tracklet_link_to_profile(
        self,
        current_track: int,
        candidate_profile: str,
        track_to_profile: Dict[int, str],
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
        track_observation_counts: Dict[int, int],
        track_body_reid_samples: Dict[int, List[Dict]],
        max_gap_frames: int,
        min_old_obs: int,
        center_norm_limit: float,
        allow_overlap_frames: int,
    ) -> Dict:
        current_span = self._track_span(track_frame_bboxes, current_track)
        if current_span is None:
            return {"combined": 0.0, "old_track": None}
        current_start, _ = current_span
        current_first_bbox = self._track_bbox_at(track_frame_bboxes, current_track, current_start)
        current_samples = track_body_reid_samples.get(current_track, [])
        if current_first_bbox is None or not current_samples:
            return {"combined": 0.0, "old_track": None}

        best = {"combined": 0.0, "old_track": None}
        for old_track, profile_id in track_to_profile.items():
            old_track = int(old_track)
            if old_track == current_track or profile_id != candidate_profile:
                continue
            if track_observation_counts.get(old_track, 0) < min_old_obs:
                continue
            old_span = self._track_span(track_frame_bboxes, old_track)
            if old_span is None:
                continue
            _, old_end = old_span
            gap = int(current_start - old_end)
            if gap < -allow_overlap_frames or gap > max_gap_frames:
                continue

            old_last_bbox = self._track_bbox_at(track_frame_bboxes, old_track, old_end)
            if old_last_bbox is None:
                continue

            center_norm = self._bbox_center_distance_norm(current_first_bbox, old_last_bbox)
            if center_norm > center_norm_limit:
                continue

            iou = self._bbox_iou(current_first_bbox, old_last_bbox)
            containment = self._bbox_containment(current_first_bbox, old_last_bbox)
            area_ratio = self._bbox_area_ratio(current_first_bbox, old_last_bbox)
            if not (0.25 <= area_ratio <= 4.0):
                continue

            body_info = self.person_reid_service.compare_tracklets(
                track_body_reid_samples.get(old_track, []),
                current_samples,
            )
            avg_top = float(body_info.get("avg_top", 0.0))
            best_body = float(body_info.get("best", 0.0))

            # Spatial score is continuity score, not region anchor.
            center_score = max(0.0, 1.0 - (center_norm / max(1e-6, center_norm_limit)))
            spatial = max(float(iou), float(containment), center_score * 0.85)
            temporal = max(0.0, 1.0 - (max(0, gap) / max(1, max_gap_frames)))
            combined = 0.50 * avg_top + 0.18 * best_body + 0.25 * spatial + 0.07 * temporal

            candidate = {
                "combined": float(combined),
                "old_track": old_track,
                "gap": gap,
                "avg_top": avg_top,
                "best": best_body,
                "spatial": float(spatial),
                "center_norm": float(center_norm),
                "iou": float(iou),
                "containment": float(containment),
                "area_ratio": float(area_ratio),
            }
            if candidate["combined"] > best["combined"]:
                best = candidate
        return best


    def _final_move_late_track_to_short_gap_return_profile(
        self,
        *,
        track_to_profile: Dict[int, str],
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
        track_observation_counts: Dict[int, int],
        track_body_reid_samples: Dict[int, List[Dict]],
        track_debug_status: Dict[int, str],
        min_track_obs: int = 80,
        max_candidate_gap_frames: int = 90,
        min_current_profile_gap_frames: int = 180,
        min_candidate_app: float = 0.72,
        min_candidate_body_best: float = 0.74,
        max_overlap_frames: int = 0,
    ) -> bool:
        """
        Final-only repair cho case track quay lại bị gán nhầm vào profile xa.
        Ví dụ generic: track late T nằm trong profile A, nhưng A chỉ có các track kết thúc rất lâu
        trước T; trong khi profile B có track kết thúc ngay trước T với body/app hợp lý.

        Không hardcode P/track. Chỉ chuyển nếu:
        - track late đủ dài;
        - gap với profile hiện tại xa;
        - có một profile khác kết thúc gần trước track đó;
        - body/app với profile gần đủ tốt và không overlap thật sự.
        """
        if not track_to_profile or not track_frame_bboxes or not track_body_reid_samples:
            return False

        profile_to_tracks: Dict[str, List[int]] = {}
        for tid, pid in list(track_to_profile.items()):
            if pid:
                profile_to_tracks.setdefault(pid, []).append(int(tid))

        changed = False
        for tid, current_pid in sorted(list(track_to_profile.items())):
            tid = int(tid)
            if not current_pid:
                continue
            if int(track_observation_counts.get(tid, 0) or 0) < int(min_track_obs):
                continue
            span = self._track_span(track_frame_bboxes, tid)
            if span is None:
                continue
            start, end = int(span[0]), int(span[1])
            current_samples = track_body_reid_samples.get(tid, []) or []
            if len(current_samples) < 6:
                continue

            # Gap tới các peer trong profile hiện tại trước khi track này bắt đầu.
            current_prev_gaps = []
            for peer in profile_to_tracks.get(current_pid, []):
                peer = int(peer)
                if peer == tid:
                    continue
                ps = self._track_span(track_frame_bboxes, peer)
                if ps is None:
                    continue
                p_start, p_end = int(ps[0]), int(ps[1])
                if p_end <= start:
                    current_prev_gaps.append(start - p_end)
                elif p_start <= end and p_end >= start:
                    # Same-profile overlap with another real track: không sửa ở rule này.
                    return False
            if not current_prev_gaps:
                continue
            current_gap = min(current_prev_gaps)
            if current_gap < int(min_current_profile_gap_frames):
                continue

            best = None
            for candidate_pid, peers in profile_to_tracks.items():
                if candidate_pid == current_pid:
                    continue
                candidate_samples = []
                candidate_best_gap = None
                candidate_peer = None
                for peer in peers:
                    peer = int(peer)
                    ps = self._track_span(track_frame_bboxes, peer)
                    if ps is None:
                        continue
                    p_start, p_end = int(ps[0]), int(ps[1])
                    gap = start - p_end
                    if gap < -int(max_overlap_frames) or gap > int(max_candidate_gap_frames):
                        continue
                    if int(track_observation_counts.get(peer, 0) or 0) < 5:
                        continue
                    samples = track_body_reid_samples.get(peer, []) or []
                    if not samples:
                        continue
                    candidate_samples.extend(samples)
                    if candidate_best_gap is None or abs(gap) < abs(candidate_best_gap):
                        candidate_best_gap = gap
                        candidate_peer = peer
                if len(candidate_samples) < 3:
                    continue
                body_info = self.person_reid_service.compare_tracklets(candidate_samples, current_samples)
                avg_top = float(body_info.get("avg_top", 0.0) or 0.0)
                best_body = float(body_info.get("best", 0.0) or 0.0)
                color_avg = float(body_info.get("color_avg_top", 0.0) or 0.0)
                color_best = float(body_info.get("color_best", 0.0) or 0.0)
                app_score = max(avg_top, 0.60 * avg_top + 0.25 * best_body + 0.15 * color_avg)
                if app_score < float(min_candidate_app) and best_body < float(min_candidate_body_best):
                    continue
                # Ưu tiên gap ngắn + app tốt.
                gap_score = max(0.0, 1.0 - (max(0, candidate_best_gap or 0) / max(1, max_candidate_gap_frames)))
                score = 0.72 * app_score + 0.18 * best_body + 0.10 * gap_score
                cand = {
                    "profile_id": candidate_pid,
                    "peer": candidate_peer,
                    "gap": candidate_best_gap,
                    "score": score,
                    "avg_top": avg_top,
                    "best": best_body,
                    "color_avg": color_avg,
                    "color_best": color_best,
                    "app_score": app_score,
                }
                if best is None or cand["score"] > best["score"]:
                    best = cand

            if best is None:
                continue
            old_status = track_debug_status.get(tid, "")
            ok = self.online_identity.reassign_track_to_profile(
                track_id=tid,
                source_profile_id=current_pid,
                target_profile_id=best["profile_id"],
            )
            if not ok:
                continue
            track_to_profile[tid] = best["profile_id"]
            self.online_identity.track_to_profile[tid] = best["profile_id"]
            track_debug_status[tid] = (
                f"FINAL_SHORT_GAP_RETURN_REPAIR: Track {tid} {current_pid} -> {best['profile_id']}, "
                f"current_gap={current_gap}, candidate_gap={best['gap']}, candidate_peer={best['peer']}, "
                f"score={best['score']:.3f}, app={best['app_score']:.3f}, body_avg={best['avg_top']:.3f}, "
                f"body_best={best['best']:.3f}, color_avg={best['color_avg']:.3f}; prev_status={old_status}"
            )
            print(
                f"[IDDBG_FINAL_SHORT_GAP_RETURN_REPAIR] track={tid} {current_pid}->{best['profile_id']} "
                f"current_gap={current_gap}, candidate_gap={best['gap']}, candidate_peer={best['peer']}, "
                f"score={best['score']:.3f}, app={best['app_score']:.3f}, "
                f"body_avg={best['avg_top']:.3f}, body_best={best['best']:.3f}, color_avg={best['color_avg']:.3f}"
            )
            changed = True

        return changed

    def _profile_has_same_frame_conflict_with_track(
        self,
        target_profile: str,
        current_track: int,
        track_to_profile: Dict[int, str],
        track_frame_bboxes: Dict[int, Dict[int, List[float]]],
    ) -> bool:
        current_bboxes = track_frame_bboxes.get(current_track, {}) or {}
        current_frames = set(int(f) for f in current_bboxes.keys())
        if not current_frames:
            return True

        for other_track, profile_id in track_to_profile.items():
            other_track = int(other_track)
            if other_track == current_track or profile_id != target_profile:
                continue
            other_bboxes = track_frame_bboxes.get(other_track, {}) or {}
            overlap = current_frames.intersection(set(int(f) for f in other_bboxes.keys()))
            for frame_idx in overlap:
                box_a = current_bboxes.get(frame_idx) or current_bboxes.get(str(frame_idx))
                box_b = other_bboxes.get(frame_idx) or other_bboxes.get(str(frame_idx))
                if box_a is None or box_b is None:
                    continue
                if not self._is_duplicate_like_bbox_pair(box_a, box_b):
                    return True
        return False

    def _lock_profile_in_frame(
        self,
        frame_profile_locks: Dict[int, Dict[str, Dict]],
        frame_index: int,
        profile_id: str,
        track_id: int,
        bbox: List[float],
    ) -> None:
        frame_profile_locks.setdefault(frame_index, {})
        frame_profile_locks[frame_index][profile_id] = {
            "track_id": track_id,
            "bbox": bbox,
        }

