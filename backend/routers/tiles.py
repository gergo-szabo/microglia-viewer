import math
from io import BytesIO

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse

from ..config import Settings
from ..dependencies import dep_file_registry, dep_frame_cache, dep_job_registry, dep_settings, dep_tile_cache
from ..models import DZIInfo
from ..services.file_registry import FileRegistry
from ..services.job_registry import JobRegistry
from ..services.nd2_loader import Nd2Loader
from ..services.tile_cache import FrameCache, TileCache
from ..utils import dzi as dzi_utils
from ..utils.image import build_overlay_rgba, encode_jpeg, encode_png_rgba, normalize_to_8bit, resize_region

router = APIRouter(prefix="/tiles", tags=["tiles"])
_loader = Nd2Loader()

TRANSPARENT_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01'
    b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)


def _get_frame(
    record,
    channel: int,
    t: int,
    z: int,
    frame_cache: FrameCache,
) -> np.ndarray:
    key = (record.id, channel, t, z)
    cached = frame_cache.get(key)
    if cached is not None:
        return cached
    frame = _loader.get_frame(record, channel, t, z)
    frame_cache.put(key, frame)
    return frame


def _get_tile_bytes(
    frame: np.ndarray,
    level: int,
    col: int,
    row: int,
    max_lvl: int,
    img_w: int,
    img_h: int,
    tile_size: int,
    quality: int,
) -> bytes:
    scale = 2 ** (max_lvl - level)
    tw, th = dzi_utils.tile_output_size(col, row, level, max_lvl, img_w, img_h, tile_size)

    if scale > 16:
        # Resize full frame, then crop tile
        out_w = max(math.ceil(img_w / scale), 1)
        out_h = max(math.ceil(img_h / scale), 1)
        small = cv2.resize(frame, (out_w, out_h), interpolation=cv2.INTER_LINEAR)
        x0_s = col * tile_size
        y0_s = row * tile_size
        x1_s = min(x0_s + tile_size, out_w)
        y1_s = min(y0_s + tile_size, out_h)
        region = small[y0_s:y1_s, x0_s:x1_s]
    else:
        x0, y0, x1, y1 = dzi_utils.tile_bounds_in_original(col, row, level, max_lvl, img_w, img_h, tile_size)
        region = frame[y0:y1, x0:x1]
        region = resize_region(region, tw, th)

    if region.dtype == np.uint16:
        region = normalize_to_8bit(region)
    elif region.dtype != np.uint8:
        region = normalize_to_8bit(region)

    return encode_jpeg(region, quality)


@router.get("/{file_id}/info.json", response_model=DZIInfo)
async def tile_info(
    file_id: str,
    channel: int = 0,
    t: int = 0,
    z: int = 0,
    registry: FileRegistry = Depends(dep_file_registry),
    settings: Settings = Depends(dep_settings),
) -> DZIInfo:
    record = registry.get(file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")
    img_w = record.sizes.get("X", 1)
    img_h = record.sizes.get("Y", 1)
    max_lvl = dzi_utils.max_level(img_w, img_h)
    return DZIInfo(
        width=img_w,
        height=img_h,
        tile_size=settings.TILE_SIZE,
        overlap=dzi_utils.OVERLAP,
        format="jpeg",
        max_level=max_lvl,
    )


@router.get("/{file_id}/dzi.xml")
async def tile_dzi_xml(
    file_id: str,
    channel: int = 0,
    t: int = 0,
    z: int = 0,
    registry: FileRegistry = Depends(dep_file_registry),
    settings: Settings = Depends(dep_settings),
) -> Response:
    record = registry.get(file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")
    img_w = record.sizes.get("X", 1)
    img_h = record.sizes.get("Y", 1)
    xml = dzi_utils.dzi_xml(img_w, img_h, settings.TILE_SIZE)
    return Response(content=xml, media_type="text/xml")


@router.get("/{file_id}/{level}/{col_row}.jpg")
async def tile_jpeg(
    file_id: str,
    level: int,
    col_row: str,
    channel: int = 0,
    t: int = 0,
    z: int = 0,
    registry: FileRegistry = Depends(dep_file_registry),
    tile_cache: TileCache = Depends(dep_tile_cache),
    frame_cache: FrameCache = Depends(dep_frame_cache),
    settings: Settings = Depends(dep_settings),
):
    record = registry.get(file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        col, row = map(int, col_row.split("_"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tile coordinates")

    img_w = record.sizes.get("X", 1)
    img_h = record.sizes.get("Y", 1)
    max_lvl = dzi_utils.max_level(img_w, img_h)

    cache_key = (file_id, channel, t, z, level, col, row, "base")
    cached = tile_cache.get(cache_key)
    if cached is not None:
        return Response(content=cached, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=3600"})

    frame = _get_frame(record, channel, t, z, frame_cache)
    jpeg_bytes = _get_tile_bytes(frame, level, col, row, max_lvl, img_w, img_h,
                                  settings.TILE_SIZE, settings.JPEG_QUALITY)
    tile_cache.put(cache_key, jpeg_bytes)
    return Response(content=jpeg_bytes, media_type="image/jpeg",
                    headers={"Cache-Control": "public, max-age=3600"})


@router.get("/{file_id}/overlay/{level}/{col_row}.png")
async def overlay_tile_png(
    file_id: str,
    level: int,
    col_row: str,
    channel: int = 0,
    t: int = 0,
    z: int = 0,
    masks: str = Query(default="branches,soma,nucleus"),
    registry: FileRegistry = Depends(dep_file_registry),
    job_registry: JobRegistry = Depends(dep_job_registry),
    tile_cache: TileCache = Depends(dep_tile_cache),
    settings: Settings = Depends(dep_settings),
):
    record = registry.get(file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        col, row = map(int, col_row.split("_"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tile coordinates")

    job = job_registry.get_completed_job_for_file(file_id)
    if job is None or job.result is None:
        return Response(content=TRANSPARENT_PNG, media_type="image/png")

    mask_set = {m.strip() for m in masks.split(",") if m.strip()}
    cache_key = (file_id, channel, t, z, level, col, row, "overlay", masks)
    cached = tile_cache.get(cache_key)
    if cached is not None:
        return Response(content=cached, media_type="image/png",
                        headers={"Cache-Control": "public, max-age=60"})

    seg_result = _load_seg_result(job.id, z, settings.RESULTS_DIR)
    if seg_result is None:
        return Response(content=TRANSPARENT_PNG, media_type="image/png")

    img_w = record.sizes.get("X", 1)
    img_h = record.sizes.get("Y", 1)
    max_lvl = dzi_utils.max_level(img_w, img_h)
    scale = 2 ** (max_lvl - level)
    tw, th = dzi_utils.tile_output_size(col, row, level, max_lvl, img_w, img_h, settings.TILE_SIZE)

    overlay_full = build_overlay_rgba(seg_result, (img_h, img_w), masks=mask_set)

    if scale > 16:
        out_w = max(math.ceil(img_w / scale), 1)
        out_h = max(math.ceil(img_h / scale), 1)
        small = cv2.resize(overlay_full, (out_w, out_h), interpolation=cv2.INTER_NEAREST)
        x0_s = col * settings.TILE_SIZE
        y0_s = row * settings.TILE_SIZE
        region = small[y0_s:min(y0_s + settings.TILE_SIZE, out_h),
                        x0_s:min(x0_s + settings.TILE_SIZE, out_w)]
    else:
        x0, y0, x1, y1 = dzi_utils.tile_bounds_in_original(col, row, level, max_lvl, img_w, img_h,
                                                              settings.TILE_SIZE)
        region = overlay_full[y0:y1, x0:x1]
        if region.shape[:2] != (th, tw):
            region = cv2.resize(region, (tw, th), interpolation=cv2.INTER_NEAREST)

    if region.size == 0:
        return Response(content=TRANSPARENT_PNG, media_type="image/png")
    png_bytes = encode_png_rgba(region)
    tile_cache.put(cache_key, png_bytes)
    return Response(content=png_bytes, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=60"})


def _load_seg_result(job_id: str, z: int, results_dir: str) -> dict | None:
    import pickle
    from pathlib import Path
    p = Path(results_dir) / job_id / "seg_results.pkl"
    if not p.exists():
        return None
    try:
        with open(p, "rb") as f:
            all_segs = pickle.load(f)
        return all_segs.get(z)
    except Exception:
        return None
