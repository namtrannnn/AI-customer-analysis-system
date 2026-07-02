"""
AI-13: Zone Enter/Exit Detection Service

Phát hiện sự kiện khi một người BƯỚC VÀO hoặc ĐI RA khỏi một zone.
Dựa trên việc so sánh zone_id của track ở 2 frame liên tiếp.

Yêu cầu:
- AI-09 (TrackingService) đã gán track_id cho từng person.
- AI-11 (ROIService) đã gán zone_id cho từng vị trí.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ─── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class TrackPosition:
    """Vị trí của 1 track tại 1 thời điểm."""
    track_id: int
    x: float              # relative 0..1
    y: float              # relative 0..1
    zone_id: Optional[int]
    timestamp: datetime
    frame_index: int


@dataclass
class ZoneEvent:
    """Sự kiện enter/exit zone."""
    event_type: str       # "enter" | "exit"
    track_id: int
    zone_id: int
    timestamp: datetime
    frame_index: int
    x: float
    y: float


@dataclass
class TrackZoneState:
    """
    Trạng thái hiện tại của 1 track trong các zones.
    Dùng để theo dõi liên tục qua nhiều frame.
    """
    track_id: int
    current_zone_id: Optional[int] = None
    zone_entry_time: Optional[datetime] = None
    zone_entry_frame: Optional[int] = None
    history: list = field(default_factory=list)  # list[dict] zone visit history


# ─── Service ──────────────────────────────────────────────────────────────────

class ZoneEnterExitService:
    """
    AI-13 Zone Enter/Exit Detection Service.

    Theo dõi trạng thái zone của từng track xuyên suốt video.
    Phát hiện thời điểm chính xác khi enter/exit zone.
    """

    def __init__(self, min_frames_in_zone: int = 2):
        """
        Args:
            min_frames_in_zone: Số frame tối thiểu phải ở trong zone
                                mới tính là ENTER. Tránh event rác do
                                track đi qua biên zone nhanh.
        """
        self.min_frames_in_zone = min_frames_in_zone
        # track_id → TrackZoneState
        self._states: dict[int, TrackZoneState] = {}
        # Pending zones: track vừa vào zone nhưng chưa đủ min_frames
        self._pending: dict[int, dict] = {}

    def reset(self) -> None:
        """Reset state — gọi khi bắt đầu video mới."""
        self._states.clear()
        self._pending.clear()

    def process_frame_positions(
        self,
        positions: list[TrackPosition],
    ) -> list[ZoneEvent]:
        """
        Xử lý tất cả track positions trong 1 frame.

        Args:
            positions: list vị trí các track trong frame hiện tại.
                       Mỗi position đã có zone_id từ ROIService.

        Returns:
            list[ZoneEvent] — các sự kiện enter/exit xảy ra trong frame này.
        """
        events: list[ZoneEvent] = []
        seen_track_ids = set()

        for pos in positions:
            seen_track_ids.add(pos.track_id)
            track_events = self._process_single_position(pos)
            events.extend(track_events)

        # Track nào không còn xuất hiện trong frame → có thể đã exit
        # Nhưng không generate exit ngay — chờ max_age của tracker
        # Việc này được xử lý ở finalize()

        return events

    def _process_single_position(self, pos: TrackPosition) -> list[ZoneEvent]:
        """Xử lý 1 track position, trả về events nếu có."""
        events: list[ZoneEvent] = []
        track_id = pos.track_id

        # Khởi tạo state nếu track mới
        if track_id not in self._states:
            self._states[track_id] = TrackZoneState(track_id=track_id)

        state = self._states[track_id]
        prev_zone_id = state.current_zone_id
        curr_zone_id = pos.zone_id

        # ── Không có gì thay đổi ──────────────────────────────────────────────
        if prev_zone_id == curr_zone_id:
            # Vẫn ở cùng zone, chỉ update pending counter nếu có
            if curr_zone_id is not None and track_id in self._pending:
                self._pending[track_id]["frame_count"] += 1
                # Đủ min_frames → confirm ENTER
                if self._pending[track_id]["frame_count"] >= self.min_frames_in_zone:
                    pending = self._pending.pop(track_id)
                    events.append(ZoneEvent(
                        event_type="enter",
                        track_id=track_id,
                        zone_id=curr_zone_id,
                        timestamp=pending["timestamp"],
                        frame_index=pending["frame_index"],
                        x=pending["x"],
                        y=pending["y"],
                    ))
                    state.zone_entry_time = pending["timestamp"]
                    state.zone_entry_frame = pending["frame_index"]
                    # Ghi vào history
                    state.history.append({
                        "zone_id": curr_zone_id,
                        "enter_time": pending["timestamp"],
                        "enter_frame": pending["frame_index"],
                        "leave_time": None,
                        "leave_frame": None,
                    })
            return events

        # ── Zone thay đổi ─────────────────────────────────────────────────────

        # 1. EXIT zone cũ (nếu có)
        if prev_zone_id is not None:
            # Hủy pending nếu đang chờ confirm zone cũ
            self._pending.pop(track_id, None)

            # Generate EXIT event
            events.append(ZoneEvent(
                event_type="exit",
                track_id=track_id,
                zone_id=prev_zone_id,
                timestamp=pos.timestamp,
                frame_index=pos.frame_index,
                x=pos.x,
                y=pos.y,
            ))

            # Cập nhật leave_time trong history
            if state.history:
                last = state.history[-1]
                if last["zone_id"] == prev_zone_id and last["leave_time"] is None:
                    last["leave_time"] = pos.timestamp
                    last["leave_frame"] = pos.frame_index

            state.zone_entry_time = None
            state.zone_entry_frame = None

        # 2. ENTER zone mới (nếu có)
        if curr_zone_id is not None:
            if self.min_frames_in_zone <= 1:
                # Confirm ngay
                events.append(ZoneEvent(
                    event_type="enter",
                    track_id=track_id,
                    zone_id=curr_zone_id,
                    timestamp=pos.timestamp,
                    frame_index=pos.frame_index,
                    x=pos.x,
                    y=pos.y,
                ))
                state.zone_entry_time = pos.timestamp
                state.zone_entry_frame = pos.frame_index
                state.history.append({
                    "zone_id": curr_zone_id,
                    "enter_time": pos.timestamp,
                    "enter_frame": pos.frame_index,
                    "leave_time": None,
                    "leave_frame": None,
                })
            else:
                # Buffer: chờ đủ min_frames mới confirm
                self._pending[track_id] = {
                    "zone_id": curr_zone_id,
                    "timestamp": pos.timestamp,
                    "frame_index": pos.frame_index,
                    "x": pos.x,
                    "y": pos.y,
                    "frame_count": 1,
                }

        # Cập nhật state
        state.current_zone_id = curr_zone_id
        return events

    def finalize(self) -> list[ZoneEvent]:
        """
        Gọi sau khi video kết thúc — generate EXIT event cho tất cả
        track vẫn còn đang ở trong zone.
        """
        events: list[ZoneEvent] = []
        now = datetime.now()

        for track_id, state in self._states.items():
            if state.current_zone_id is not None:
                events.append(ZoneEvent(
                    event_type="exit",
                    track_id=track_id,
                    zone_id=state.current_zone_id,
                    timestamp=now,
                    frame_index=-1,  # -1 = end of video
                    x=0.0,
                    y=0.0,
                ))
                # Cập nhật leave_time trong history
                if state.history:
                    last = state.history[-1]
                    if last["zone_id"] == state.current_zone_id and last["leave_time"] is None:
                        last["leave_time"] = now
                        last["leave_frame"] = -1

        return events

    def get_zone_visit_summary(self) -> list[dict]:
        """
        Trả về tóm tắt zone visits của tất cả tracks.
        Dùng để lưu vào bảng zone_visits trong DB.
        """
        result = []
        for track_id, state in self._states.items():
            for visit in state.history:
                enter_time = visit.get("enter_time")
                leave_time = visit.get("leave_time")
                duration = None
                if enter_time and leave_time:
                    duration = int((leave_time - enter_time).total_seconds())

                result.append({
                    "track_id": track_id,
                    "zone_id": visit["zone_id"],
                    "enter_time": enter_time,
                    "leave_time": leave_time,
                    "enter_frame": visit.get("enter_frame"),
                    "leave_frame": visit.get("leave_frame"),
                    "duration_seconds": duration,
                })

        return result

    def get_all_events(self) -> list[ZoneEvent]:
        """Trả về tất cả events đã detect (để debug/log)."""
        return []  # Events được trả trực tiếp qua process_frame_positions()

    def get_track_state(self, track_id: int) -> Optional[TrackZoneState]:
        return self._states.get(track_id)


# ─── Singleton ────────────────────────────────────────────────────────────────
# Không dùng singleton vì mỗi video cần 1 instance riêng (stateful)
# Khởi tạo trong MovementTrackPipelineService
