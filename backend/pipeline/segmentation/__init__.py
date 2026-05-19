from .base import SegmentationBackend
from .automd import AutoMDSegmenter
from .yolo import YOLOSegmenter

_REGISTRY: dict[str, type[SegmentationBackend]] = {
    "automd": AutoMDSegmenter,
    "yolo": YOLOSegmenter,
}


def get_segmenter(name: str) -> SegmentationBackend:
    cls = _REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unknown segmenter: {name!r}. Available: {list(_REGISTRY)}")
    instance = cls()
    if not instance.is_available():
        raise RuntimeError(f"Segmenter {name!r} is not available in this environment.")
    return instance


def list_segmenters() -> list[dict]:
    result = []
    for name, cls in _REGISTRY.items():
        inst = cls()
        result.append({"name": name, "available": inst.is_available(), "description": inst.description})
    return result


def register_segmenter(name: str, cls: type[SegmentationBackend]) -> None:
    _REGISTRY[name] = cls
