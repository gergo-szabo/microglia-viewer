import io

import cv2
import numpy as np
from PIL import Image


def encode_jpeg(img: np.ndarray, quality: int = 85) -> bytes:
    if img.dtype == np.uint16:
        img = (img >> 8).astype(np.uint8)
    elif img.dtype != np.uint8:
        img = img.astype(np.uint8)
    ret, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ret:
        raise RuntimeError("JPEG encoding failed")
    return buf.tobytes()


def encode_png_rgba(rgba: np.ndarray) -> bytes:
    img_pil = Image.fromarray(rgba, "RGBA")
    buf = io.BytesIO()
    img_pil.save(buf, format="PNG", optimize=False)
    return buf.getvalue()


def build_overlay_rgba(
    seg_result: dict,
    shape: tuple[int, int],
    masks: set[str] | None = None,
) -> np.ndarray:
    """Compose RGBA overlay from segmentation masks (branches=green, soma=red, nucleus=cyan)."""
    overlay = np.zeros((*shape, 4), dtype=np.uint8)
    if (masks is None or "branches" in masks) and seg_result.get("branches") is not None:
        overlay[seg_result["branches"] > 0] = [0, 204, 0, 180]
    if (masks is None or "soma" in masks) and seg_result.get("soma") is not None:
        overlay[seg_result["soma"] > 0] = [255, 0, 0, 200]
    if (masks is None or "nucleus" in masks) and seg_result.get("nucleus") is not None:
        overlay[seg_result["nucleus"] > 0] = [0, 255, 255, 220]
    return overlay


def resize_region(region: np.ndarray, tw: int, th: int) -> np.ndarray:
    if region.shape[0] == th and region.shape[1] == tw:
        return region
    return cv2.resize(region, (tw, th), interpolation=cv2.INTER_LINEAR)


def normalize_to_8bit(img: np.ndarray) -> np.ndarray:
    """Min-max normalize any dtype to uint8."""
    mn = float(img.min())
    mx = float(img.max())
    if mx == mn:
        return np.zeros_like(img, dtype=np.uint8)
    return ((img.astype(np.float32) - mn) / (mx - mn) * 255).clip(0, 255).astype(np.uint8)
