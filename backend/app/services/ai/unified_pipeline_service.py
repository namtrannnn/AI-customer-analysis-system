"""
AI-15: Unified Pipeline Service

Merge video pipeline (PB01 - nhận diện khách) +
       movement track pipeline (ND3 - tracking đường đi)

Gọi 2 pipeline độc lập rồi merge kết quả.
Không sửa video_pipeline_service.py để tránh break code cũ.
"""

import tempfile
from dataclasses import dataclass, field
from typing import Optional

from app.services.ai.video_pipeline_service import (
    VideoProcessingPipelineService,
    video_pipeline_service,
)
from app.services.ai.movement_track_pipeline_service import (
    MovementTrackPipelineService,
    MovementPipelineResult,
    movement_track_pipeline,
)


@dataclass
class UnifiedPipelineResult:
    """Kết quả gộp từ cả 2 pipeline."""

    # ── Từ video_pipeline (PB01) ──
    total_customers: int = 0
    new_customers: int = 0
    returning_customers: int = 0
    detected_customers: list = field(default_factory=list)
    merged_profiles: list = field(default_factory=list)

    # ── Từ movement_track_pipeline (ND3) ──
    movement_result: Optional[MovementPipelineResult] = None

    # ── Map profile_id → track_id để join 2 kết quả ──
    track_to_profile: dict = field(default_factory=dict)


class UnifiedPipelineService:
    """
    AI-15: Chạy cả video pipeline (nhận diện) và tracking pipeline (đường đi).

    Usage:
        result = unified_pipeline.process(video_path, zones)
        # result.detected_customers  → dùng cho response FE-06/07
        # result.movement_result     → dùng lưu movement_tracks + zone_visits
    """

    def __init__(
        self,
        video_svc: Optional[VideoProcessingPipelineService] = None,
        tracking_svc: Optional[MovementTrackPipelineService] = None,
        run_tracking: bool = True,
        tracking_fps: float = 2.0,
    ):
        self.video_svc = video_svc or video_pipeline_service
        self.tracking_svc = tracking_svc or movement_track_pipeline
        self.run_tracking = run_tracking
        self.tracking_fps = tracking_fps

    def process(
        self,
        video_path: str,
        zones: list[dict] | None = None,
        output_face_dir: str = "./pipeline_faces",
        target_fps: float = 1.0,
    ) -> UnifiedPipelineResult:
        """
        Chạy full pipeline.

        Args:
            video_path : đường dẫn file video
            zones      : list zone dicts từ DB [{"id", "zone_name", "polygon", ...}]
                         Nếu None hoặc empty thì skip tracking.
            output_face_dir: thư mục lưu ảnh khuôn mặt crop
            target_fps : FPS để extract frame cho video pipeline

        Returns:
            UnifiedPipelineResult
        """
        result = UnifiedPipelineResult()

        # ── 1. Chạy video pipeline (nhận diện khách) ─────────────────────────
        print("\n[UnifiedPipeline] Bắt đầu Video Pipeline (PB01)...")
        video_result = self.video_svc.process_video(
            video_path=video_path,
            output_face_dir=output_face_dir,
            target_fps=target_fps,
        )

        # Map kết quả video pipeline
        merged_profiles = video_result.get("merged_profiles", [])
        track_to_profile = video_result.get("track_to_profile", {})

        result.merged_profiles = merged_profiles
        result.track_to_profile = track_to_profile
        result.total_customers = len(merged_profiles)
        result.new_customers = result.total_customers   # ND2 sẽ phân loại sau
        result.returning_customers = 0

        # Build detected_customers list (khớp schema video_schema.py)
        for profile in merged_profiles:
            result.detected_customers.append({
                "anonymous_id": profile.get("profile_id", "UNKNOWN"),
                "customer_type": "new",   # ND2 phân loại
                "confidence": round(
                    float(profile.get("best_face_confidence") or 0.0), 2
                ),
            })

        # ── 2. Chạy movement tracking pipeline (ND3) ─────────────────────────
        if self.run_tracking and zones:
            print("\n[UnifiedPipeline] Bắt đầu Movement Track Pipeline (ND3)...")
            try:
                movement_result = self.tracking_svc.process_video(
                    video_path=video_path,
                    zones=zones,
                )
                result.movement_result = movement_result

                # Gán anonymous_id cho từng track dựa trên track_to_profile
                for track in movement_result.tracks:
                    profile_id = track_to_profile.get(track.track_id)
                    if profile_id:
                        track.anonymous_id = profile_id
                    else:
                        track.anonymous_id = f"TRK_{track.track_id:04d}"

                print(
                    f"[UnifiedPipeline] Tracking xong: "
                    f"{movement_result.total_persons} người, "
                    f"{len(movement_result.zone_visits)} zone visits"
                )
            except Exception as e:
                print(f"[UnifiedPipeline] Tracking pipeline lỗi (bỏ qua): {e}")
                result.movement_result = None
        else:
            reason = "zones empty/None" if not zones else "run_tracking=False"
            print(f"[UnifiedPipeline] Skip tracking ({reason})")

        print(
            f"\n[UnifiedPipeline] Hoàn tất: "
            f"{result.total_customers} khách, "
            f"{len(result.detected_customers)} profiles"
        )

        return result


# ─── Singleton ────────────────────────────────────────────────────────────────
unified_pipeline = UnifiedPipelineService()
