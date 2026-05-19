import threading
from collections import OrderedDict

import numpy as np


class TileCache:
    """LRU cache for encoded tile bytes (JPEG/PNG)."""

    def __init__(self, maxsize: int = 1024):
        self._cache: OrderedDict[tuple, bytes] = OrderedDict()
        self._maxsize = maxsize
        self._lock = threading.Lock()

    def get(self, key: tuple) -> bytes | None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        return None

    def put(self, key: tuple, data: bytes) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            else:
                if len(self._cache) >= self._maxsize:
                    self._cache.popitem(last=False)
            self._cache[key] = data

    def invalidate_file(self, file_id: str) -> None:
        with self._lock:
            keys = [k for k in self._cache if k[0] == file_id]
            for k in keys:
                del self._cache[k]


class FrameCache:
    """LRU cache for raw uint16 frames to avoid repeated nd2 reads."""

    def __init__(self, maxsize: int = 20):
        self._cache: OrderedDict[tuple, np.ndarray] = OrderedDict()
        self._maxsize = maxsize
        self._lock = threading.Lock()

    def get(self, key: tuple) -> np.ndarray | None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        return None

    def put(self, key: tuple, frame: np.ndarray) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            else:
                if len(self._cache) >= self._maxsize:
                    self._cache.popitem(last=False)
            self._cache[key] = frame

    def invalidate_file(self, file_id: str) -> None:
        with self._lock:
            keys = [k for k in self._cache if k[0] == file_id]
            for k in keys:
                del self._cache[k]
