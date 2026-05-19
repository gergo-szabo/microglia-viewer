from abc import ABC, abstractmethod

import numpy as np


class SegmentationBackend(ABC):

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def segment(self, img_8bit: np.ndarray, params: dict) -> dict:
        """
        Args:
            img_8bit: 2D (H, W) uint8 grayscale image
            params: backend-specific parameters

        Returns dict with keys:
            branches: np.ndarray (H, W) uint8  — process/branch mask
            soma:     np.ndarray (H, W) uint8  — soma/cell body mask
            nucleus:  np.ndarray (H, W) uint8  — nucleus mask
            metadata: dict
        """
        ...
