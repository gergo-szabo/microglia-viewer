from pathlib import Path

import cv2
import numpy as np

from .base import SegmentationBackend


class YOLOSegmenter(SegmentationBackend):
    """
    YOLO-based instance segmentation. Requires ultralytics package + trained weights.

    Class convention (must match training):
        class 0 → branches / processes
        class 1 → soma / cell body
        class 2 → nucleus

    Load weights before use:
        segmenter = YOLOSegmenter()
        segmenter.load_weights("/path/to/best.pt")
    """

    name = "yolo"
    description = "YOLO instance segmentation (requires ultralytics + trained weights)"

    _model = None
    _weights_path: str | None = None

    def is_available(self) -> bool:
        try:
            import ultralytics  # noqa: F401
        except ImportError:
            return False
        return self._model is not None

    def load_weights(self, weights_path: str) -> None:
        from ultralytics import YOLO
        if not Path(weights_path).exists():
            raise FileNotFoundError(f"YOLO weights not found: {weights_path}")
        self._model = YOLO(weights_path)
        self._weights_path = weights_path

    def segment(self, img_8bit: np.ndarray, params: dict) -> dict:
        if self._model is None:
            raise RuntimeError("YOLO weights not loaded. Call load_weights() first.")

        conf = float(params.get("conf", 0.5))
        img_rgb = cv2.cvtColor(img_8bit, cv2.COLOR_GRAY2RGB)
        results = self._model(img_rgb, conf=conf, verbose=False)

        branches = np.zeros(img_8bit.shape, dtype=np.uint8)
        soma = np.zeros(img_8bit.shape, dtype=np.uint8)
        nucleus = np.zeros(img_8bit.shape, dtype=np.uint8)

        for result in results:
            if result.masks is None:
                continue
            masks = result.masks.data.cpu().numpy()
            classes = result.boxes.cls.cpu().numpy()
            for mask, cls in zip(masks, classes):
                m = (mask > 0.5).astype(np.uint8) * 255
                if m.shape != img_8bit.shape:
                    m = cv2.resize(m, (img_8bit.shape[1], img_8bit.shape[0]),
                                   interpolation=cv2.INTER_NEAREST)
                if int(cls) == 0:
                    branches = np.maximum(branches, m)
                elif int(cls) == 1:
                    soma = np.maximum(soma, m)
                elif int(cls) == 2:
                    nucleus = np.maximum(nucleus, m)

        return {
            "branches": branches,
            "soma": soma,
            "nucleus": nucleus,
            "metadata": {"model": self._weights_path, "conf": conf},
        }
