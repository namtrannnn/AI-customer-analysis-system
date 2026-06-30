"""
AI-14: Movement Track Pipeline Service
"""

import time
import tempfile
import cv2
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from app.services.ai.frame_extractor_service import FrameExtractorService
from app.services.ai.tracking_service import TrackingService, tracker_service
from app.services.ai.roi_service import ROIService, roi_service
from app.services.ai.zone_enter_exit_service import (
    ZoneEnterExitService,
    TrackPosition,
    ZoneEvent,
)


# ─── Result data classes ──────────────────────────────────────────────────────

@dataclass
class TrackPoint:
    track_id: int
    x: float
    y: float
    zone_id: Optional[int]
    tracked_at: datetime
    frame_index: int


@dataclass
class TrackResult:
    track_id: int
    points: list = field(default_factory=list)
    zones_visited: list = field(default_factory=list)
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    anonymous_id: Optional[str] = None


@dataclass
class ZoneVisitData:
    track_id: int
    zone_id: int
    enter_time: Optional[datetime]
    leave_time: Optional[datetime]
    duration_seconds: Optional[int]
    enter_frame: Optional[int] = None
    leave_frame: Optional[int] = None


@dataclass
class MovementPipelineResult:
    tracks: list = field(default_factory=list)
    zone_visits: list = field(default_factory=list)
    zone_events: list = field(default_factory=list)
    total_persons: int = 0
    total_frames_processed: int = 0
    processing_time_ms: int = 0
    video_fps: float = 0.0
    video_duration_seconds: float = 0.0


# ─── Pipeline ─────────────────────────────────────────────────────────────────

class MovementTrackPipelineService:

    def __init__(
        self,
        tracking_svc: Optional[TrackingService] = None,
        roi_svc: Optional[ROIService] = None,
        target_fps: float = 2.0,
        conf_threshold: float = 0.4,
        min_frames_in_zone: int = 2,
    ):
        self.tracking_svc = tracking_svc or tracker_service
        self.roi_svc = roi_svc or roi_service
        self.frame_extractor = FrameExtractorService()
        self.target_fps = target_fps
        self.conf_threshold = conf_threshold
        self.min_frames_in_zone = min_frames_in_zone

    def process_video(
        self,
        video_path: str,
        zones: list[dict],
    ) -> MovementPipelineResult:

        start_ms = int(time.time() * 1000)

        result = MovementPipelineResult()
        zone_enter_exit = ZoneEnterExitService(
            min_frames_in_zone=self.min_frames_in_zone
        )

        track_points: dict[int, list[TrackPoint]] = {}
        track_zones: dict[int, set[int]] = {}
        track_entry: dict[int, datetime] = {}
        track_exit: dict[int, datetime] = {}
        all_zone_events: list[ZoneEvent] = []

        # Thời điểm bắt đầu xử lý video = now
        # timestamp của mỗi frame = now + offset giây trong video
        video_start_time = datetime.now()

        with tempfile.TemporaryDirectory(prefix="tracking_frames_") as frame_dir:
            extraction = self.frame_extractor.extract_frames(
                video_path=video_path,
                output_dir=frame_dir,
                target_fps=self.target_fps,
            )

            result.video_fps = extraction.video_fps
            result.video_duration_seconds = extraction.duration_seconds
            result.total_frames_processed = extraction.extracted_count

            for ef in extraction.frames:
                frame = cv2.imread(ef.image_path)
                if frame is None:
                    continue

                frame_h, frame_w = frame.shape[:2]

                # Timestamp thực tế = lúc bắt đầu + offset trong video
                ts = video_start_time + timedelta(seconds=ef.timestamp_seconds)

                # AI-09: Track persons
                tracked = self.tracking_svc.track_persons_in_frame(
                    frame=frame,
                    frame_index=ef.frame_index,
                    img_path=ef.image_path,
                    conf_threshold=self.conf_threshold,
                )

                if not tracked:
                    continue

                positions_this_frame: list[TrackPosition] = []

                for det in tracked:
                    x1, y1, x2, y2 = det["bbox"]
                    nx1, ny1, nx2, ny2 = self.roi_svc.normalize_bbox(
                        x1, y1, x2, y2, frame_w, frame_h
                    )
                    cx, cy = self.roi_svc.bbox_centroid(nx1, ny1, nx2, ny2)

                    # AI-11: Check zone
                    zone_result = self.roi_svc.find_zone_for_point(cx, cy, zones)
                    zone_id = zone_result.zone_id
                    track_id = det["track_id"]

                    point = TrackPoint(
                        track_id=track_id,
                        x=round(cx, 4),
                        y=round(cy, 4),
                        zone_id=zone_id,
                        tracked_at=ts,
                        frame_index=ef.frame_index,
                    )

                    if track_id not in track_points:
                        track_points[track_id] = []
                        track_zones[track_id] = set()
                        track_entry[track_id] = ts

                    track_points[track_id].append(point)
                    track_exit[track_id] = ts

                    if zone_id is not None:
                        track_zones[track_id].add(zone_id)

                    positions_this_frame.append(TrackPosition(
                        track_id=track_id,
                        x=cx,
                        y=cy,
                        zone_id=zone_id,
                        timestamp=ts,
                        frame_index=ef.frame_index,
                    ))

                # AI-13: Detect enter/exit events
                events = zone_enter_exit.process_frame_positions(positions_this_frame)
                all_zone_events.extend(events)

        # Finalize
        final_events = zone_enter_exit.finalize()
        all_zone_events.extend(final_events)

        # Aggregate tracks
        for track_id, points in track_points.items():
            if not points:
                continue

            entry = track_entry.get(track_id)
            exit_ = track_exit.get(track_id)
            duration = None
            if entry and exit_:
                duration = int((exit_ - entry).total_seconds())

            result.tracks.append(TrackResult(
                track_id=track_id,
                points=points,
                zones_visited=sorted(list(track_zones.get(track_id, set()))),
                entry_time=entry,
                exit_time=exit_,
                duration_seconds=duration,
            ))

        # Zone visits
        zone_visit_summary = zone_enter_exit.get_zone_visit_summary()
        for v in zone_visit_summary:
            result.zone_visits.append(ZoneVisitData(
                track_id=v["track_id"],
                zone_id=v["zone_id"],
                enter_time=v.get("enter_time"),
                leave_time=v.get("leave_time"),
                duration_seconds=v.get("duration_seconds"),
                enter_frame=v.get("enter_frame"),
                leave_frame=v.get("leave_frame"),
            ))

        result.zone_events = all_zone_events
        result.total_persons = len(track_points)
        result.processing_time_ms = int(time.time() * 1000) - start_ms

        return result


# ─── Singleton ────────────────────────────────────────────────────────────────
movement_track_pipeline = MovementTrackPipelineService()
