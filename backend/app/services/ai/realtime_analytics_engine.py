from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import cv2
import numpy as np

from app.services.ai.tracking_service import TrackingService, YOLO_MODEL_PATH


class RealtimeAnalyticsEngine:
    """
    Realtime analytics engine cho live camera MVP.

    Engine nay:
    - tao / cap nhat state tu frame hien tai
    - sinh event tracking / ROI
    - khong persist event
    """

    def __init__(self, track_end_timeout_seconds: float = 1.5):
        self.tracker = TrackingService(model_path=YOLO_MODEL_PATH)
        self.track_end_timeout = timedelta(seconds=track_end_timeout_seconds)

    def process_frame(self, runtime, frame_packet) -> dict[str, Any]:
        frame = self._resolve_decoded_frame(frame_packet)

        if frame is None:
            return {
                "current_count": runtime.current_count,
                "current_tracks": runtime.current_tracks,
                "emitted_events": [],
                "decoded_frame": None,
            }

        tracked_persons = self.tracker.track_persons_in_frame(
            frame=frame,
            frame_index=frame_packet.frame_id or 0,
            img_path=f"realtime://{runtime.stream_session_id}",
        )

        event_timestamp = frame_packet.timestamp
        emitted_events: list[dict[str, Any]] = []
        next_tracks = dict(runtime.current_tracks)
        seen_track_ids: set[int] = set()

        for person in tracked_persons:
            track_id = int(person["track_id"])
            seen_track_ids.add(track_id)

            bbox = [int(v) for v in person["bbox"]]
            confidence = person.get("confidence")
            centroid = self._build_track_centroid(bbox)
            active_roi_ids = self._find_active_roi_ids(
                point=centroid,
                roi_config=runtime.roi_config,
            )

            previous_track = next_tracks.get(track_id)
            previous_roi_ids = set(previous_track.get("active_roi_ids", [])) if previous_track else set()
            current_roi_ids = set(active_roi_ids)

            if previous_track is None:
                emitted_events.append(
                    self._build_event(
                        event_type="track_start",
                        event_timestamp=event_timestamp,
                        session_id=runtime.stream_session_id,
                        payload={
                            "track_id": track_id,
                            "bbox": bbox,
                            "confidence": confidence,
                            "centroid": centroid,
                        },
                    )
                )

            entered_roi_ids = sorted(list(current_roi_ids - previous_roi_ids))
            exited_roi_ids = sorted(list(previous_roi_ids - current_roi_ids))

            for roi_id in entered_roi_ids:
                emitted_events.append(
                    self._build_event(
                        event_type="roi_enter",
                        event_timestamp=event_timestamp,
                        session_id=runtime.stream_session_id,
                        payload={
                            "track_id": track_id,
                            "roi_id": roi_id,
                        },
                    )
                )

            for roi_id in exited_roi_ids:
                emitted_events.append(
                    self._build_event(
                        event_type="roi_exit",
                        event_timestamp=event_timestamp,
                        session_id=runtime.stream_session_id,
                        payload={
                            "track_id": track_id,
                            "roi_id": roi_id,
                        },
                    )
                )

            point_record = {
                "track_id": track_id,
                "x": centroid[0],
                "y": centroid[1],
                "tracked_at": event_timestamp.isoformat(),
                "active_roi_ids": active_roi_ids,
            }
            path_buffer = runtime.path_buffer_by_track.setdefault(track_id, [])
            path_buffer.append(point_record)

            if len(path_buffer) > runtime.max_path_buffer_points:
                runtime.path_buffer_by_track[track_id] = path_buffer[-runtime.max_path_buffer_points:]

            next_tracks[track_id] = {
                "track_id": track_id,
                "bbox": bbox,
                "centroid": centroid,
                "confidence": confidence,
                "active_roi_ids": active_roi_ids,
                "last_seen_at": event_timestamp,
            }

        for track_id, track_info in list(next_tracks.items()):
            if track_id in seen_track_ids:
                continue

            last_seen_at = track_info.get("last_seen_at")
            if last_seen_at is None:
                continue

            if event_timestamp - last_seen_at < self.track_end_timeout:
                continue

            for roi_id in track_info.get("active_roi_ids", []):
                emitted_events.append(
                    self._build_event(
                        event_type="roi_exit",
                        event_timestamp=event_timestamp,
                        session_id=runtime.stream_session_id,
                        payload={
                            "track_id": track_id,
                            "roi_id": roi_id,
                        },
                    )
                )

            emitted_events.append(
                self._build_event(
                    event_type="track_end",
                    event_timestamp=event_timestamp,
                    session_id=runtime.stream_session_id,
                    payload={
                        "track_id": track_id,
                    },
                )
            )

            next_tracks.pop(track_id, None)

        return {
            "current_count": len(next_tracks),
            "current_tracks": next_tracks,
            "emitted_events": emitted_events,
            "decoded_frame": frame,
        }

    def build_debug_frame(
        self,
        frame: np.ndarray,
        current_tracks: dict[int, dict[str, Any]],
        roi_config: list[dict[str, Any]],
        current_count: int,
    ) -> bytes | None:
        if frame is None:
            return None

        debug_frame = frame.copy()

        for track in current_tracks.values():
            x1, y1, x2, y2 = [int(v) for v in track["bbox"]]
            track_id = track["track_id"]
            label = f"Trk {track_id}"

            cv2.rectangle(debug_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                debug_frame,
                label,
                (x1, max(20, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                2,
            )

        for roi in roi_config:
            points = roi.get("points", [])
            if len(points) < 3:
                continue

            polygon = np.array(
                [[int(point["x"]), int(point["y"])] for point in points],
                dtype=np.int32,
            )
            zone_name = roi.get("zone_name") or roi.get("zone_key") or "ROI"
            anchor_x, anchor_y = polygon[0]

            cv2.polylines(debug_frame, [polygon], isClosed=True, color=(255, 180, 0), thickness=2)
            cv2.putText(
                debug_frame,
                zone_name,
                (int(anchor_x), max(20, int(anchor_y) - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 180, 0),
                2,
            )

        cv2.putText(
            debug_frame,
            f"Count: {current_count}",
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (50, 220, 50),
            2,
        )

        encoded, jpeg_buffer = cv2.imencode(
            ".jpg",
            debug_frame,
            [cv2.IMWRITE_JPEG_QUALITY, 82],
        )

        if not encoded:
            return None

        return jpeg_buffer.tobytes()

    def _resolve_decoded_frame(self, frame_packet):
        if frame_packet.decoded_frame is not None:
            return frame_packet.decoded_frame

        frame_array = np.frombuffer(frame_packet.frame_bytes, dtype=np.uint8)
        decoded_frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
        frame_packet.decoded_frame = decoded_frame
        return decoded_frame

    def _build_track_centroid(self, bbox: list[int]) -> list[float]:
        x1, y1, x2, y2 = bbox
        return [
            float((x1 + x2) / 2.0),
            float(y2),
        ]

    def _find_active_roi_ids(self, point: list[float], roi_config: list[dict[str, Any]]) -> list[str]:
        x, y = point
        active_roi_ids: list[str] = []

        for roi in roi_config:
            points = roi.get("points", [])
            if len(points) < 3:
                continue

            polygon = np.array(
                [[float(item["x"]), float(item["y"])] for item in points],
                dtype=np.float32,
            )

            if cv2.pointPolygonTest(polygon, (x, y), False) >= 0:
                active_roi_ids.append(str(roi.get("zone_key")))

        return active_roi_ids

    def _build_event(
        self,
        event_type: str,
        event_timestamp: datetime,
        session_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "event_type": event_type,
            "event_timestamp": event_timestamp,
            "session_id": session_id,
            "payload": payload,
        }
