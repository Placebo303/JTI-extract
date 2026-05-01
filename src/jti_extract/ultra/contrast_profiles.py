"""Per-segment contrast profile diagnostics for ultra JTI sweep.

Stage 20: local diagonal contrast profiles vs sideband background.
"""

from typing import Any, Dict, Optional
import numpy as np

from jti_extract.ultra.fold_lattice import phase_in_frame


def select_contrast_candidates(
    t_a: np.ndarray, t_b: np.ndarray, contrast_window_ps: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Select candidate pairs within the expanded contrast window.

    Parameters
    ----------
    t_a, t_b : ndarray
        Timestamps of channel A and B events (ps). Must be aligned
        (already sorted).
    contrast_window_ps : int
        Expanded coincidence window for contrast diagnostics (ps).

    Returns
    -------
    t_a_out, t_b_out : ndarray
        Timestamps of candidate pairs (ps).
    delta_out : ndarray
        delta = t_b - t_a (ps).
    """
    from jti_extract.ultra.g2_accumulate import iter_all_candidates

    candidates: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
    for a_chunk, b_chunk, d_chunk in iter_all_candidates(
        t_a, t_b, contrast_window_ps, chunk_events=200_000
    ):
        candidates.append((a_chunk, b_chunk, d_chunk))

    if not candidates:
        return (
            np.array([], dtype=np.int64),
            np.array([], dtype=np.int64),
            np.array([], dtype=np.int64),
        )

    return (
        np.concatenate([c[0] for c in candidates]),
        np.concatenate([c[1] for c in candidates]),
        np.concatenate([c[2] for c in candidates]),
    )


def build_contrast_profile(
    candidates_t_a: np.ndarray,
    candidates_t_b: np.ndarray,
    delta_ps: np.ndarray,
    n_bins: int,
    bin_width_ps: int,
    frame_origin_ps: float,
    frame_length_ps: int,
    on_diag_band_bins: int,
    bg_inner_bins: int,
    bg_outer_bins: int,
    center_coarse_bins: int,
) -> Dict[str, Any]:
    """Build per-segment contrast profile.

    Parameters
    ----------
    candidates_t_a, candidates_t_b : ndarray
        Timestamps of candidate pairs (ps).
    delta_ps : ndarray
        delta = t_b - t_a (ps).
    n_bins : int
        Number of full-frame bins.
    bin_width_ps : int
        Width of each time bin (ps).
    frame_origin_ps : float
        Global frame origin (ps).
    frame_length_ps : int
        Frame length (ps).
    on_diag_band_bins : int
        On-diagonal band width in bins (|offset_bins| <= band).
    bg_inner_bins : int
        Inner offset for sideband (bins).
    bg_outer_bins : int
        Outer offset for sideband (bins).
    center_coarse_bins : int
        Number of coarse segments (M) along the diagonal direction.

    Returns
    -------
    dict
        Keys: segments (list of dicts), plus metadata.
    """
    n_cand = int(candidates_t_a.size)
    if n_cand == 0:
        return {"segments": [], "n_candidates": 0}

    # True time center (not bin center), then fold to frame phase
    t_center = (candidates_t_a.astype(np.float64) + candidates_t_b.astype(np.float64)) / 2.0
    phase = phase_in_frame(t_center, frame_origin_ps, frame_length_ps)

    # Assign to coarse segments
    segment_size = float(frame_length_ps) / float(center_coarse_bins)
    seg_idx = np.floor(phase / segment_size).astype(np.int64)
    seg_idx = np.clip(seg_idx, 0, center_coarse_bins - 1)

    # Compute offset in bins
    offset_bins = np.round(delta_ps / float(bin_width_ps)).astype(np.int64)
    abs_offset = np.abs(offset_bins)

    # Masks
    on_mask = abs_offset <= on_diag_band_bins
    sb_mask = (abs_offset >= bg_inner_bins) & (abs_offset <= bg_outer_bins)

    # Vectorized accumulation using bincount
    on_counts = np.bincount(seg_idx[on_mask], minlength=center_coarse_bins).astype(np.int64)
    sb_counts = np.bincount(seg_idx[sb_mask], minlength=center_coarse_bins).astype(np.int64)

    # Area correction
    on_band_bins = 2 * on_diag_band_bins + 1
    sb_band_bins = 2 * (bg_outer_bins - bg_inner_bins + 1)
    area_scale = float(on_band_bins) / float(sb_band_bins) if sb_band_bins > 0 else 1.0

    # Background scaled counts
    bg_scaled = sb_counts.astype(np.float64) * area_scale

    # Contrast ratio with explicit sideband_zero handling
    eps = 1e-9
    sideband_zero = sb_counts == 0
    contrast_ratio = np.where(
        sideband_zero,
        np.inf,  # undefined when sideband=0
        (on_counts.astype(np.float64) + eps) / (bg_scaled + eps),
    )
    contrast_excess = np.where(
        sideband_zero,
        np.inf,
        (on_counts.astype(np.float64) - bg_scaled) / (bg_scaled + eps),
    )

    # SNR (Poisson) — when sideband=0, SNR = on / sqrt(on) = sqrt(on)
    snr_raw = np.where(
        sideband_zero,
        on_counts.astype(np.float64) / np.sqrt(on_counts.astype(np.float64) + eps),
        (on_counts.astype(np.float64) - bg_scaled) / np.sqrt(
            on_counts.astype(np.float64) + bg_scaled + eps
        ),
    )

    # SNR valid-bg only: None when sideband=0
    snr_valid_bg = np.where(
        sideband_zero,
        np.nan,
        (on_counts.astype(np.float64) - bg_scaled) / np.sqrt(
            on_counts.astype(np.float64) + bg_scaled + eps
        ),
    )

    # Build per-segment summary
    segments = []
    for seg in range(center_coarse_bins):
        seg_start_ps = float(seg) * segment_size
        seg_stop_ps = float(seg + 1) * segment_size

        cr_val = float(contrast_ratio[seg])
        cr_display = None if np.isinf(cr_val) else cr_val

        snr_vb = float(snr_valid_bg[seg])
        snr_vb_display = None if np.isnan(snr_vb) else snr_vb

        segments.append({
            "segment_idx": int(seg),
            "segment_start_ps": float(seg_start_ps),
            "segment_stop_ps": float(seg_stop_ps),
            "on_diag_counts": int(on_counts[seg]),
            "sideband_counts": int(sb_counts[seg]),
            "sideband_zero": bool(sideband_zero[seg]),
            "on_diag_offset_bins": on_band_bins,
            "sideband_offset_bins": sb_band_bins,
            "bg_scaled_counts": float(bg_scaled[seg]),
            "contrast_ratio": cr_display,
            "contrast_excess": None if np.isinf(float(contrast_excess[seg])) else float(contrast_excess[seg]),
            "snr": float(snr_raw[seg]),
            "snr_valid_bg": snr_vb_display,
            "is_snr3": bool(snr_raw[seg] >= 3.0),
            "is_snr5": bool(snr_raw[seg] >= 5.0),
            "is_snr3_valid_bg": bool(snr_vb_display is not None and snr_vb_display >= 3.0),
            "is_snr5_valid_bg": bool(snr_vb_display is not None and snr_vb_display >= 5.0),
            "is_contrast2": bool(cr_display is not None and cr_display >= 2.0),
            "is_contrast5": bool(cr_display is not None and cr_display >= 5.0),
        })

    return {
        "segments": segments,
        "n_candidates": n_cand,
        "center_coarse_bins": center_coarse_bins,
        "on_band_bins": on_band_bins,
        "sb_band_bins": sb_band_bins,
        "area_scale": area_scale,
    }
