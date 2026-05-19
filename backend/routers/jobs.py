import asyncio
import base64
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from ..config import Settings
from ..dependencies import dep_file_registry, dep_job_registry, dep_settings, dep_tile_cache
from ..models import AnalysisResult, JobCreateRequest, JobStatus
from ..pipeline.segmentation import list_segmenters
from ..services.file_registry import FileRegistry
from ..services.job_registry import JobRegistry
from ..services.tile_cache import TileCache
from ..services.worker import submit_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobStatus, status_code=status.HTTP_201_CREATED)
async def create_job(
    request_body: JobCreateRequest,
    request: Request,
    file_registry: FileRegistry = Depends(dep_file_registry),
    job_registry: JobRegistry = Depends(dep_job_registry),
    tile_cache: TileCache = Depends(dep_tile_cache),
    settings: Settings = Depends(dep_settings),
) -> JobStatus:
    if file_registry.get(request_body.file_id) is None:
        raise HTTPException(status_code=404, detail="File not found")

    available = {s["name"] for s in list_segmenters() if s["available"]}
    if request_body.segmenter not in available:
        raise HTTPException(
            status_code=400,
            detail=f"Segmenter {request_body.segmenter!r} not available. Available: {sorted(available)}"
        )

    job = job_registry.create(request_body)

    executor = request.app.state.executor
    asyncio.create_task(
        submit_job(
            job=job,
            job_registry=job_registry,
            file_registry=file_registry,
            tile_cache=tile_cache,
            results_dir=settings.RESULTS_DIR,
            executor=executor,
        )
    )
    return job.to_status()


@router.get("", response_model=list[JobStatus])
async def list_jobs(job_registry: JobRegistry = Depends(dep_job_registry)) -> list[JobStatus]:
    return [j.to_status() for j in job_registry.list_all()]


@router.get("/{job_id}", response_model=JobStatus)
async def get_job(
    job_id: str,
    job_registry: JobRegistry = Depends(dep_job_registry),
) -> JobStatus:
    job = job_registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_status()


@router.get("/{job_id}/results", response_model=AnalysisResult)
async def get_results(
    job_id: str,
    job_registry: JobRegistry = Depends(dep_job_registry),
) -> AnalysisResult:
    job = job_registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "complete":
        raise HTTPException(status_code=409, detail=f"Job not complete (status={job.status})")
    return job.result


@router.get("/{job_id}/graphs/{graph_name}")
async def get_graph(
    job_id: str,
    graph_name: str,
    job_registry: JobRegistry = Depends(dep_job_registry),
):
    valid_names = {"resolution", "correlations", "coherences"}
    if graph_name not in valid_names:
        raise HTTPException(status_code=400, detail=f"Unknown graph: {graph_name!r}")
    job = job_registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "complete" or not job.graphs:
        raise HTTPException(status_code=409, detail="Job not complete")
    b64 = job.graphs.get(graph_name)
    if not b64:
        raise HTTPException(status_code=404, detail=f"Graph {graph_name!r} not available")
    png_bytes = base64.b64decode(b64)
    return StreamingResponse(iter([png_bytes]), media_type="image/png")


@router.get("/{job_id}/progress")
async def job_progress(
    job_id: str,
    job_registry: JobRegistry = Depends(dep_job_registry),
) -> EventSourceResponse:
    job = job_registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_stream():
        if job.status in ("complete", "failed"):
            event_type = "complete" if job.status == "complete" else "error"
            data = {"type": event_type, "pct": job.progress,
                    "message": job.message or job.error or ""}
            if job.status == "complete" and job.result:
                data["data"] = job.result.model_dump()
            yield {"event": event_type, "data": json.dumps(data)}
            return

        q = job_registry.subscribe_sse(job_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30.0)
                    yield {"event": event["type"], "data": json.dumps(event)}
                    if event["type"] in ("complete", "error"):
                        break
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}
        finally:
            job_registry.unsubscribe_sse(job_id, q)

    return EventSourceResponse(event_stream())
