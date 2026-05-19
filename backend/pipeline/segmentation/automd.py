import cv2
import numpy as np

from .base import SegmentationBackend


class AutoMDSegmenter(SegmentationBackend):
    name = "automd"
    description = "Classical CV: Otsu threshold + morphological opening + distance transform (AutoMD baseline)"

    def is_available(self) -> bool:
        return True

    def segment(self, img_8bit: np.ndarray, params: dict) -> dict:
        open_iters = int(params.get("open_iterations", 7))
        soma_frac = float(params.get("soma_fraction", 0.20))
        nucleus_frac = float(params.get("nucleus_fraction", 0.50))

        # Branches: Otsu threshold — bright pixels = processes
        otsu_val, branches = cv2.threshold(
            img_8bit, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

        # Soma base: morphological opening removes thin branches, leaves cell bodies
        kernel = np.ones((3, 3), np.uint8)
        soma_base = cv2.morphologyEx(branches, cv2.MORPH_OPEN, kernel, iterations=open_iters)

        # Distance transform on soma regions
        dist = cv2.distanceTransform(soma_base, cv2.DIST_L2, 5)
        max_dist = float(dist.max())

        soma = np.zeros(img_8bit.shape, dtype=np.uint8)
        nucleus = np.zeros(img_8bit.shape, dtype=np.uint8)
        if max_dist > 0:
            soma[dist > soma_frac * max_dist] = 255
            nucleus[dist > nucleus_frac * max_dist] = 255

        return {
            "branches": branches,
            "soma": soma,
            "nucleus": nucleus,
            "metadata": {
                "otsu_threshold": int(otsu_val),
                "max_dist": max_dist,
                "open_iterations": open_iters,
            },
        }
