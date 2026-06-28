import os
import cv2
import shutil
from typing import Dict

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
from app.services.ai.video_pipeline_identity_corrections import VideoPipelineIdentityCorrectionMixin


class VideoProcessingPipelineService(
    VideoPipelineDebugMixin,
    VideoPipelineGeometryMixin,
    VideoPipelineExportMixin,
    VideoPipelineIdentityCorrectionMixin,
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
        print("VIDEO_PIPELINE_VERSION = camera_ready_realtime_identity_v4_2_26_refactor_short_gap_sticky_safe")

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
        print("KHỞI ĐỘNG ONLINE AI PIPELINE + TRUE DELAYED REALTIME V1 DEBUG LITE")
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

        FACE_ONLY_REID_THRESHOLD = 0.48
        FACE_ONLY_REID_CONF = 0.78
        FACE_ONLY_REID_MARGIN = 0.06

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
        REASSIGN_MIN_FACE = 0.53
        REASSIGN_MIN_TOTAL = 0.48
        REASSIGN_MIN_FACE_CONF = 0.78
        REASSIGN_CONFIRM_MIN_SAMPLES = 2
        REASSIGN_CONFIRM_MIN_AVG_FACE = 0.54
        REASSIGN_CONFIRM_MIN_AVG_TOTAL = 0.49
        REASSIGN_IMMEDIATE_FACE = 0.64
        REASSIGN_IMMEDIATE_TOTAL = 0.55
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
        RECENT_TRACK_HANDOFF_MAX_GAP_SECONDS = 12.0
        RECENT_TRACK_HANDOFF_MIN_NEW_OBS = 1
        RECENT_TRACK_HANDOFF_MAX_NEW_OBS = 180
        RECENT_TRACK_HANDOFF_IOU = 0.03
        RECENT_TRACK_HANDOFF_CONTAINMENT = 0.10
        RECENT_TRACK_HANDOFF_CENTER_NORM = 0.42
        RECENT_TRACK_HANDOFF_AREA_RATIO_MIN = 0.25
        RECENT_TRACK_HANDOFF_AREA_RATIO_MAX = 4.00
        RECENT_TRACK_HANDOFF_OLD_MAX_MOTION_NORM = 0.28
        RECENT_TRACK_HANDOFF_CURRENT_MAX_MOTION_NORM = 0.35
        RECENT_TRACK_HANDOFF_MIN_APPEARANCE = 0.18

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
        BODY_REID_SAMPLE_EVERY_N_OBS = 3
        BODY_REID_MAX_SAMPLES_PER_TRACK = 28
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
        FINAL_PEER_OUTLIER_SPLIT_ENABLED = True
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
        EPISODE_SPLIT_ENABLED = True
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
        PROFILE_REFINE_ENABLED = True
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
        FINAL_HEAD_SPLIT_ENABLED = True
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
        FINAL_TAIL_GROUP_SPLIT_ENABLED = True
        FINAL_TAIL_GROUP_SPLIT_GAP_SECONDS = 5.0
        FINAL_TAIL_GROUP_SPLIT_MIN_PROFILE_TRACKS = 5
        FINAL_TAIL_GROUP_SPLIT_MAX_HEAD_TRACKS = 2
        FINAL_TAIL_GROUP_SPLIT_MIN_HEAD_TOTAL_OBS = 300
        FINAL_TAIL_GROUP_SPLIT_MIN_TAIL_TRACKS = 3
        FINAL_TAIL_GROUP_SPLIT_MIN_TAIL_TOTAL_OBS = 180
        FINAL_TAIL_GROUP_SPLIT_MIN_EACH_TAIL_OBS = 25

        FINAL_SHORT_GAP_RETURN_REPAIR_ENABLED = True
        FINAL_SHORT_GAP_RETURN_REPAIR_MAX_CANDIDATE_GAP_SECONDS = 6.0
        FINAL_SHORT_GAP_RETURN_REPAIR_MIN_CURRENT_GAP_SECONDS = 18.0
        FINAL_SHORT_GAP_RETURN_REPAIR_MIN_TRACK_OBS = 80

        # v4.2.26: nếu track đã được assign bằng short-gap strong return,
        # khóa mềm track đó vào profile đã chọn để tránh relink ping-pong sang P khác
        # chỉ vì face vector cao hơn ở các frame sau.
        SHORT_GAP_RETURN_STICKY_LOCK_ENABLED = True

        FINAL_EARLY_SINGLETON_SPLIT_ENABLED = True
        FINAL_EARLY_SINGLETON_SPLIT_GAP_SECONDS = 18.0
        FINAL_EARLY_SINGLETON_MAX_HEAD_OBS = 180
        FINAL_EARLY_SINGLETON_MIN_TAIL_TOTAL_OBS = 250
        FINAL_EARLY_SINGLETON_MIN_LONG_TAIL_OBS = 250

        FINAL_MIDDLE_SINGLETON_SPLIT_ENABLED = True
        FINAL_MIDDLE_SINGLETON_MAX_MIDDLE_OBS = 150
        FINAL_MIDDLE_SINGLETON_MIN_EDGE_OBS = 250
        FINAL_MIDDLE_SINGLETON_MIN_HEAD_GAP_SECONDS = 18.0
        FINAL_MIDDLE_SINGLETON_MAX_TAIL_GAP_SECONDS = 4.0

        # Final-only patch trên nền v4.2.3: giữ nguyên online logic cũ, chỉ sửa case
        # predecessor bị dính profile cũ nhưng successor đã có singleton profile sạch.
        FINAL_SUCCESSOR_OWNS_PREDECESSOR_ENABLED = True
        FINAL_SUCCESSOR_PREDECESSOR_MAX_GAP_SECONDS = 6.0

        # Final-only tail-pair fix for short/compact videos.
        # Giữ video dài/complex theo logic v4.2.9 để không phá các cụm đúng của video 1.
        FINAL_SEQUENTIAL_TAIL_PAIR_SPLIT_ENABLED = True
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
        short_gap_return_sticky_locks = {}
        frame_profile_locks = {}

        # last_assigned_track_states lưu bbox cuối của từng track đã có profile.
        # Khi tracker đứt track và sinh track mới gần như cùng vị trí, ta nối lại
        # theo track trước đó thay vì cho track mới match toàn gallery.
        last_assigned_track_states = {}

        debug_person_records = []
        debug_face_records = []

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
                f"[TrueDelayedRealtime] correction_interval={REALTIME_CORRECTION_INTERVAL_FRAMES} frames, "
                f"track_close_timeout={realtime_track_close_timeout_frames} frames, "
                f"display_delay={delayed_display_min_frames} frames/{DELAYED_DISPLAY_MIN_OBS} obs"
            )

            for frame_data in frame_result.frames:
                image = cv2.imread(frame_data.image_path)

                if image is None:
                    continue

                tracked_persons = self.tracker.track_persons_in_frame(
                    frame=image,
                    frame_index=frame_data.frame_index,
                    img_path=frame_data.image_path,
                )

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
                        # ONLINE RELINK / CORRECTION
                        # ====================================================
                        # Track đã có profile vẫn có thể bị gán nhầm lúc đầu.
                        # Nếu về sau face rõ hơn và một profile khác phù hợp hơn,
                        # chuyển RIÊNG track này sang profile đó. Không merge nguyên
                        # profile cũ để tránh kéo P006 thật vào P004.
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

                        # Entry-reuse là rủi ro cao: không cho confirmation bằng appearance/total kéo qua.
                        # Chỉ face rất mạnh mới được match ngay.
                        if selected_is_entry_reuse and not immediate_reid and not selected_short_gap_strong_return:
                            should_assign_existing = False
                            temporal_spatial_block_reason = (
                                "entry_reuse_requires_immediate_strong_face_not_confirmation"
                            )
                        elif not immediate_reid and not confirmed_reid:
                            should_assign_existing = False
                            temporal_spatial_block_reason = "candidate_not_confirmed_yet"
                            track_debug_status[track_id] = (
                                f"PENDING: candidate not confirmed, candidate={best_profile_id}, "
                                f"total={best_total_score:.3f}, face={best_face_score:.3f}, "
                                f"app={best_app_score:.3f}, margin={best_margin:.3f}, "
                                f"conf={face_conf:.2f}, obs={obs_count}"
                            )

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
                            observed_frame_indices=[frame_data.frame_index],
                            appearance_signature=appearance_signature if valid_body_for_identity else None,
                            bbox=bbox,
                            match_score=best_total_score,
                        )
                        track_to_profile[track_id] = profile_id
                        profile_owner_track.setdefault(profile_id, int(track_id))

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
                    # Chỉ tạo profile mới nếu không quá gần profile cũ
                    # hoặc đã pending đủ lâu.
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

                    can_create_new_profile_now = (
                        face_conf >= MIN_FACE_CONFIDENCE_FOR_NEW_PROFILE
                        and valid_body_for_identity
                        and not ambiguous_reid_candidate
                        and local_handoff_candidate_profile is None
                        and (
                            not near_existing_profile
                            or obs_count >= MAX_PENDING_OBS_BEFORE_NEW_PROFILE
                        )
                    )

                    can_create_from_best_sample = (
                        has_stable_best_sample
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

                # ========================================================
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
                self._split_same_frame_active_profile_conflicts(
                    frame_index=current_frame_index,
                    active_track_ids=active_track_ids,
                    active_track_bboxes=active_track_bboxes,
                    track_to_profile=track_to_profile,
                    track_frame_bboxes=track_frame_bboxes,
                    track_debug_status=track_debug_status,
                    profile_owner_track=profile_owner_track,
                )

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

                    # 4) visual/color outlier split realtime, không đợi hết video.
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

            # ============================================================
            # EXPORT PROFILES
            # ============================================================
            # Không chạy final video pass. Mọi correction đã chạy theo periodic/track-closed event.
            print(f"[TrueDelayedRealtime] realtime_correction_ticks={realtime_correction_ticks}")

            # Tách episode muộn khỏi profile lớn trước khi export.
            # Đây không phải hard-code track id; nó dựa trên temporal gap + tail cluster.
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
                    realtime_frame_index=None,
                )

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
                    realtime_frame_index=None,
                )

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

            # IMPORTANT: v4.2.9 is the stable behavior for the first/long video.
            # Tail-pair split is only enabled for compact videos where the known failure
            # pattern is a late predecessor/successor pair (e.g. track30/33), so it cannot
            # break the correct long-video clusters. This is not track-id hardcoding.
            short_video_tail_pair_allowed = (
                len(track_observation_counts) <= int(FINAL_SEQUENTIAL_TAIL_PAIR_MAX_TRACK_COUNT)
                and int(getattr(frame_result, "extracted_count", 0) or 0) <= int(FINAL_SEQUENTIAL_TAIL_PAIR_MAX_EXTRACTED_FRAMES)
            )
            if FINAL_SEQUENTIAL_TAIL_PAIR_SPLIT_ENABLED and short_video_tail_pair_allowed:
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
            elif FINAL_SEQUENTIAL_TAIL_PAIR_SPLIT_ENABLED:
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

                    for record in debug_person_records:
                        f_idx = record["frame_index"]

                        if f_idx not in records_by_frame:
                            records_by_frame[f_idx] = []

                        records_by_frame[f_idx].append(record)

                    # Tính tổng số khách hàng theo đúng danh sách export cuối cùng.
                    # Không dùng track_to_profile trực tiếp vì nó có thể còn profile rỗng/ghost
                    # đã bị _build_export_profiles_from_current_mapping skip khỏi tổng kết.
                    exported_profile_ids = set(p.get("profile_id") for p in merged_profiles if p.get("profile_id"))
                    total_unique_people = len(exported_profile_ids)

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
                            final_profile_id = track_to_profile.get(track_id, "PENDING")
                            if final_profile_id not in exported_profile_ids:
                                final_profile_id = "PENDING"
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
                            elif display_profile_id != "PENDING":
                                box_color = (0, 255, 0)     # green: committed P_id
                                text_color = (0, 255, 255)
                            else:
                                box_color = (0, 0, 255)     # red: pending/no identity
                                text_color = (0, 0, 255)

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

                        # HIỂN THỊ TỔNG SỐ NGƯỜI Ở GÓC TRÊN CÙNG BÊN TRÁI
                        counter_label = f"Total person: {total_unique_people}"
                        counter_color = (0, 255, 0)

                        # Đổ bóng (Shadow) cho chữ dễ đọc trên nền sáng
                        cv2.putText(img, counter_label, (32, 52), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 3)
                        # Chữ chính
                        cv2.putText(img, counter_label, (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, counter_color, 3)

                        out_video.write(img)

                    out_video.release()

            person_paths = self._build_person_paths(
                track_to_profile=track_to_profile,
                track_frame_bboxes=track_frame_bboxes,
            )

            print("XỬ LÝ ONLINE PIPELINE HOÀN TẤT!")

            return {
                "raw_track_count": len(track_observation_counts),
                "assigned_tracks": len(track_to_profile),
                "faces_detected": len(debug_face_records),
                "valid_tracklets": len(track_to_profile),
                "merged_profiles": merged_profiles,
                "track_to_profile": track_to_profile,
                # Dùng cho camera/DB: lấy đường đi theo P_id, nhưng vẫn giữ từng track_id gốc.
                "person_paths": person_paths,
            }



CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
YUNET_MODEL_PATH = os.path.join(CURRENT_DIR, "models", "face_detection_yunet_2023mar.onnx")
SFACE_MODEL_PATH = os.path.join(CURRENT_DIR, "models", "face_recognition_sface_2021dec.onnx")

video_pipeline_service = VideoProcessingPipelineService(
    yunet_model_path=YUNET_MODEL_PATH,
    sface_model_path=SFACE_MODEL_PATH,
)
