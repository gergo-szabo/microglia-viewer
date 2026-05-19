from dataclasses import dataclass

import numpy as np


@dataclass
class StackAnalysis:
    resolution_metrics: list[float]
    vert_correlations: list[float]
    horiz_coherences: list[float]
    optimal_z_start: int
    optimal_z_end: int


class StackAnalyser:

    def analyse(
        self,
        stack_8: np.ndarray,
        res_threshold: float = 45.0,
        corr_threshold: float = 0.78,
    ) -> StackAnalysis:
        Z = stack_8.shape[0]

        res_metrics = [
            float(np.percentile(stack_8[z], 99) - np.percentile(stack_8[z], 1))
            for z in range(Z)
        ]

        vert_corrs = []
        for z in range(Z - 1):
            a = stack_8[z].flatten().astype(np.float64)
            b = stack_8[z + 1].flatten().astype(np.float64)
            r = float(np.corrcoef(a, b)[0, 1])
            vert_corrs.append(r if np.isfinite(r) else 0.0)

        horiz_cohs = [self._horiz_coherence(stack_8[z]) for z in range(Z)]

        z_start, z_end = self._find_optimal_range(res_metrics, vert_corrs, res_threshold, corr_threshold)

        return StackAnalysis(
            resolution_metrics=res_metrics,
            vert_correlations=vert_corrs,
            horiz_coherences=horiz_cohs,
            optimal_z_start=z_start,
            optimal_z_end=z_end,
        )

    @staticmethod
    def _horiz_coherence(img: np.ndarray) -> float:
        s = 1
        pairs = [
            (img[:, s:].flatten(), img[:, :-s].flatten()),
            (img[s:, :].flatten(), img[:-s, :].flatten()),
            (img[s:, s:].flatten(), img[:-s, :-s].flatten()),
            (img[s:, :-s].flatten(), img[:-s, s:].flatten()),
        ]
        rs = []
        for a, b in pairs:
            a, b = a.astype(np.float64), b.astype(np.float64)
            r = float(np.corrcoef(a, b)[0, 1])
            if np.isfinite(r):
                rs.append(r)
        return float(np.mean(rs)) if rs else 0.0

    @staticmethod
    def _find_optimal_range(
        res_metrics: list[float],
        vert_corrs: list[float],
        res_thresh: float,
        corr_thresh: float,
    ) -> tuple[int, int]:
        n = len(res_metrics)
        if n == 0:
            return 0, 0

        res_pass = [m >= res_thresh for m in res_metrics]
        corr_pass = [c >= corr_thresh for c in vert_corrs]  # len n-1

        best_start, best_end, best_len = 0, 0, 0
        run_start = 0

        for z in range(n):
            slice_ok = res_pass[z]
            pair_ok = corr_pass[z - 1] if z > 0 else True
            if not (slice_ok and pair_ok):
                run_start = z + 1
            else:
                length = z - run_start + 1
                if length > best_len:
                    best_len = length
                    best_start = run_start
                    best_end = z

        if best_len == 0:
            # Fallback: use all slices
            return 0, n - 1
        return best_start, best_end
