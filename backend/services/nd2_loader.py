import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import dask.array as da
import nd2
import numpy as np


@dataclass
class FileRecord:
    id: str
    filename: str
    path: str
    nd2_handle: nd2.ND2File
    dask_array: da.Array
    axis_order: list[str]
    sizes: dict[str, int]
    channels: list[str]
    pixel_microns: float | None
    z_step_um: float | None
    time_interval_s: float | None
    dtype: str
    upload_time: datetime
    lock: threading.Lock = field(default_factory=threading.Lock)


class Nd2Loader:

    def open(self, path: str) -> FileRecord:
        f = nd2.ND2File(path)
        dask_arr = f.to_dask()
        axis_order = list(f.sizes.keys())
        sizes = dict(f.sizes)

        channels = self._get_channel_names(f)
        pixel_microns, z_step_um, time_interval_s = self._get_spatial_metadata(f)

        return FileRecord(
            id=str(uuid.uuid4()),
            filename=Path(path).name,
            path=path,
            nd2_handle=f,
            dask_array=dask_arr,
            axis_order=axis_order,
            sizes=sizes,
            channels=channels,
            pixel_microns=pixel_microns,
            z_step_um=z_step_um,
            time_interval_s=time_interval_s,
            dtype=str(dask_arr.dtype),
            upload_time=datetime.utcnow(),
        )

    def get_frame(self, record: FileRecord, channel: int, t: int, z: int) -> np.ndarray:
        """Returns a single 2D (Y, X) frame as uint16 (or native dtype)."""
        axis = record.axis_order
        slices = [slice(None)] * len(axis)

        if "C" in axis:
            slices[axis.index("C")] = channel
        if "T" in axis and record.sizes.get("T", 1) > 1:
            slices[axis.index("T")] = t
        if "Z" in axis:
            slices[axis.index("Z")] = z

        with record.lock:
            frame = record.dask_array[tuple(slices)].compute()

        # Squeeze any remaining size-1 dims that aren't Y/X
        while frame.ndim > 2:
            frame = frame[0]

        return frame

    @staticmethod
    def _get_channel_names(f: nd2.ND2File) -> list[str]:
        try:
            meta = f.metadata
            if hasattr(meta, "channels") and meta.channels:
                return [ch.channel.name for ch in meta.channels]
        except Exception:
            pass
        n_channels = f.sizes.get("C", 1)
        return [f"CH{i}" for i in range(n_channels)]

    @staticmethod
    def _get_spatial_metadata(f: nd2.ND2File) -> tuple[float | None, float | None, float | None]:
        pixel_microns = z_step_um = time_interval_s = None
        try:
            vox = f.voxel_size()
            pixel_microns = float(vox.x) if vox.x else None
            z_step_um = float(vox.z) if hasattr(vox, "z") and vox.z else None
        except Exception:
            pass
        try:
            # frame_metadata gives per-frame timing; approximate from first two frames
            coords = list(f.frame_metadata().values())
            if len(coords) >= 2:
                t0 = coords[0].channels[0].time.absoluteJulianDayNumber if coords[0].channels else None
                t1 = coords[1].channels[0].time.absoluteJulianDayNumber if coords[1].channels else None
                if t0 is not None and t1 is not None:
                    time_interval_s = abs(float(t1) - float(t0)) * 86400.0
        except Exception:
            pass
        return pixel_microns, z_step_um, time_interval_s
