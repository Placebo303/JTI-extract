"""Diagnostics-only helpers for ultra JTI sweep pairing methods.

All functions consume synthetic / pre-loaded arrays only.
They do not read ``.ttbin`` files and do not implement background subtraction
or signed-spectrum output.

Each diagnostic wrapper produces comparable metrics across:
- strict single-hit frame retention
- folded-without-strict
- nearest heuristic
- greedy-unique heuristic
- g2_all_candidates (reference)
"""

from typing import Dict, List, Tuple

import numpy as np


# ---------------------------------------------------------------------------
#  Helpers replicated from existing CLI modules (read-only reference)
#  These are NOT the main physical pairing algorithms and must not replace
#  the existing implementations.
# ---------------------------------------------------------------------------


def _nearest_pairs(
    t_a: np.ndarray, t_b: np.ndarray, window_ps: int
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Nearest-neighbour heuristic, equivalent to ``nearest_pairs()``.

    .. note::
        This is a *diagnostic* helper.  It must not replace the original
        implementation in ``src/jti_extract/cli/tdc_layer_scan.py``.
    """
    if t_a.size == 0 or t_b.size == 0:
        return (
            np.array([], dtype=np.int64),
            np.array([], dtype=np.int64),
            np.array([], dtype=np.int64),
        )
    pos = np.searchsorted(t_b, t_a)
    best_delta = np.full(t_a.shape, np.iinfo(np.int64).max, dtype=np.int64)
    best_t_b = np.zeros(t_a.shape, dtype=np.int64)
    right = pos < t_b.size
    best_delta[right] = t_b[pos[right]] - t_a[right]
    best_t_b[right] = t_b[pos[right]]
    left = pos > 0
    left_delta = t_b[pos[left] - 1] - t_a[left]
    use_left = np.abs(left_delta) < np.abs(best_delta[left])
    left_indices = np.flatnonzero(left)
    replace = left_indices[use_left]
    best_delta[replace] = left_delta[use_left]
    best_t_b[replace] = t_b[pos[replace] - 1]
    keep = np.abs(best_delta) <= int(window_ps)
    return t_a[keep].copy(), best_t_b[keep].copy(), best_delta[keep].copy()


def _greedy_unique_pairs(
    t_a: np.ndarray, t_b: np.ndarray, window_ps: int
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Greedy-unique heuristic, equivalent to ``greedy_unique_pairs()``.

    .. note::
        This is a *diagnostic* helper.  It must not replace the original
        implementation in ``src/jti_extract/cli/tdc_layer_scan.py``.
    """
    i = 0
    j = 0
    out_a: List[int] = []
    out_b: List[int] = []
    out_d: List[int] = []
    n_a = int(t_a.size)
    n_b = int(t_b.size)
    w = int(window_ps)
    while i < n_a and j < n_b:
        av = int(t_a[i])
        while j < n_b and int(t_b[j]) < av - w:
            j += 1
        if j >= n_b:
            break
        candidates: List[Tuple[int, int]] = []
        if abs(int(t_b[j]) - av) <= w:
            candidates.append((abs(int(t_b[j]) - av), j))
        if j + 1 < n_b and abs(int(t_b[j + 1]) - av) <= w:
            candidates.append((abs(int(t_b[j + 1]) - av), j + 1))
        if candidates:
            _, jj = min(candidates)
            bv = int(t_b[jj])
            out_a.append(av)
            out_b.append(bv)
            out_d.append(bv - av)
            i += 1
            j = jj + 1
        else:
            i += 1
    return (
        np.asarray(out_a, dtype=np.int64),
        np.asarray(out_b, dtype=np.int64),
        np.asarray(out_d, dtype=np.int64),
    )


# ---------------------------------------------------------------------------
#  Strict single-hit frame retention diagnostic
# ---------------------------------------------------------------------------


def strict_retention_meta(
    t_a: np.ndarray,
    t_b: np.ndarray,
    frame_origin_ps: float,
    bin_width_ps: int,
    n_bins: int,
) -> Dict[str, float]:
    """Compute strict single-hit retention statistics.

    Replicates (for diagnostics) the logic of ``_pairs_from_timetags()``.

    Parameters
    ----------
    t_a : np.ndarray
        Sorted channel A timestamps (ps).
    t_b : np.ndarray
        Sorted channel B timestamps (ps).
    frame_origin_ps : float
        Global frame origin (ps).
    bin_width_ps : int
        Bin width (ps).
    n_bins : int
        Number of bins per frame dimension.

    Returns
    -------
    dict
        ``n_strict_pairs``, ``single_hit_retention_ratio``,
        ``multi_hit_rejected_ratio``.
    """
    bw = int(bin_width_ps)
    N = int(n_bins)
    origin = float(frame_origin_ps)

    # Raw (non-moduloed) bin indices, matching _pairs_from_timetags()
    shifted_a = np.asarray(t_a, dtype=np.float64) - origin
    shifted_b = np.asarray(t_b, dtype=np.float64) - origin
    raw_a = np.floor(shifted_a / float(bw)).astype(np.int64)
    raw_b = np.floor(shifted_b / float(bw)).astype(np.int64)

    f_a = np.floor_divide(raw_a, N)
    d_a = np.mod(raw_a, N).astype(np.int64, copy=False)
    f_b = np.floor_divide(raw_b, N)
    d_b = np.mod(raw_b, N).astype(np.int64, copy=False)

    def _unique_single_hit(frames: np.ndarray, bins: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        if frames.size == 0:
            return np.array([], dtype=np.int64), np.array([], dtype=np.int64)
        change_idx = np.flatnonzero(frames[1:] != frames[:-1]) + 1
        starts = np.concatenate(([0], change_idx))
        ends = np.concatenate((change_idx, [frames.size]))
        counts = ends - starts
        keep = counts == 1
        kept_starts = starts[keep]
        return frames[kept_starts], bins[kept_starts]

    fu_a, du_a = _unique_single_hit(f_a, d_a)
    fu_b, du_b = _unique_single_hit(f_b, d_b)

    n_events_ch_a = int(t_a.size)
    n_events_ch_b = int(t_b.size)
    n_single_hit_a = int(fu_a.size)
    n_single_hit_b = int(fu_b.size)

    common, i0, i1 = np.intersect1d(fu_a, fu_b, assume_unique=True, return_indices=True)
    n_strict_pairs = int(common.size)

    total_frames_a = int(np.max(f_a)) - int(np.min(f_a)) + 1 if f_a.size else 0
    total_frames_b = int(np.max(f_b)) - int(np.min(f_b)) + 1 if f_b.size else 0

    # retention ratios relative to events
    single_hit_retention_a = (
        float(n_single_hit_a) / float(n_events_ch_a) if n_events_ch_a > 0 else 0.0
    )
    single_hit_retention_b = (
        float(n_single_hit_b) / float(n_events_ch_b) if n_events_ch_b > 0 else 0.0
    )

    return {
        "n_events_ch_a": float(n_events_ch_a),
        "n_events_ch_b": float(n_events_ch_b),
        "n_single_hit_frames_a": float(n_single_hit_a),
        "n_single_hit_frames_b": float(n_single_hit_b),
        "n_strict_pairs": float(n_strict_pairs),
        "single_hit_retention_ratio_a": single_hit_retention_a,
        "single_hit_retention_ratio_b": single_hit_retention_b,
        "multi_hit_rejected_a": float(n_events_ch_a - n_single_hit_a),
        "multi_hit_rejected_b": float(n_events_ch_b - n_single_hit_b),
    }


# ---------------------------------------------------------------------------
#  Method comparison diagnostic
# ---------------------------------------------------------------------------


def method_comparison_summary(
    t_a: np.ndarray,
    t_b: np.ndarray,
    coincidence_window_ps: int,
) -> Dict[str, float]:
    """Compare candidate/pair counts across methods.

    Returns
    -------
    dict
        ``n_candidates_all``, ``n_nearest_pairs``, ``n_greedy_unique_pairs``,
        ``all_vs_nearest_ratio``, ``all_vs_greedy_ratio``.
    """
    from jti_extract.ultra.g2_accumulate import all_candidates

    ca, _, _ = all_candidates(t_a, t_b, coincidence_window_ps)
    n_all = int(ca.size)

    _, _, dn = _nearest_pairs(t_a, t_b, coincidence_window_ps)
    n_near = int(dn.size)

    _, _, dg = _greedy_unique_pairs(t_a, t_b, coincidence_window_ps)
    n_greedy = int(dg.size)

    return {
        "n_candidates_all": float(n_all),
        "n_nearest_pairs": float(n_near),
        "n_greedy_unique_pairs": float(n_greedy),
        "all_vs_nearest_ratio": float(n_all) / float(n_near) if n_near > 0 else float("inf"),
        "all_vs_greedy_ratio": float(n_all) / float(n_greedy) if n_greedy > 0 else float("inf"),
    }
