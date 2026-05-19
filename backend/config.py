from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MICROGLIA_")

    DATA_DIR: str = "./data"
    RESULTS_DIR: str = "./results"

    TILE_CACHE_MAXSIZE: int = 1024
    FRAME_CACHE_MAXSIZE: int = 20
    TILE_SIZE: int = 256
    JPEG_QUALITY: int = 85

    MAX_UPLOAD_MB: int = 4096
    WORKER_THREADS: int = 4

    CORS_ORIGINS: list[str] = ["*"]

    UNET_WEIGHTS_PATH: str | None = "backend/models/unet.h5"
    YOLO_WEIGHTS_PATH: str | None = None


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
