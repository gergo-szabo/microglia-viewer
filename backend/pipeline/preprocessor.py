import cv2
import numpy as np


class ImagePreProcessor:

    def process_stack(self, stack_16: np.ndarray, contrast_level: int = 150) -> np.ndarray:
        """Input: (Z, Y, X) uint16. Output: (Z, Y, X) uint8."""
        result = np.empty(stack_16.shape, dtype=np.uint8)
        for z in range(stack_16.shape[0]):
            result[z] = self.process_slice(stack_16[z], contrast_level=contrast_level)
        return result

    def process_slice(self, img16: np.ndarray, contrast_level: int = 150) -> np.ndarray:
        img8 = self._to_8bit(img16)
        img8 = self._contrast_stretch(img8, level=contrast_level)
        img8 = cv2.medianBlur(img8, 5)
        return img8

    @staticmethod
    def _to_8bit(img16: np.ndarray) -> np.ndarray:
        mn, mx = img16.min(), img16.max()
        if mx == mn:
            return np.zeros_like(img16, dtype=np.uint8)
        return ((img16.astype(np.float32) - mn) / (mx - mn) * 255).clip(0, 255).astype(np.uint8)

    @staticmethod
    def _contrast_stretch(img8: np.ndarray, level: int = 150) -> np.ndarray:
        factor = (259.0 * (level + 255)) / (255.0 * (259 - level))
        stretched = factor * (img8.astype(np.float32) - 128.0) + 128.0
        return np.clip(stretched, 0, 255).astype(np.uint8)
