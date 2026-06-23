import os
import cv2
import shutil
from typing import List, Dict, Optional
from dataclasses import dataclass

import numpy as np

# Import các service AI lõi
from app.services.ai.frame_extractor_service import FrameExtractorService
from app.services.ai.tracking_service import tracker_service  # AI-09 (Tracking)
from app.services.ai.face_detection_service import FaceDetectionService, PersonDetectionInput  # AI-03
from app.services.ai.face_embedding_service import FaceEmbeddingService, FaceEmbeddingResult  # AI-04
from app.services.ai.face_matching_service import face_matcher
from app.services.ai.online_identity_service import OnlineIdentityService
from app.services.ai.appearance_signature_service import AppearanceSignatureService  # AI-05 (Face Matching)

@dataclass
class ProcessedCustomer:
    track_id: int
    observation_count: int
    best_face_image_path: Optional[str]
    embedding: Optional[List[float]]
    face_confidence: Optional[float]
    observed_frame_indices: List[int]


class VideoProcessingPipelineService:
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
            )

            self.appearance_service = AppearanceSignatureService()  

        def _is_valid_person_crop_for_identity(self, frame, bbox) -> bool:
            """
            Chặn crop người quá xấu trước khi tạo/match identity.

            Mục tiêu:
            - Tránh case mới thấy chân/thân mà đã tạo profile.
            - Tránh làm bẩn appearance profile.
            """

            if frame is None or bbox is None:
                return False

            h, w = frame.shape[:2]
            x1, y1, x2, y2 = [int(v) for v in bbox]

            x1 = max(0, min(x1, w - 1))
            x2 = max(0, min(x2, w))
            y1 = max(0, min(y1, h - 1))
            y2 = max(0, min(y2, h))

            box_w = max(0, x2 - x1)
            box_h = max(0, y2 - y1)

            if box_w < 40 or box_h < 100:
                return False

            ratio = box_h / (box_w + 1e-6)

            # Người đứng bình thường thường cao hơn rộng.
            if ratio < 1.2 or ratio > 5.0:
                return False

            # Nếu bbox nằm rất thấp, dễ là chỉ thấy chân/thân dưới.
            bottom_touch = y2 >= h - 5
            top_is_low = y1 > h * 0.65

            if bottom_touch and top_is_low:
                return False

            return True

        def process_video(
            self,
            video_path: str,
            output_face_dir: str = "./pipeline_faces",
            target_fps: float = 1.0,
            debug_video_path: str = None,
        ) -> Dict:

            if os.path.exists(output_face_dir):
                shutil.rmtree(output_face_dir)

            os.makedirs(output_face_dir, exist_ok=True)

            print("\n" + "=" * 60)
            print("KHỞI ĐỘNG ONLINE AI PIPELINE + SAFE APPEARANCE MATCHING")
            print("=" * 60)

            # Reset gallery mỗi lần xử lý video mới
            self.online_identity.reset()

            # ============================================================
            # CONFIG
            # ============================================================
            SAMPLE_EVERY_N_OBS = 3

            MIN_FACE_CONFIDENCE_FOR_MATCH = 0.55
            MIN_FACE_CONFIDENCE_FOR_NEW_PROFILE = 0.78
            MIN_FRAMES_OBSERVED = 3

            # Strict face match cũng không được auto-match nếu app/margin yếu
            MATCH_MARGIN_STRONG = 0.07
            MATCH_MARGIN_WEAK = 0.04

            STRICT_FACE_MIN_APP = 0.68
            STRICT_FACE_MIN_CONF = 0.72
            MIN_OBS_FOR_STRICT_MATCH = 3

            SOFT_APP_THRESHOLD = 0.74

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

            STABLE_TRACK_MIN_OBS_FOR_NEW_PROFILE = 30
            STABLE_TRACK_MIN_BEST_FACE_CONF = 0.70

            # ============================================================
            # RUNTIME STATE
            # ============================================================
            track_observation_counts = {}
            track_frame_indices = {}
            track_frame_bboxes = {}
            track_best_face = {}
            track_best_embedding = {}
            track_best_appearance = {}
            track_debug_status = {}

            track_to_profile = {}
            track_best_identity_sample = {}

            debug_person_records = []
            debug_face_records = []

            print("[AI-01] Đang trích xuất frames từ video...")

            with self.frame_extractor.create_temp_frame_dir() as frame_dir:
                frame_result = self.frame_extractor.extract_frames(
                    video_path,
                    frame_dir,
                    target_fps=target_fps,
                )

                print(f"[AI-02/09] Đang tracking trên {frame_result.extracted_count} frames...")

                for frame_data in frame_result.frames:
                    image = cv2.imread(frame_data.image_path)

                    if image is None:
                        continue

                    tracked_persons = self.tracker.track_persons_in_frame(
                        frame=image,
                        frame_index=frame_data.frame_index,
                        img_path=frame_data.image_path,
                    )

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
                        })

                        already_assigned = track_id in track_to_profile

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

                        if not valid_body_for_identity and not already_assigned and not stable_track_with_good_face:
                            track_debug_status[track_id] = (
                                "PENDING: invalid body crop, wait better frame"
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

                            self.online_identity.update_profile(
                                profile_id=profile_id,
                                track_id=track_id,
                                embedding=embedding,
                                face_image_path=face.face_image_path,
                                face_confidence=face_conf,
                                frame_index=frame_data.frame_index,
                                observation_count=1,
                                observed_frame_indices=current_track_frames,
                                appearance_signature=appearance_signature if valid_body_for_identity else None,
                                bbox=bbox,
                            )

                            track_debug_status[track_id] = (
                                f"UPDATED: Track {track_id} -> {profile_id}"
                            )
                            continue

                        # ====================================================
                        # CASE 2: TRACK MỚI, TÌM PROFILE PHÙ HỢP
                        # ====================================================
                        (
                            best_profile_id,
                            best_total_score,
                            best_face_score,
                            best_app_score,
                            best_margin,
                        ) = self.online_identity.find_best_profile(
                            embedding=embedding,
                            appearance_signature=appearance_signature,
                            current_frame_index=frame_data.frame_index,
                            current_track_frames=current_track_frames,
                            current_track_frame_bboxes=current_track_frame_bboxes,
                            appearance_service=self.appearance_service,
                        )

                        should_assign_existing = False

                        if best_profile_id is not None:
                            # A. Face mạnh nhưng vẫn cần app/margin/obs/conf phụ trợ.
                            if best_face_score >= self.online_identity.strict_threshold:
                                if (
                                    obs_count >= MIN_OBS_FOR_STRICT_MATCH
                                    and face_conf >= STRICT_FACE_MIN_CONF
                                    and (
                                        best_app_score >= STRICT_FACE_MIN_APP
                                        or best_margin >= MATCH_MARGIN_STRONG
                                        or best_face_score >= 0.52
                                    )
                                ):
                                    should_assign_existing = True

                            # B. Face lưng chừng, bắt buộc appearance khá tốt.
                            elif best_face_score >= self.online_identity.soft_threshold:
                                if (
                                    best_app_score >= SOFT_APP_THRESHOLD
                                    and best_margin >= MATCH_MARGIN_WEAK
                                    and face_conf >= 0.68
                                    and obs_count >= MIN_FRAMES_OBSERVED
                                ):
                                    should_assign_existing = True

                            # C. Face yếu, chỉ match nếu appearance rất mạnh.
                            elif best_face_score >= self.online_identity.weak_track_threshold:
                                # Case C1: track ngắn, face yếu nhưng appearance mạnh
                                if (
                                    best_total_score >= WEAK_TOTAL_THRESHOLD
                                    and best_face_score >= WEAK_FACE_MIN_THRESHOLD
                                    and best_app_score >= WEAK_APP_THRESHOLD
                                    and best_margin >= MATCH_MARGIN_WEAK
                                    and face_conf >= 0.70
                                    and obs_count <= WEAK_TRACK_MAX_OBS
                                ):
                                    should_assign_existing = True

                                # Case C2: track hơi dài hơn nhưng appearance CỰC mạnh
                                # Dành cho case như P_0004 + P_0005:
                                # face=0.336, app=0.924, total=0.424, margin=0.074, obs=21.
                                elif (
                                    best_total_score >= STRONG_APP_TOTAL_THRESHOLD
                                    and best_face_score >= STRONG_APP_FACE_MIN_THRESHOLD
                                    and best_app_score >= STRONG_APP_THRESHOLD
                                    and best_margin >= MATCH_MARGIN_WEAK
                                    and face_conf >= 0.75
                                    and obs_count <= STRONG_APP_LONG_TRACK_MAX_OBS
                                ):
                                    should_assign_existing = True

                        if should_assign_existing and best_profile_id is not None:
                            profile_id = best_profile_id
                            track_to_profile[track_id] = profile_id

                            self.online_identity.update_profile(
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
                                match_score=best_total_score,
                            )

                            track_debug_status[track_id] = (
                                f"MATCHED: Track {track_id} -> {profile_id}, "
                                f"total={best_total_score:.3f}, "
                                f"face={best_face_score:.3f}, "
                                f"app={best_app_score:.3f}, "
                                f"margin={best_margin:.3f}, "
                                f"conf={face_conf:.2f}, "
                                f"obs={obs_count}"
                            )

                            print(
                                f"[OnlineID] Track {track_id} -> existing {profile_id}, "
                                f"total={best_total_score:.3f}, "
                                f"face={best_face_score:.3f}, "
                                f"app={best_app_score:.3f}, "
                                f"margin={best_margin:.3f}, "
                                f"conf={face_conf:.2f}, "
                                f"obs={obs_count}"
                            )

                            continue

                        # ====================================================
                        # CASE 3: KHÔNG MATCH.
                        # Chỉ tạo profile mới nếu không quá gần profile cũ
                        # hoặc đã pending đủ lâu.
                        # ====================================================
                        near_existing_profile = (
                            best_profile_id is not None
                            and best_total_score >= 0.38
                        )

                        best_sample = track_best_identity_sample.get(track_id)

                        has_stable_best_sample = (
                            best_sample is not None
                            and obs_count >= STABLE_TRACK_MIN_OBS_FOR_NEW_PROFILE
                            and best_sample["face_confidence"] >= STABLE_TRACK_MIN_BEST_FACE_CONF
                        )

                        can_create_new_profile_now = (
                            face_conf >= MIN_FACE_CONFIDENCE_FOR_NEW_PROFILE
                            and valid_body_for_identity
                            and (
                                not near_existing_profile
                                or obs_count >= MAX_PENDING_OBS_BEFORE_NEW_PROFILE
                            )
                        )

                        can_create_from_best_sample = (
                            has_stable_best_sample
                            and not near_existing_profile
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

                            track_debug_status[track_id] = (
                                f"NEW: Track {track_id} -> {profile_id}, "
                                f"from_best_sample={can_create_from_best_sample}, "
                                f"total={best_total_score:.3f}, "
                                f"face={best_face_score:.3f}, "
                                f"app={best_app_score:.3f}, "
                                f"margin={best_margin:.3f}, "
                                f"current_conf={face_conf:.2f}, "
                                f"best_conf={sample['face_confidence']:.2f}, "
                                f"obs={obs_count}"
                            )

                            print(
                                f"[OnlineID] Track {track_id} -> new {profile_id}, "
                                f"from_best_sample={can_create_from_best_sample}, "
                                f"total={best_total_score:.3f}, "
                                f"face={best_face_score:.3f}, "
                                f"app={best_app_score:.3f}, "
                                f"margin={best_margin:.3f}, "
                                f"current_conf={face_conf:.2f}, "
                                f"best_conf={sample['face_confidence']:.2f}, "
                                f"obs={obs_count}"
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
                                f"current_conf={face_conf:.2f}, "
                                f"best_conf={best_conf:.2f}, "
                                f"obs={obs_count}"
                            )
                # ============================================================
                # EXPORT PROFILES
                # ============================================================
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

                online_profiles = self.online_identity.export_profiles()

                merged_profiles = []

                for profile in online_profiles:
                    profile_embeddings = profile.get("embeddings", [])

                    merged_profiles.append({
                        "profile_id": profile["profile_id"],
                        "merged_track_ids": sorted(list(set(profile.get("track_ids", [])))),
                        "total_observations": profile.get("total_observations", 0),
                        "best_face_image_path": profile.get("best_face_image_path"),
                        "best_face_confidence": profile.get("best_face_confidence"),
                        "primary_embedding": profile_embeddings[0] if profile_embeddings else None,
                        "embeddings": profile_embeddings,
                        "appearance_signatures": profile.get("appearance_signatures", []),
                        "match_scores": profile.get("match_scores", []),
                        "observed_frame_indices": profile.get("observed_frame_indices", []),
                        "frame_bboxes": profile.get("frame_bboxes", {}),
                    })
                    merged_profiles = self._safe_handoff_merge_profiles(merged_profiles)

                # ============================================================
                # DEBUG REPORT
                # ============================================================
                print("\n========== DEBUG ONLINE IDENTITY ==========")
                print(f"raw_track_count      : {len(track_observation_counts)}")
                print(f"assigned_tracks      : {len(track_to_profile)}")
                print(f"online_profiles      : {len(online_profiles)}")
                print(f"final_profiles       : {len(merged_profiles)}")
                print(f"faces_detected       : {len(debug_face_records)}")

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

                        for record in debug_person_records:
                            f_idx = record["frame_index"]

                            if f_idx not in records_by_frame:
                                records_by_frame[f_idx] = []

                            records_by_frame[f_idx].append(record)

                        # Tính tổng số khách hàng duy nhất đã được gộp ID
                        # (Dùng set để loại bỏ các track_id bị trùng profile_id)
                        total_unique_people = len(set(pid for pid in track_to_profile.values() if pid != "PENDING"))

                        for frame_data in frame_result.frames:
                            img = cv2.imread(frame_data.image_path)

                            if img is None:
                                continue

                            frame_records = records_by_frame.get(frame_data.frame_index, [])

                            for record in frame_records:
                                x1, y1, x2, y2 = [int(v) for v in record["bbox"]]
                                track_id = record["track_id"]
                                profile_id = track_to_profile.get(track_id, "PENDING")

                                # Màu khung viền (Xanh lá nếu có ID thật, Đỏ nếu là rác bị loại)
                                box_color = (0, 255, 0) if profile_id != "PENDING" else (0, 0, 255)
                                
                                # Đổi màu chữ thành Vàng (B=0, G=255, R=255)
                                text_color = (0, 255, 255) if profile_id != "PENDING" else (0, 0, 255)

                                cv2.rectangle(img, (x1, y1), (x2, y2), box_color, 2)

                                label = f"Trk:{track_id} -> {profile_id}"

                                cv2.putText(
                                    img,
                                    label,
                                    (x1, max(0, y1 - 10)),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    0.6,
                                    text_color, # Dùng biến text_color ở đây
                                    2,
                                )

                            # HIỂN THỊ TỔNG SỐ NGƯỜI Ở GÓC TRÊN CÙNG BÊN TRÁI
                            counter_label = f"Total person: {total_unique_people}"
                            counter_color = (0, 255, 0)
                            
                            # Đổ bóng (Shadow) cho chữ dễ đọc trên nền sáng
                            cv2.putText(img, counter_label, (32, 52), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 3)
                            # Chữ chính
                            cv2.putText(img, counter_label, (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, counter_color, 3)

                            out_video.write(img)

                        out_video.release()

                print("XỬ LÝ ONLINE PIPELINE HOÀN TẤT!")

                return {
                    "raw_track_count": len(track_observation_counts),
                    "assigned_tracks": len(track_to_profile),
                    "faces_detected": len(debug_face_records),
                    "valid_tracklets": len(track_to_profile),
                    "merged_profiles": merged_profiles,
                    "track_to_profile": track_to_profile,
                }

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

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
YUNET_MODEL_PATH = os.path.join(CURRENT_DIR, "models", "face_detection_yunet_2023mar.onnx")
# Sửa lại đường dẫn nạp mô hình mới
SFACE_MODEL_PATH = os.path.join(CURRENT_DIR, "models", "face_recognition_sface_2021dec.onnx")

video_pipeline_service = VideoProcessingPipelineService(
    yunet_model_path=YUNET_MODEL_PATH,
    sface_model_path=SFACE_MODEL_PATH # Truyền file sface vào tham số này
)