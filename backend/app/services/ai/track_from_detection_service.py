"""
AI-14b: Track từ detection records của video pipeline.

Thay vì chạy ByteTrack lần 2, dùng debug_person_records đã có từ
video_pipeline_service để tính đường đi + zone enter/exit.

track_id trong debug_person_records khớp hoàn toàn với track_id
trong track_to_profile → map được P_000X.
"""

from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional

from app.services.ai.roi_service import roi_service
from app.services.ai.zone_enter_exit_service import (
    ZoneEnterExitService,
    TrackPosition,
)
from app.services.ai.movement_track_pipeline_service import (
    TrackPoint,
    TrackResult,
    ZoneVisitData,
    MovementPipelineResult,
)


def process_detections_for_tracking(
    debug_person_records: list[dict],
    zones: list[dict],
    video_fps: float = 1.0,
    frame_width: int = 1280,
    frame_height: int = 720,
    min_frames_in_zone: int = 2,
) -> MovementPipelineResult:
    """
    Xử lý debug_person_records từ video_pipeline để tính:
    - Đường đi của từng track (position theo thời gian)
    - Zone enter/exit events
    - Zone visit summary

    Args:
        debug_person_records: list[{"frame_index", "track_id", "bbox": [x1,y1,x2,y2]}]
        zones: list zone dicts từ DB
        video_fps: FPS của video gốc
        frame_width/height: kích thước frame để normalize bbox
        min_frames_in_zone: số frame tối thiểu trong zone mới tính ENTER
    """
    result = MovementPipelineResult()
    zone_enter_exit = ZoneEnterExitService(min_frames_in_zone=min_frames_in_zone)

    track_points: dict[int, list[TrackPoint]] = {}
    track_zones: dict[int, set[int]] = {}

    # THÊM DÒNG NÀY
    track_route: dict[int, list[int]] = {}

    track_entry: dict[int, datetime] = {}
    track_exit: dict[int, datetime] = {}

    # Thời điểm bắt đầu = now, mỗi frame = now + offset
    video_start = datetime.now()

    # Sort theo frame_index để đảm bảo thứ tự thời gian
    sorted_records = sorted(debug_person_records, key=lambda r: r["frame_index"])

    # Group records theo frame để xử lý zone enter/exit theo frame
    frames_dict: dict[int, list[dict]] = {}
    for rec in sorted_records:
        fi = rec["frame_index"]
        if fi not in frames_dict:
            frames_dict[fi] = []
        frames_dict[fi].append(rec)

    for frame_index in sorted(frames_dict.keys()):
        records = frames_dict[frame_index]
        # Timestamp thực tế
        ts = video_start + timedelta(seconds=frame_index / max(video_fps, 1.0))

        positions_this_frame: list[TrackPosition] = []

        for rec in records:
            track_id = rec["track_id"]
            bbox = rec.get("bbox", [0, 0, 1, 1])

            if len(bbox) < 4:
                continue

            x1, y1, x2, y2 = bbox

            # Lấy frame size từ record (chính xác) hoặc fallback về tham số
            fw = rec.get("frame_width", frame_width)
            fh = rec.get("frame_height", frame_height)

            # Normalize bbox pixel → relative 0..1
            nx1, ny1, nx2, ny2 = roi_service.normalize_bbox(
                x1, y1, x2, y2, fw, fh
            )
            cx, cy = roi_service.bbox_centroid(nx1, ny1, nx2, ny2)

            # AI-11: Check zone
            zone_result = roi_service.find_zone_for_point(cx, cy, zones)
            zone_id = zone_result.zone_id

            point = TrackPoint(
                track_id=track_id,
                x=round(cx, 4),
                y=round(cy, 4),
                zone_id=zone_id,
                tracked_at=ts,
                frame_index=frame_index,
            )

            if track_id not in track_points:
                track_points[track_id] = []
                track_zones[track_id] = set()

                # THÊM DÒNG NÀY
                track_route[track_id] = []

                track_entry[track_id] = ts

            # append điểm gốc
            track_points[track_id].append(point)

            prev_points = track_points[track_id]

            if len(prev_points) >= 2:
                p1 = prev_points[-2]
                p2 = prev_points[-1]

                steps = 3  # tăng số điểm giả giữa 2 frame

                for i in range(1, steps):
                    interp_point = TrackPoint(
                        track_id=track_id,
                        x=round(p1.x + (p2.x - p1.x) * i / steps, 4),
                        y=round(p1.y + (p2.y - p1.y) * i / steps, 4),
                        zone_id=p2.zone_id,
                        tracked_at=ts,
                        frame_index=frame_index,
                    )
                    track_points[track_id].append(interp_point)

            track_exit[track_id] = ts

            if zone_id is not None:
                track_zones[track_id].add(zone_id)

                # THÊM ĐOẠN NÀY
                if (
                    len(track_route[track_id]) == 0
                    or track_route[track_id][-1] != zone_id
                ):
                    track_route[track_id].append(zone_id)

            positions_this_frame.append(TrackPosition(
                track_id=track_id,
                x=cx,
                y=cy,
                zone_id=zone_id,
                timestamp=ts,
                frame_index=frame_index,
            ))

        # AI-13: Zone enter/exit
        events = zone_enter_exit.process_frame_positions(positions_this_frame)
        result.zone_events.extend(events)

    # Finalize
    result.zone_events.extend(zone_enter_exit.finalize())

    # Aggregate tracks
    for track_id, points in track_points.items():
        if not points:
            continue
        entry = track_entry.get(track_id)
        exit_ = track_exit.get(track_id)
        duration = int((exit_ - entry).total_seconds()) if entry and exit_ else None
        print(
            "TRACK:",
            track_id,
            "route =",
            track_route.get(track_id),
        )
        result.tracks.append(
            TrackResult(
                track_id=track_id,
                points=points,

                # SỬA DÒNG NÀY
                zones_visited=track_route.get(track_id, []),

                entry_time=entry,
                exit_time=exit_,
                duration_seconds=duration,
            )
        )
    # Zone visits
    for v in zone_enter_exit.get_zone_visit_summary():
        result.zone_visits.append(ZoneVisitData(
            track_id=v["track_id"],
            zone_id=v["zone_id"],
            enter_time=v.get("enter_time"),
            leave_time=v.get("leave_time"),
            duration_seconds=v.get("duration_seconds"),
            enter_frame=v.get("enter_frame"),
            leave_frame=v.get("leave_frame"),
        ))

    result.total_persons = len(track_points)

    return result
