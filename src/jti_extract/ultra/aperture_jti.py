"""Aperture-local JTI reconstruction.

Stage 22: reconstruct JTI within a selected temporal aperture.
Uses aperture-local lattice (not full-frame lattice).
"""

from typing import Any, Dict, Optional
import numpy as np

from jti_extract.ultra.accumulators import FixedLatticeAccumulator
from jti_extract.ultra.fold_lattice import phase_in_frame
from jti_extract.ultra.g2_accumulate import all_candidates


def build_aperture_accumulator(
    t_a: np.ndarray,
    t_b: np.ndarray,
    aperture: Dict[str, Any],
    n_bins: int,
    bin_width_ps: int,
    frame_origin_ps: float,
    frame_length_ps: int,
    coincidence_window_ps: int,
    edge_guard_ps: int,
    coarse_n_bins: int = 0,
) -> Dict[str, Any]:
    """Build JTI accumulator within a selected temporal aperture.

    Uses aperture-local lattice: aperture_origin_ps = aperture_start_ps,
    aperture_n_bins = floor(duration_ps / bin_width_ps).

    Parameters
    ----------
    t_a, t_b : ndarray
        Raw timestamps of channel A and B events (ps). Different sizes OK.
    aperture : dict
        Aperture info from select_apertures().
    n_bins, bin_width_ps, frame_origin_ps, frame_length_ps : int/float
        Full-frame lattice parameters (used for candidate generation).
    coincidence_window_ps, edge_guard_ps : int
        Coincidence window and edge guard (ps).
    coarse_n_bins : int
        Coarse JTI dimension (0 = skip).

    Returns
    -------
    dict
        Aperture JTI summary.
    """
    # Generate candidate pairs first
    cand_t_a, cand_t_b, _ = all_candidates(t_a, t_b, coincidence_window_ps)
    n_cand = int(cand_t_a.size)
    if n_cand == 0:
        return {"n_candidates_in_aperture": 0}

    # Compute true time center for each candidate
    t_center = (cand_t_a.astype(np.float64) + cand_t_b.astype(np.float64)) / 2.0

    # Aperture boundaries in phase space
    start_ps = float(aperture["start_ps"])
    stop_ps = float(aperture["stop_ps"])
    wraps = aperture.get("wraps_boundary", False)

    # Compute frame phase for center
    phase_center = phase_in_frame(t_center, frame_origin_ps, frame_length_ps)

    if wraps:
        # Wrapped aperture: phase in [start, frame_length) ∪ [0, stop % frame_length)
        stop_mod = stop_ps % frame_length_ps
        mask = (phase_center >= start_ps) | (phase_center < stop_mod)
    else:
        mask = (phase_center >= start_ps) & (phase_center < stop_ps)

    n_in_aperture = int(np.count_nonzero(mask))

    if n_in_aperture == 0:
        return {"n_candidates_in_aperture": 0}

    t_a_ap = cand_t_a[mask]
    t_b_ap = cand_t_b[mask]

    # Aperture-local lattice parameters
    aperture_duration_ps = stop_ps - start_ps
    aperture_n_bins = max(1, int(aperture_duration_ps / bin_width_ps))
    aperture_origin_ps = start_ps

    # Build aperture-local accumulator
    acc = FixedLatticeAccumulator(
        n_bins=aperture_n_bins,
        bin_width_ps=bin_width_ps,
        frame_origin_ps=aperture_origin_ps,
        coincidence_window_ps=coincidence_window_ps,
        edge_guard_ps=edge_guard_ps,
        coarse_n_bins=coarse_n_bins,
    )
    acc.add_candidates(t_a_ap, t_b_ap)

    summary = acc.summary()
    summary["n_candidates_in_aperture"] = n_in_aperture
    summary["aperture_candidate_fraction"] = n_in_aperture / n_cand
    summary["aperture_id"] = aperture.get("aperture_id", -1)
    summary["aperture_duration_ps"] = aperture_duration_ps
    summary["aperture_n_bins"] = aperture_n_bins
    summary["aperture_origin_ps"] = aperture_origin_ps
    summary["aperture_folding_mode"] = "phase-folded-across-global-frames"
    # Include coarse JTI for downstream SVD
    if acc.coarse_jti is not None:
        summary["coarse_jti"] = acc.coarse_jti

    return summary
