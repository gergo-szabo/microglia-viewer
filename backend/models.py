from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class FileInfo(BaseModel):
    id: str
    filename: str
    sizes: dict[str, int]
    channels: list[str]
    pixel_microns: float | None
    z_step_um: float | None
    time_interval_s: float | None
    dtype: str
    upload_time: datetime


class JobCreateRequest(BaseModel):
    file_id: str
    channel_dapi: int = 0
    channel_alx: int = 1
    t: int = 0
    segmenter: str = "automd"
    segmenter_params: dict = {}


class JobStatus(BaseModel):
    id: str
    file_id: str
    status: Literal["queued", "running", "complete", "failed"]
    progress: int
    step: str | None = None
    message: str | None = None
    error: str | None = None
    created_at: datetime
    finished_at: datetime | None = None


class AnalysisResult(BaseModel):
    job_id: str
    optimal_z_start: int
    optimal_z_end: int
    resolution_metrics: list[float]
    vert_correlations: list[float]
    horiz_coherences: list[float]
    segmentation_available: bool
    segmenter_used: str


class SegmenterInfo(BaseModel):
    name: str
    available: bool
    description: str


class DZIInfo(BaseModel):
    width: int
    height: int
    tile_size: int
    overlap: int
    format: str
    max_level: int
