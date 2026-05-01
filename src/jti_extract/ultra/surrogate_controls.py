"""Surrogate / control validation for aperture contrast.

Stage 24: time-shift, phase-shuffle, and off-diagonal aperture surrogates.
"""

from typing import Any, Dict, List, Optional
import numpy as np

from jti_extract.ultra.contrast_profiles import (
    build_contrast_profile,
    select_contrast_candidates,
)
from jti_extract.ultra.aperture_select import select_apertures


def time_shift_surrogate(
    t_a: np.ndarray,
    t_b: np.ndarray,
    shift_ps: int,
    contrast_window_ps: int,
    n_bins: int,
    bin_width_ps: int,
    frame_origin_ps: float,
    frame_length_ps: int,
    on_diag_band_bins: int,
    bg_inner_bins: int,
    bg_outer_bins: int,
    center_coarse_bins: int,
) -> Dict[str, Any]:
    """Time-shift surrogate: shift channel B by shift_ps.

    Parameters
    ----------
    t_a, t_b : ndarray
        Raw timestamps (ps).
    shift_ps : int
        Time shift applied to channel B (ps).
    Other parameters: same as build_contrast_profile.

    Returns
    -------
    dict
        Surrogate contrast profile summary.
    """
    t_b_shifted = t_b + shift_ps
    ca, cb, delta = select_contrast_candidates(t_a, t_b_shifted, contrast_window_ps)
    cprof = build_contrast_profile(
        ca, cb, delta,
        n_bins=n_bins,
        bin_width_ps=bin_width_ps,
        frame_origin_ps=frame_origin_ps,
        frame_length_ps=frame_length_ps,
        on_diag_band_bins=on_diag_band_bins,
        bg_inner_bins=bg_inner_bins,
        bg_outer_bins=bg_outer_bins,
        center_coarse_bins=center_coarse_bins,
    )
    return cprof


def phase_shuffle_surrogate(
    t_a: np.ndarray,
    t_b: np.ndarray,
    rng: np.random.Generator,
    contrast_window_ps: int,
    n_bins: int,
    bin_width_ps: int,
    frame_origin_ps: float,
    frame_length_ps: int,
    on_diag_band_bins: int,
    bg_inner_bins: int,
    bg_outer_bins: int,
    center_coarse_bins: int,
) -> Dict[str, Any]:
    """Phase-shuffle surrogate: shuffle t_b frame phases.

    Preserves frame index and marginal distribution of t_b within each frame.
    Only shuffles the phase within each frame, keeping the frame assignment.
    """
    # Compute frame index and phase for each t_b event
    shifted = t_b.astype(np.float64) - float(frame_origin_ps)
    frame_idx = np.floor(shifted / float(frame_length_ps)).astype(np.int64)
    phase_b = np.mod(shifted, float(frame_length_ps))

    # Shuffle phase within each frame independently
    unique_frames = np.unique(frame_idx)
    for f in unique_frames:
        frame_mask = frame_idx == f
        frame_phases = phase_b[frame_mask].copy()
        rng.shuffle(frame_phases)
        phase_b[frame_mask] = frame_phases

    # Reconstruct t_b with shuffled phases, then sort for searchsorted
    t_b_shuffled = frame_origin_ps + frame_idx.astype(np.float64) * float(frame_length_ps) + phase_b
    t_b_shuffled = np.sort(t_b_shuffled)

    ca, cb, delta = select_contrast_candidates(t_a, t_b_shuffled, contrast_window_ps)
    cprof = build_contrast_profile(
        ca, cb, delta,
        n_bins=n_bins,
        bin_width_ps=bin_width_ps,
        frame_origin_ps=frame_origin_ps,
        frame_length_ps=frame_length_ps,
        on_diag_band_bins=on_diag_band_bins,
        bg_inner_bins=bg_inner_bins,
        bg_outer_bins=bg_outer_bins,
        center_coarse_bins=center_coarse_bins,
    )
    return cprof


def phase_shuffle_multi(
    t_a: np.ndarray,
    t_b: np.ndarray,
    n_shuffles: int = 20,
    seed: int = 42,
    contrast_window_ps: int = 3000,
    n_bins: int = 1024,
    bin_width_ps: int = 100,
    frame_origin_ps: float = 0.0,
    frame_length_ps: int = 102400,
    on_diag_band_bins: int = 2,
    bg_inner_bins: int = 10,
    bg_outer_bins: int = 30,
    center_coarse_bins: int = 512,
) -> Dict[str, Any]:
    """Run phase-shuffle n_shuffles times, return distribution stats.

    Returns
    -------
    dict
        max_snr_mean, max_snr_std, true_zscore, true_percentile,
        shuffle_max_snrs (list), true_max_snr
    """
    rng = np.random.default_rng(seed)

    # True contrast
    ca, cb, delta = select_contrast_candidates(t_a, t_b, contrast_window_ps)
    true_cprof = build_contrast_profile(
        ca, cb, delta,
        n_bins=n_bins, bin_width_ps=bin_width_ps,
        frame_origin_ps=frame_origin_ps, frame_length_ps=frame_length_ps,
        on_diag_band_bins=on_diag_band_bins, bg_inner_bins=bg_inner_bins,
        bg_outer_bins=bg_outer_bins, center_coarse_bins=center_coarse_bins,
    )
    true_summary = summarize_contrast_profile(true_cprof)
    true_max_snr = true_summary["max_snr"]

    # Shuffle distribution
    shuffle_max_snrs = []
    for _ in range(n_shuffles):
        surr_cprof = phase_shuffle_surrogate(
            t_a, t_b, rng,
            contrast_window_ps=contrast_window_ps, n_bins=n_bins,
            bin_width_ps=bin_width_ps, frame_origin_ps=frame_origin_ps,
            frame_length_ps=frame_length_ps,
            on_diag_band_bins=on_diag_band_bins, bg_inner_bins=bg_inner_bins,
            bg_outer_bins=bg_outer_bins, center_coarse_bins=center_coarse_bins,
        )
        surr_summary = summarize_contrast_profile(surr_cprof)
        shuffle_max_snrs.append(surr_summary["max_snr"])

    shuffle_arr = np.array(shuffle_max_snrs)
    mean_snr = float(np.mean(shuffle_arr))
    std_snr = float(np.std(shuffle_arr))
    zscore = (true_max_snr - mean_snr) / (std_snr + 1e-9)
    percentile = float(np.mean(shuffle_arr < true_max_snr) * 100.0)

    return {
        "true_max_snr": true_max_snr,
        "phase_shuffle_max_snr_mean": mean_snr,
        "phase_shuffle_max_snr_std": std_snr,
        "true_zscore_vs_shuffle": float(zscore),
        "true_percentile_vs_shuffle": percentile,
        "n_shuffles": n_shuffles,
        "shuffle_max_snrs": shuffle_max_snrs,
    }


def summarize_contrast_profile(cprof: Dict[str, Any]) -> Dict[str, float]:
    """Summarize a contrast profile into aggregate metrics."""
    segments = cprof.get("segments", [])
    if not segments:
        return {"max_snr": 0.0, "mean_snr": 0.0, "max_contrast_ratio": 0.0, "n_snr3": 0, "n_snr5": 0}

    snrs = [float(s["snr"]) for s in segments]
    crs = [float(s["contrast_ratio"]) for s in segments if s["contrast_ratio"] is not None]
    return {
        "max_snr": max(snrs),
        "mean_snr": float(np.mean(snrs)),
        "max_contrast_ratio": max(crs) if crs else 0.0,
        "n_snr3": sum(1 for s in snrs if s >= 3.0),
        "n_snr5": sum(1 for s in snrs if s >= 5.0),
    }
