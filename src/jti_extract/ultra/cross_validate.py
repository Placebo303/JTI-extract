"""Cross-validation helpers between the ultra pipeline and baseline
jti-extract / jti-schmidt outputs.

Stage G status: implemented.  All helpers consume synthetic or pre-loaded
arrays only.  No .ttbin I/O.
"""

from typing import Dict, Optional

import numpy as np

from jti_extract.ultra.accumulators import FixedLatticeAccumulator
from jti_extract.ultra.diagnostics_pairing import strict_retention_meta
from jti_extract.ultra.g2_accumulate import all_candidates
from jti_extract.ultra.svd_estimators import svd_coarse_jti
from jti_extract.ultra.sweep_ultra_jti import run_synthetic_sweep_point


def cross_validate_ultra_vs_strict(
    t_a: np.ndarray,
    t_b: np.ndarray,
    *,
    n_bins: int,
    bin_width_ps: int,
    frame_origin_ps: float,
    coincidence_window_ps: int,
    edge_guard_ps: int,
    coarse_n_bins: int = 0,
) -> Dict[str, float]:
    """Compare ultra all-candidates results vs strict single-hit results.

    This produces diagnostics on how the strict selection bias affects
    candidate counts, diagonal profile, and coarse SVD metrics.

    Parameters
    ----------
    t_a, t_b : np.ndarray
        Sorted channel timestamps (ps).
    n_bins, bin_width_ps, frame_origin_ps : int, int, float
        Frame lattice parameters.
    coincidence_window_ps : int
        Fixed physical coincidence window (ps).
    edge_guard_ps : int
        Edge-guard margin (ps).
    coarse_n_bins : int
        Coarse JTI dimension (0 = skip).

    Returns
    -------
    dict
        Comparison metrics with keys prefixed ``ultra_``, ``strict_``,
        and ``ratio_``.
    """
    # 1. Ultra pipeline (all-candidates)
    ultra_result = run_synthetic_sweep_point(
        t_a, t_b,
        n_bins=n_bins, bin_width_ps=bin_width_ps,
        frame_origin_ps=frame_origin_ps,
        coincidence_window_ps=coincidence_window_ps,
        edge_guard_ps=edge_guard_ps,
        coarse_n_bins=coarse_n_bins,
    )

    # 2. Strict all-candidates: run all-candidates then apply strict mask
    ca_all, cb_all, _ = all_candidates(t_a, t_b, coincidence_window_ps)
    strict_meta = strict_retention_meta(
        t_a, t_b, frame_origin_ps, bin_width_ps, n_bins,
    )

    # Build a strict-only accumulator using original timestamps.
    # We identify strict single-hit frames and extract the original event
    # timestamps — no bin-center approximation.
    bw = int(bin_width_ps)
    N = int(n_bins)
    origin = float(frame_origin_ps)

    shifted_a = np.asarray(t_a, dtype=np.float64) - origin
    shifted_b = np.asarray(t_b, dtype=np.float64) - origin
    raw_a = np.floor(shifted_a / float(bw)).astype(np.int64)
    raw_b = np.floor(shifted_b / float(bw)).astype(np.int64)

    f_a = np.floor_divide(raw_a, N)
    f_b = np.floor_divide(raw_b, N)

    def _strict_single_hit_info(frames, bins):
        """Return strict-frame indices, their bin indices, and original event starts."""
        if frames.size == 0:
            return (
                np.array([], dtype=np.int64),
                np.array([], dtype=np.int64),
                np.array([], dtype=np.int64),
            )
        change_idx = np.flatnonzero(frames[1:] != frames[:-1]) + 1
        starts = np.concatenate(([0], change_idx))
        ends = np.concatenate((change_idx, [frames.size]))
        counts = ends - starts
        keep = counts == 1
        kept_starts = starts[keep]
        return frames[kept_starts], bins[kept_starts], kept_starts

    fu_a, du_a, starts_a = _strict_single_hit_info(f_a, raw_a)
    fu_b, du_b, starts_b = _strict_single_hit_info(f_b, raw_b)

    common, i0, i1 = np.intersect1d(fu_a, fu_b, assume_unique=True, return_indices=True)

    # Extract original timestamps using the original event indices.
    strict_a_orig_idx = starts_a[i0]
    strict_b_orig_idx = starts_b[i1]
    strict_t_a = np.asarray(t_a, dtype=np.int64)[strict_a_orig_idx]
    strict_t_b = np.asarray(t_b, dtype=np.int64)[strict_b_orig_idx]

    # Accumulate strict
    strict_acc = FixedLatticeAccumulator(
        n_bins=n_bins, bin_width_ps=bin_width_ps,
        frame_origin_ps=frame_origin_ps,
        coincidence_window_ps=coincidence_window_ps,
        edge_guard_ps=edge_guard_ps,
        coarse_n_bins=coarse_n_bins,
    )
    strict_acc.add_candidates(strict_t_a, strict_t_b)

    strict_n_pairs = float(strict_acc.n_candidates_after_edge_guard)
    ultra_n_pairs = float(ultra_result["n_candidates_after_edge_guard"])

    result: Dict[str, float] = {
        "ultra_n_candidates": float(ultra_result["n_candidates_total"]),
        "ultra_n_after_edge": ultra_n_pairs,
        "strict_n_pairs": strict_n_pairs,
        "strict_n_strict_pairs": float(strict_meta["n_strict_pairs"]),
        "strict_single_hit_retention_a": float(strict_meta["single_hit_retention_ratio_a"]),
        "strict_single_hit_retention_b": float(strict_meta["single_hit_retention_ratio_b"]),
        "ratio_ultra_vs_strict": ultra_n_pairs / strict_n_pairs if strict_n_pairs > 0 else float("inf"),
    }

    # Compare coarse SVD if available
    if coarse_n_bins > 0:
        cjti_ultra = None
        # Rebuild ultra accumulator to get coarse JTI
        ultra_acc = FixedLatticeAccumulator(
            n_bins=n_bins, bin_width_ps=bin_width_ps,
            frame_origin_ps=frame_origin_ps,
            coincidence_window_ps=coincidence_window_ps,
            edge_guard_ps=edge_guard_ps,
            coarse_n_bins=coarse_n_bins,
        )
        ultra_acc.add_candidates(ca_all, cb_all)
        cjti_ultra = ultra_acc.coarse_jti

        cjti_strict = strict_acc.coarse_jti

        if cjti_ultra is not None and np.sum(cjti_ultra) > 0:
            try:
                svd_u = svd_coarse_jti(cjti_ultra)
                result["ultra_K_coarse"] = svd_u["schmidt_number"]
            except (ValueError, np.linalg.LinAlgError):
                pass

        if cjti_strict is not None and np.sum(cjti_strict) > 0:
            try:
                svd_s = svd_coarse_jti(cjti_strict)
                result["strict_K_coarse"] = svd_s["schmidt_number"]
            except (ValueError, np.linalg.LinAlgError):
                pass

        if "ultra_K_coarse" in result and "strict_K_coarse" in result:
            k_s = result["strict_K_coarse"]
            result["ratio_K_ultra_vs_strict"] = (
                result["ultra_K_coarse"] / k_s if k_s > 0 else float("inf")
            )

    return result
