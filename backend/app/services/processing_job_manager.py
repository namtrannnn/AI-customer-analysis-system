import asyncio
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ProcessingJobState:
    job_id: str
    file_name: str
    temp_video_path: str
    status: str = "pending"
    progress: dict[str, Any] | None = None
    error: str | None = None
    result: dict[str, Any] | None = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    subscribers: list[asyncio.Queue] = field(default_factory=list)
    recent_events: list[dict[str, Any]] = field(default_factory=list)
    person_session_map: dict[str, int] = field(default_factory=dict)

    def snapshot(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "file_name": self.file_name,
            "status": self.status,
            "progress": self.progress,
            "error": self.error,
            "result": self.result,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class ProcessingJobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, ProcessingJobState] = {}
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self) -> None:
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

    async def create_job(self, file_name: str, temp_video_path: str) -> ProcessingJobState:
        async with self._lock:
            job_id = str(uuid.uuid4())
            job = ProcessingJobState(
                job_id=job_id,
                file_name=file_name,
                temp_video_path=temp_video_path,
            )
            self._jobs[job_id] = job
            return job

    def get_job(self, job_id: str) -> ProcessingJobState | None:
        return self._jobs.get(job_id)

    async def subscribe(self, job_id: str) -> asyncio.Queue | None:
        job = self.get_job(job_id)
        if not job:
            return None
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        job.subscribers.append(queue)
        for event in job.recent_events[-50:]:
            await queue.put(event)
        if job.status == "completed" and job.result is not None:
            await queue.put({"type": "complete", "data": job.result})
        elif job.status == "failed":
            await queue.put({"type": "error", "message": job.error or "Processing failed"})
        return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        job = self.get_job(job_id)
        if not job:
            return
        if queue in job.subscribers:
            job.subscribers.remove(queue)

    def mark_running(self, job_id: str) -> None:
        job = self.get_job(job_id)
        if not job:
            return
        job.status = "running"
        job.started_at = datetime.now()

    def mark_completed(self, job_id: str, result: dict[str, Any]) -> None:
        job = self.get_job(job_id)
        if not job:
            return
        job.status = "completed"
        job.result = result
        job.finished_at = datetime.now()
        self.publish(job_id, {"type": "complete", "data": result})

    def mark_failed(self, job_id: str, error: str) -> None:
        job = self.get_job(job_id)
        if not job:
            return
        job.status = "failed"
        job.error = error
        job.finished_at = datetime.now()
        self.publish(job_id, {"type": "error", "message": error})

    def update_progress(self, job_id: str, progress: dict[str, Any]) -> None:
        job = self.get_job(job_id)
        if not job:
            return
        job.progress = progress
        self.publish(job_id, {"type": "progress", "data": progress})

    def publish(self, job_id: str, event: dict[str, Any]) -> None:
        job = self.get_job(job_id)
        if not job:
            return
        job.recent_events.append(event)
        if len(job.recent_events) > 200:
            job.recent_events = job.recent_events[-200:]
        for queue in list(job.subscribers):
            self._put_event(queue, event)

    def cleanup_temp_file(self, job_id: str) -> None:
        job = self.get_job(job_id)
        if not job:
            return
        path = job.temp_video_path
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

    def _put_event(self, queue: asyncio.Queue, event: dict[str, Any]) -> None:
        def put_now() -> None:
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(event)

        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(put_now)


processing_job_manager = ProcessingJobManager()
