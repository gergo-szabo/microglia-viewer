from pathlib import Path

import cv2
import numpy as np

from .base import SegmentationBackend

_INPUT_SIZE = 512
# Conv2D layer names as stored in the .h5 checkpoint (determined from weight shapes)
_SAVED_CONV_NAMES = [
    "conv2d_20", "conv2d_21", "conv2d_22", "conv2d_23",
    "conv2d_24", "conv2d_25", "conv2d_26", "conv2d_27",
    "conv2d_28", "conv2d_29", "conv2d_30", "conv2d_31",
    "conv2d_32", "conv2d_33", "conv2d_34", "conv2d_35",
    "conv2d_36", "conv2d_37", "conv2d_38",
]


def _build_unet(n_classes: int = 3):
    """
    Architecture reconstructed from weight shapes in the checkpoint.

    Encoder filter progression: 64/32 → 64 → 128 → 256 (bottleneck: 512)
    First block uses a custom swish-like activation: 0.5*(relu(x) + sigmoid(x))
    """
    import tensorflow as tf
    from tensorflow.keras import layers, models

    size = _INPUT_SIZE
    inputs = layers.Input((size, size, 3))

    # Block 1: custom activation, 3→64→32
    x = layers.Conv2D(64, 3, activation=None, padding="same",
                      kernel_initializer="he_normal")(inputs)
    c1 = layers.Conv2D(32, 3, activation="swish", padding="same",
                       kernel_initializer="he_normal")(
        layers.Lambda(lambda t: 0.5 * (tf.nn.relu(t[0]) + tf.nn.sigmoid(t[1])))([x, x])
    )
    p1 = layers.MaxPooling2D()(c1)

    # Block 2: 32→64→64
    x2 = layers.Conv2D(64, 3, activation=None, padding="same",
                       kernel_initializer="he_normal")(p1)
    c2 = layers.Conv2D(64, 3, activation="swish", padding="same",
                       kernel_initializer="he_normal")(x2)
    p2 = layers.MaxPooling2D()(c2)

    # Block 3: 64→128→128
    x3 = layers.Conv2D(128, 3, activation=None, padding="same",
                       kernel_initializer="he_normal")(p2)
    c3 = layers.Conv2D(128, 3, activation="swish", padding="same",
                       kernel_initializer="he_normal")(x3)
    p3 = layers.MaxPooling2D()(c3)

    # Block 4: 128→256→256
    x4 = layers.Conv2D(256, 3, activation=None, padding="same",
                       kernel_initializer="he_normal")(p3)
    c4 = layers.Conv2D(256, 3, activation="swish", padding="same",
                       kernel_initializer="he_normal")(x4)
    p4 = layers.MaxPooling2D()(c4)

    # Bottleneck: 256→512→512
    x5 = layers.Conv2D(512, 3, activation=None, padding="same",
                       kernel_initializer="he_normal")(p4)
    c5 = layers.Conv2D(512, 3, activation="swish", padding="same",
                       kernel_initializer="he_normal")(x5)

    # Decoder block 1: upsample+cat(512,256)→768→256→256
    u6 = layers.concatenate([layers.UpSampling2D()(c5), c4])
    x6 = layers.Conv2D(256, 3, activation=None, padding="same",
                       kernel_initializer="he_normal")(u6)
    c6 = layers.Conv2D(256, 3, activation="swish", padding="same",
                       kernel_initializer="he_normal")(x6)

    # Decoder block 2: upsample+cat(256,128)→384→128→128
    u7 = layers.concatenate([layers.UpSampling2D()(c6), c3])
    x7 = layers.Conv2D(128, 3, activation=None, padding="same",
                       kernel_initializer="he_normal")(u7)
    c7 = layers.Conv2D(128, 3, activation="swish", padding="same",
                       kernel_initializer="he_normal")(x7)

    # Decoder block 3: upsample+cat(128,64)→192→64→64
    u8 = layers.concatenate([layers.UpSampling2D()(c7), c2])
    x8 = layers.Conv2D(64, 3, activation=None, padding="same",
                       kernel_initializer="he_normal")(u8)
    c8 = layers.Conv2D(64, 3, activation="swish", padding="same",
                       kernel_initializer="he_normal")(x8)

    # Decoder block 4: upsample+cat(64,32)→96→32→32
    u9 = layers.concatenate([layers.UpSampling2D()(c8), c1])
    x9 = layers.Conv2D(32, 3, activation=None, padding="same",
                       kernel_initializer="he_normal")(u9)
    c9 = layers.Conv2D(32, 3, activation="swish", padding="same",
                       kernel_initializer="he_normal")(x9)

    # Output: 32→3
    outputs = layers.Conv2D(n_classes, 1, activation="softmax")(c9)

    return models.Model(inputs, outputs)


def _load_weights_from_checkpoint(model, weights_path: str) -> None:
    """Load Conv2D weights from a full-model h5 checkpoint using h5py."""
    import h5py

    conv_layers = [l for l in model.layers
                   if l.__class__.__name__ == "Conv2D"]
    assert len(conv_layers) == len(_SAVED_CONV_NAMES), (
        f"Expected {len(_SAVED_CONV_NAMES)} Conv2D layers, got {len(conv_layers)}"
    )

    with h5py.File(weights_path, "r") as f:
        mw = f["model_weights"]
        for layer, saved_name in zip(conv_layers, _SAVED_CONV_NAMES):
            grp = mw[saved_name][saved_name]
            kernel = grp["kernel"][()]
            bias = grp["bias"][()]
            layer.set_weights([kernel, bias])


class UNetSegmenter(SegmentationBackend):
    """
    UNet semantic segmentation (TensorFlow/Keras).

    Class convention (matches training color-sort encoding):
        class 0 → background
        class 1 → branches / processes
        class 2 → soma / cell body

    Load weights before use:
        segmenter = UNetSegmenter()
        segmenter.load_weights("/path/to/unet.h5")
    """

    name = "unet"
    description = "UNet semantic segmentation (requires TensorFlow + trained weights)"

    _model = None
    _weights_path: str | None = None

    def is_available(self) -> bool:
        try:
            import tensorflow  # noqa: F401
        except ImportError:
            return False
        return type(self)._model is not None

    def load_weights(self, weights_path: str) -> None:
        if not Path(weights_path).exists():
            raise FileNotFoundError(f"UNet weights not found: {weights_path}")
        model = _build_unet()
        _load_weights_from_checkpoint(model, weights_path)
        type(self)._model = model
        type(self)._weights_path = weights_path

    def segment(self, img_8bit: np.ndarray, params: dict) -> dict:
        model = type(self)._model
        if model is None:
            raise RuntimeError("UNet weights not loaded. Call load_weights() first.")

        orig_h, orig_w = img_8bit.shape
        img_rgb = cv2.cvtColor(img_8bit, cv2.COLOR_GRAY2RGB)
        img_resized = cv2.resize(img_rgb, (_INPUT_SIZE, _INPUT_SIZE))
        img_norm = img_resized.astype(np.float32) / 255.0

        pred = model.predict(np.expand_dims(img_norm, axis=0), verbose=0)
        pred_mask = np.argmax(pred[0], axis=-1)

        def _mask(cls_idx: int) -> np.ndarray:
            m = (pred_mask == cls_idx).astype(np.uint8) * 255
            if m.shape != (orig_h, orig_w):
                m = cv2.resize(m, (orig_w, orig_h), interpolation=cv2.INTER_NEAREST)
            return m

        return {
            "branches": _mask(1),
            "soma": _mask(2),
            "nucleus": np.zeros(img_8bit.shape, dtype=np.uint8),
            "metadata": {"model": type(self)._weights_path},
        }
