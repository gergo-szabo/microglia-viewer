import asyncio
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..models import AnalysisResult, JobCreateRequest, JobStatus


@dataclass
class JobRecord:
    id: str
    file_id: str
    request: JobCreateRequest
    status: str = "queued"
    progress: int = 0
    step: str | None = None
    message: str | None = None
    error: str | None = None
    result: AnalysisResult | None = None
    graphs: dict[str, str] | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None
    _sse_queues: list[asyncio.Queue] = field(default_factory=list)

    def to_status(self) -> JobStatus:
        return JobStatus(
            id=self.id,
            file_id=self.file_id,
            status=self.status,  # type: ignore[arg-type]
            progress=self.progress,
            step=self.step,
            message=self.message,
            error=self.error,
            created_at=self.created_at,
            finished_at=self.finished_at,
        )


class JobRegistry:

    def __init__(self):
        self._records: dict[str, JobRecord] = {}
        self._lock = threading.Lock()

    def create(self, request: JobCreateRequest) -> JobRecord:
        job_id = str(uuid.uuid4())
        record = JobRecord(id=job_id, file_id=request.file_id, request=request)
        with self._lock:
            self._records[job_id] = record
        return record

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._records.get(job_id)

    def list_all(self) -> list[JobRecord]:
        with self._lock:
            return list(self._records.values())

    def update(self, job_id: str, **kwargs: Any) -> None:
        with self._lock:
            record = self._records.get(job_id)
            if record is None:
                return
            for k, v in kwargs.items():
                setattr(record, k, v)

    def emit_progress(self, job_id: str, event: dict, loop: asyncio.AbstractEventLoop) -> None:
        with self._lock:
            record = self._records.get(job_id)
            if record is None:
                return
            queues = list(record._sse_queues)
        for q in queues:
            try:
                loop.call_soon_threadsafe(q.put_nowait, event)
            except Exception:
                pass

    def subscribe_sse(self, job_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        with self._lock:
            record = self._records.get(job_id)
            if record:
                record._sse_queues.append(q)
        return q

    def unsubscribe_sse(self, job_id: str, q: asyncio.Queue) -> None:
        with self._lock:
            record = self._records.get(job_id)
            if record and q in record._sse_queues:
                record._sse_queues.remove(q)

    def get_completed_job_for_file(self, file_id: str) -> JobRecord | None:
        with self._lock:
            completed = [
                r for r in self._records.values()
                if r.file_id == file_id and r.status == "complete"
            ]
        if not completed:
            return None
        return max(completed, key=lambda r: r.finished_at or datetime.min)
