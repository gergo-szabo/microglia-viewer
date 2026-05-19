import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from ..config import Settings
from ..dependencies import dep_file_registry, dep_settings, dep_tile_cache
from ..models import FileInfo
from ..services.file_registry import FileRegistry
from ..services.nd2_loader import Nd2Loader
from ..services.tile_cache import TileCache

router = APIRouter(prefix="/files", tags=["files"])
_loader = Nd2Loader()


def _record_to_info(record) -> FileInfo:
    return FileInfo(
        id=record.id,
        filename=record.filename,
        sizes=record.sizes,
        channels=record.channels,
        pixel_microns=record.pixel_microns,
        z_step_um=record.z_step_um,
        time_interval_s=record.time_interval_s,
        dtype=record.dtype,
        upload_time=record.upload_time,
    )


@router.post("/upload", response_model=FileInfo, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile,
    registry: FileRegistry = Depends(dep_file_registry),
    settings: Settings = Depends(dep_settings),
) -> FileInfo:
    if not (file.filename or "").lower().endswith(".nd2"):
        raise HTTPException(status_code=400, detail="Only .nd2 files are supported")

    data_dir = Path(settings.DATA_DIR)
    file_id = str(uuid.uuid4())
    dest_dir = data_dir / file_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / (file.filename or "upload.nd2")

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    written = 0
    async with aiofiles.open(dest, "wb") as f:
        while chunk := file.file.read(65536):
            written += len(chunk)
            if written > max_bytes:
                await f.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=413,
                                    detail=f"File exceeds {settings.MAX_UPLOAD_MB} MB limit")
            await f.write(chunk)

    try:
        record = _loader.open(str(dest))
        record.id = file_id
        registry.register(record)
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Failed to open nd2 file: {exc}") from exc

    return _record_to_info(record)


@router.get("", response_model=list[FileInfo])
async def list_files(registry: FileRegistry = Depends(dep_file_registry)) -> list[FileInfo]:
    return [_record_to_info(r) for r in registry.list_all()]


@router.get("/{file_id}", response_model=FileInfo)
async def get_file(
    file_id: str,
    registry: FileRegistry = Depends(dep_file_registry),
) -> FileInfo:
    record = registry.get(file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")
    return _record_to_info(record)


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: str,
    registry: FileRegistry = Depends(dep_file_registry),
    tile_cache: TileCache = Depends(dep_tile_cache),
) -> None:
    if registry.get(file_id) is None:
        raise HTTPException(status_code=404, detail="File not found")
    tile_cache.invalidate_file(file_id)
    registry.delete(file_id)
