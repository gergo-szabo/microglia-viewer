import base64
import io
from collections.abc import Callable
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from ..models import AnalysisResult
from .preprocessor import ImagePreProcessor
from .segmentation import get_segmenter
from .stack_analyser import StackAnalyser


class PipelineRunner:

    def __init__(self):
        self.preprocessor = ImagePreProcessor()
        self.stack_analyser = StackAnalyser()

    def run(
        self,
        file_record,
        channel_dapi: int,
        channel_alx: int,
        t: int,
        segmenter_name: str,
        segmenter_params: dict,
        job_id: str,
        results_dir: str,
        progress_cb: Callable[[str, int, str], None],
    ) -> tuple[AnalysisResult, dict[str, str]]:
        """
        Returns (AnalysisResult, graphs_dict) where graphs_dict maps name → base64 PNG.
        """
        progress_cb("loading", 5, "Extracting channel stacks...")
        dapi_stack = self._extract_stack(file_record, channel_dapi, t)
        alx_stack = self._extract_stack(file_record, channel_alx, t)

        progress_cb("preprocess", 20, "Preprocessing slices...")
        dapi_8 = self.preprocessor.process_stack(dapi_stack)
        alx_8 = self.preprocessor.process_stack(alx_stack)

        progress_cb("analysis", 45, "Analysing z-stack quality...")
        analysis = self.stack_analyser.analyse(alx_8)

        progress_cb("segmentation", 70, f"Running {segmenter_name} segmentation...")
        segmenter = get_segmenter(segmenter_name)

        z_start = analysis.optimal_z_start
        z_end = analysis.optimal_z_end
        n_slices = max(z_end - z_start + 1, 1)

        seg_results: dict[int, dict] = {}
        for i, z in enumerate(range(z_start, z_end + 1)):
            pct = 70 + int(25 * i / n_slices)
            progress_cb("segmentation", pct, f"Segmenting z={z}...")
            seg_results[z] = segmenter.segment(alx_8[z], segmenter_params)

        self._save_results(file_record.id, job_id, seg_results, results_dir)

        progress_cb("graphs", 97, "Generating analysis graphs...")
        graphs = self._generate_graphs(analysis)

        result = AnalysisResult(
            job_id=job_id,
            optimal_z_start=z_start,
            optimal_z_end=z_end,
            resolution_metrics=analysis.resolution_metrics,
            vert_correlations=analysis.vert_correlations,
            horiz_coherences=analysis.horiz_coherences,
            segmentation_available=True,
            segmenter_used=segmenter_name,
        )
        return result, graphs

    def _extract_stack(self, record, channel: int, t: int) -> np.ndarray:
        """Pull full Z stack for one channel at one timepoint. Returns (Z, Y, X) uint16."""
        axis = record.axis_order
        n_dims = len(axis)
        slices = [slice(None)] * n_dims

        if "C" in axis:
            slices[axis.index("C")] = channel
        if "T" in axis and "T" in record.sizes:
            slices[axis.index("T")] = t

        with record.lock:
            result = record.dask_array[tuple(slices)].compute()

        # Ensure output is (Z, Y, X): move Z axis to front if needed
        if "Z" in axis:
            z_pos_in_result = self._z_position_in_result(axis)
            if z_pos_in_result != 0:
                result = np.moveaxis(result, z_pos_in_result, 0)

        # If no Z dimension, add one
        if result.ndim == 2:
            result = result[np.newaxis, ...]

        return result

    @staticmethod
    def _z_position_in_result(axis_order: list[str]) -> int:
        """Return the index of Z in the result array after C and T are collapsed."""
        remaining = [a for a in axis_order if a not in ("C", "T")]
        return remaining.index("Z") if "Z" in remaining else 0

    @staticmethod
    def _save_results(file_id: str, job_id: str, seg_results: dict, results_dir: str) -> None:
        import pickle
        out_dir = Path(results_dir) / job_id
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(out_dir / "seg_results.pkl", "wb") as f:
            pickle.dump(seg_results, f)

    @staticmethod
    def _generate_graphs(analysis) -> dict[str, str]:
        graphs = {}
        Z = len(analysis.resolution_metrics)

        fig, ax = plt.subplots(figsize=(8, 3))
        ax.plot(range(Z), analysis.resolution_metrics, marker=".", color="#3498db")
        ax.axhline(45, color="#e74c3c", linestyle="--", linewidth=1, label="threshold=45")
        ax.set_title("Effective Resolution per Z-slice")
        ax.set_xlabel("Z slice")
        ax.set_ylabel("99th – 1st percentile")
        ax.legend()
        fig.tight_layout()
        graphs["resolution"] = _fig_to_b64(fig)
        plt.close(fig)

        if analysis.vert_correlations:
            fig, ax = plt.subplots(figsize=(8, 3))
            ax.plot(range(len(analysis.vert_correlations)), analysis.vert_correlations,
                    marker=".", color="#2ecc71")
            ax.axhline(0.78, color="#e74c3c", linestyle="--", linewidth=1, label="threshold=0.78")
            ax.set_title("Vertical Spatial Correlation (consecutive z-slices)")
            ax.set_xlabel("Z slice pair")
            ax.set_ylabel("Pearson r")
            ax.set_ylim(-1, 1)
            ax.legend()
            fig.tight_layout()
            graphs["correlations"] = _fig_to_b64(fig)
            plt.close(fig)

        fig, ax = plt.subplots(figsize=(8, 3))
        ax.plot(range(Z), analysis.horiz_coherences, marker=".", color="#9b59b6")
        ax.set_title("Horizontal Spatial Coherence per Z-slice")
        ax.set_xlabel("Z slice")
        ax.set_ylabel("Mean Pearson r (4 directions)")
        ax.set_ylim(-1, 1)
        fig.tight_layout()
        graphs["coherences"] = _fig_to_b64(fig)
        plt.close(fig)

        return graphs


def _fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()
