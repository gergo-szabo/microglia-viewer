from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .pipeline.segmentation import list_segmenters
from .pipeline.segmentation.unet import UNetSegmenter
from .pipeline.segmentation.yolo import YOLOSegmenter
from .routers.files import router as files_router
from .routers.jobs import router as jobs_router
from .routers.segmenters import router as segmenters_router
from .routers.tiles import router as tiles_router
from .services.file_registry import FileRegistry
from .services.job_registry import JobRegistry
from .services.tile_cache import FrameCache, TileCache


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    Path(settings.DATA_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.RESULTS_DIR).mkdir(parents=True, exist_ok=True)

    app.state.settings = settings
    app.state.file_registry = FileRegistry()
    app.state.job_registry = JobRegistry()
    app.state.tile_cache = TileCache(maxsize=settings.TILE_CACHE_MAXSIZE)
    app.state.frame_cache = FrameCache(maxsize=settings.FRAME_CACHE_MAXSIZE)
    app.state.executor = ThreadPoolExecutor(max_workers=settings.WORKER_THREADS)

    if settings.UNET_WEIGHTS_PATH:
        unet = UNetSegmenter()
        try:
            unet.load_weights(settings.UNET_WEIGHTS_PATH)
        except Exception as exc:
            print(f"[WARN] Could not load UNet weights: {exc}")

    if settings.YOLO_WEIGHTS_PATH:
        yolo = YOLOSegmenter()
        try:
            yolo.load_weights(settings.YOLO_WEIGHTS_PATH)
        except Exception as exc:
            print(f"[WARN] Could not load YOLO weights: {exc}")

    yield

    app.state.file_registry.close_all()
    app.state.executor.shutdown(wait=False)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Microglia Viewer",
        description="Browser-based nd2 microscopy viewer with AutoMD/YOLO segmentation",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(files_router, prefix="/api")
    app.include_router(tiles_router, prefix="/api")
    app.include_router(jobs_router, prefix="/api")
    app.include_router(segmenters_router, prefix="/api")

    frontend_dir = Path(__file__).parent.parent / "frontend"
    static_dir = frontend_dir / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/api/health")
    async def health():
        return {
            "status": "ok",
            "nd2_files_open": len(app.state.file_registry.list_all()),
            "jobs_total": len(app.state.job_registry.list_all()),
            "segmenters": list_segmenters(),
        }

    @app.get("/", include_in_schema=False)
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str = ""):
        index = frontend_dir / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return {"message": "Frontend not found. Place index.html in frontend/"}

    return app


app = create_app()
