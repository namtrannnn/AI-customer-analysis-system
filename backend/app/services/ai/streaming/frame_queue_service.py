from __future__ import annotations

from queue import Queue, Empty, Full
from threading import Event, Lock
from typing import Optional

from .streaming_dtos import FramePacket


class SequentialFrameQueueService:
    """AI-02: queue FIFO bảo đảm frame được lấy ra theo thứ tự đưa vào."""

    def __init__(self, maxsize: int = 64) -> None:
        if maxsize <= 0:
            raise ValueError("maxsize must be > 0")
        self._queue: Queue[FramePacket] = Queue(maxsize=maxsize)
        self._closed = Event()
        self._last_enqueued_index = -1
        self._last_dequeued_index = -1
        self._lock = Lock()

    def put(self, packet: FramePacket, timeout: float = 1.0) -> None:
        if self._closed.is_set():
            raise RuntimeError("frame queue is closed")
        with self._lock:
            if packet.frame_index <= self._last_enqueued_index:
                raise ValueError(
                    f"frame order violation: {packet.frame_index} <= {self._last_enqueued_index}"
                )
            self._last_enqueued_index = packet.frame_index
        try:
            self._queue.put(packet, timeout=timeout)
        except Full as exc:
            raise TimeoutError("frame queue is full") from exc

    def get(self, timeout: float = 0.25) -> Optional[FramePacket]:
        while True:
            if self._closed.is_set() and self._queue.empty():
                return None
            try:
                packet = self._queue.get(timeout=timeout)
            except Empty:
                if self._closed.is_set():
                    return None
                continue

            with self._lock:
                if packet.frame_index <= self._last_dequeued_index:
                    self._queue.task_done()
                    raise RuntimeError(
                        f"dequeue order violation: {packet.frame_index} <= {self._last_dequeued_index}"
                    )
                self._last_dequeued_index = packet.frame_index
            return packet

    def task_done(self) -> None:
        self._queue.task_done()

    def join(self) -> None:
        self._queue.join()

    def close(self) -> None:
        self._closed.set()

    @property
    def size(self) -> int:
        return self._queue.qsize()

    @property
    def closed(self) -> bool:
        return self._closed.is_set()
