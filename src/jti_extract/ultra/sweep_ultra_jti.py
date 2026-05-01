"""Sweep orchestration prototype for ultra JTI pipeline.

Chains the Stage A/B/C library functions into synthetic-array pipelines.
All output is returned as Python ``dict`` / ``list`` only — no CSV, JSON,
NPZ, or directory creation.

No CLI, no config schema, no ``.ttbin`` I/O, no background subtraction.
"""

from typing import Dict, List, Optional

import numpy as np

from jti_extract.ultra.accumulators import FixedLatticeAccumulator
from jti_extract.ultra.diagnostics_pairing import (
    method_comparison_summary,
    strict_retention_meta,
)
from jti_extract.ultra.g2_accumulate import all_candidates
from jti_extract.ultra.svd_estimators import svd_coarse_jti


# ---------------------------------------------------------------------------
#  Single sweep point
# ---------------------------------------------------------------------------


def run_synthetic_sweep_point(
    t_a: np.ndarray,
    t_b: np.ndarray,
    *,
    n_bins: int,
    bin_width_ps: int,
    frame_origin_ps: float,
    coincidence_window_ps: int,
    edge_guard_ps: int,
    coarse_n_bins: int = 0,
) -> Dict[str, object]:
    """Run a single synthetic sweep point and return an in-memory summary dict.

    Chains::

        all_candidates()
        → FixedLatticeAccumulator.add_candidates()
        → diagnostics_pairing.strict_retention_meta()
        → diagnostics_pairing.method_comparison_summary()
        → svd_estimators.svd_coarse_jti()  (if coarse_jti available)

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
        Coarse JTI dimension (0 = skip coarse JTI).

    Returns
    -------
    dict
        Combined summary with keys from accumulator, diagnostics_pairing,
        and svd_estimators.
    """
    # 1. All candidates
    ca, cb, _ = all_candidates(t_a, t_b, coincidence_window_ps)
    n_candidates_total = int(ca.size)

    # 2. Accumulate
    acc = FixedLatticeAccumulator(
        n_bins=n_bins,
        bin_width_ps=bin_width_ps,
        frame_origin_ps=frame_origin_ps,
        coincidence_window_ps=coincidence_window_ps,
        edge_guard_ps=edge_guard_ps,
        coarse_n_bins=coarse_n_bins,
    )
    acc.add_candidates(ca, cb)

    # 3. Strict retention diagnostic
    strict_meta = strict_retention_meta(
        t_a, t_b, frame_origin_ps, bin_width_ps, n_bins,
    )

    # 4. Method comparison diagnostic
    method_meta = method_comparison_summary(
        t_a, t_b, coincidence_window_ps,
    )

    # 5. Coarse SVD (if coarse JTI is available)
    svd_meta: Optional[Dict[str, float]] = None
    cjti = acc.coarse_jti
    if cjti is not None and np.sum(cjti) > 0:
        try:
            svd_meta = svd_coarse_jti(cjti)
        except (ValueError, np.linalg.LinAlgError):
            svd_meta = None

    # 6. Assemble result
    result: Dict[str, object] = {
        "n_bins": n_bins,
        "bin_width_ps": bin_width_ps,
        "frame_origin_ps": frame_origin_ps,
        "frame_length_ps": int(n_bins) * int(bin_width_ps),
        "coincidence_window_ps": coincidence_window_ps,
        "edge_guard_ps": edge_guard_ps,
        "coarse_n_bins": coarse_n_bins,
        "n_candidates_total": n_candidates_total,
        "n_candidates_after_edge_guard": acc.n_candidates_after_edge_guard,
        "edge_rejection_ratio": acc.edge_rejection_ratio,
        "diag_profile_sum": float(np.sum(acc.diag_profile)),
        "row_marginal_sum": float(np.sum(acc.row_marginal)),
        "col_marginal_sum": float(np.sum(acc.col_marginal)),
        **acc.summary(),
        **strict_meta,
        **method_meta,
    }
    if svd_meta is not None:
        result["K_coarse"] = svd_meta["schmidt_number"]
        result["svd_purity"] = svd_meta["purity"]
        result["svd_largest_weight"] = svd_meta["largest_weight"]
        result["svd_n_singular_values"] = svd_meta["n_singular_values"]
        result["svd_nonzero_bins"] = svd_meta["nonzero_bins"]

    return result


# ---------------------------------------------------------------------------
#  Origin sensitivity helper
# ---------------------------------------------------------------------------


def origin_sensitivity_summary(
    t_a: np.ndarray,
    t_b: np.ndarray,
    *,
    origins_ps: List[float],
    n_bins: int,
    bin_width_ps: int,
    coincidence_window_ps: int,
    edge_guard_ps: int,
    coarse_n_bins: int = 0,
) -> List[Dict[str, object]]:
    """Run sweep points for multiple *frame_origin_ps* values.

    Parameters
    ----------
    origins_ps : list of float
        Multiple global frame origins to test.  These are only for
        sensitivity check and must not be combined as independent samples.

    Returns
    -------
    list of dict
        One ``run_synthetic_sweep_point()`` result per origin.
    """
    results: List[Dict[str, object]] = []
    for origin in origins_ps:
        r = run_synthetic_sweep_point(
            t_a, t_b,
            n_bins=n_bins,
            bin_width_ps=bin_width_ps,
            frame_origin_ps=origin,
            coincidence_window_ps=coincidence_window_ps,
            edge_guard_ps=edge_guard_ps,
            coarse_n_bins=coarse_n_bins,
        )
        results.append(r)
    return results


# ---------------------------------------------------------------------------
#  Edge-guard sensitivity helper
# ---------------------------------------------------------------------------


def edge_guard_sensitivity_summary(
    t_a: np.ndarray,
    t_b: np.ndarray,
    *,
    edge_guards_ps: List[int],
    n_bins: int,
    bin_width_ps: int,
    frame_origin_ps: float,
    coincidence_window_ps: int,
    coarse_n_bins: int = 0,
) -> List[Dict[str, object]]:
    """Run sweep points for multiple *edge_guard_ps* values.

    Parameters
    ----------
    edge_guards_ps : list of int
        Multiple edge-guard margins to test.

    Returns
    -------
    list of dict
        One ``run_synthetic_sweep_point()`` result per edge-guard value.
    """
    results: List[Dict[str, object]] = []
    for eg in edge_guards_ps:
        r = run_synthetic_sweep_point(
            t_a, t_b,
            n_bins=n_bins,
            bin_width_ps=bin_width_ps,
            frame_origin_ps=frame_origin_ps,
            coincidence_window_ps=coincidence_window_ps,
            edge_guard_ps=eg,
            coarse_n_bins=coarse_n_bins,
        )
        results.append(r)
    return results


# ---------------------------------------------------------------------------
#  Method comparison sweep helper
# ---------------------------------------------------------------------------


def method_comparison_sweep(
    t_a: np.ndarray,
    t_b: np.ndarray,
    *,
    n_bins: int,
    bin_width_ps: int,
    frame_origin_ps: float,
    coincidence_window_ps: int,
    edge_guard_ps: int,
    coarse_n_bins: int = 0,
) -> Dict[str, object]:
    """Run a sweep point with detailed method comparison.

    Returns a single dict that includes per-method candidate/pair counts
    alongside the standard sweep-point fields.
    """
    base = run_synthetic_sweep_point(
        t_a, t_b,
        n_bins=n_bins,
        bin_width_ps=bin_width_ps,
        frame_origin_ps=frame_origin_ps,
        coincidence_window_ps=coincidence_window_ps,
        edge_guard_ps=edge_guard_ps,
        coarse_n_bins=coarse_n_bins,
    )

    # Add per-method counts from diagnostics_pairing
    method_meta = method_comparison_summary(t_a, t_b, coincidence_window_ps)
    base["n_candidates_all"] = int(method_meta["n_candidates_all"])
    base["n_nearest_pairs"] = int(method_meta["n_nearest_pairs"])
    base["n_greedy_unique_pairs"] = int(method_meta["n_greedy_unique_pairs"])
    base["all_vs_nearest_ratio"] = float(method_meta["all_vs_nearest_ratio"])
    base["all_vs_greedy_ratio"] = float(method_meta["all_vs_greedy_ratio"])

    return base
