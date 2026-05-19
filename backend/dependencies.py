from fastapi import Request

from .config import Settings, get_settings
from .services.file_registry import FileRegistry
from .services.job_registry import JobRegistry
from .services.tile_cache import FrameCache, TileCache


def _state(request: Request):
    return request.app.state


def dep_file_registry(request: Request) -> FileRegistry:
    return request.app.state.file_registry


def dep_job_registry(request: Request) -> JobRegistry:
    return request.app.state.job_registry


def dep_tile_cache(request: Request) -> TileCache:
    return request.app.state.tile_cache


def dep_frame_cache(request: Request) -> FrameCache:
    return request.app.state.frame_cache


def dep_settings(request: Request) -> Settings:
    return request.app.state.settings
