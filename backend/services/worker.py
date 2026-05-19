import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from ..models import JobCreateRequest
from ..pipeline.runner import PipelineRunner
from .file_registry import FileRegistry
from .job_registry import JobRegistry, JobRecord
from .tile_cache import TileCache


_runner = PipelineRunner()


async def submit_job(
    job: JobRecord,
    job_registry: JobRegistry,
    file_registry: FileRegistry,
    tile_cache: TileCache,
    results_dir: str,
    executor: ThreadPoolExecutor,
) -> None:
    loop = asyncio.get_event_loop()
    record = file_registry.get(job.file_id)
    if record is None:
        job_registry.update(job.id, status="failed", error=f"File {job.file_id} not found",
                            finished_at=datetime.utcnow())
        return

    def progress_cb(step: str, pct: int, msg: str) -> None:
        job_registry.update(job.id, step=step, progress=pct, message=msg, status="running")
        event = {"type": "progress", "step": step, "pct": pct, "message": msg}
        job_registry.emit_progress(job.id, event, loop)

    def run_sync() -> tuple:
        return _runner.run(
            file_record=record,
            channel_dapi=job.request.channel_dapi,
            channel_alx=job.request.channel_alx,
            t=job.request.t,
            segmenter_name=job.request.segmenter,
            segmenter_params=job.request.segmenter_params,
            job_id=job.id,
            results_dir=results_dir,
            progress_cb=progress_cb,
        )

    job_registry.update(job.id, status="running", progress=0, step="queued",
                        message="Starting analysis...")

    try:
        result, graphs = await loop.run_in_executor(executor, run_sync)
        job_registry.update(
            job.id,
            status="complete",
            progress=100,
            result=result,
            graphs=graphs,
            finished_at=datetime.utcnow(),
        )
        tile_cache.invalidate_file(job.file_id)
        event = {"type": "complete", "pct": 100, "data": result.model_dump()}
        job_registry.emit_progress(job.id, event, loop)
    except Exception as exc:
        import traceback
        err = f"{type(exc).__name__}: {exc}"
        job_registry.update(job.id, status="failed", error=err, finished_at=datetime.utcnow())
        event = {"type": "error", "message": err}
        job_registry.emit_progress(job.id, event, loop)
