"""Aperture selection from contrast profile.

Stage 21: select effective temporal apertures based on SNR/contrast thresholds.
"""

from typing import Any, Dict, List, Optional
import numpy as np


def _run_length_threshold(
    scores: np.ndarray,
    min_run: int = 3,
    max_gap: int = 1,
) -> List[Dict[str, int]]:
    """Find runs of True values with allowed gaps.

    Parameters
    ----------
    scores : np.ndarray
        Boolean array of scores (True = pass threshold).
    min_run : int
        Minimum consecutive segments for a run.
    max_gap : int
        Maximum gap within a run.

    Returns
    -------
    list of dict
        {start, stop, length} for each valid run.
    """
    n = len(scores)
    runs: List[Dict[str, int]] = []
    i = 0
    while i < n:
        if not scores[i]:
            i += 1
            continue
        # Found run start
        start = i
        run_end = i
        current_gap = 0
        j = i
        while j < n:
            if scores[j]:
                run_end = j
                current_gap = 0
            else:
                current_gap += 1
                if current_gap > max_gap:
                    break
            j += 1
        # Check run length
        if run_end - start + 1 >= min_run:
            runs.append({"start": start, "stop": run_end, "length": run_end - start + 1})
        i = j
    return runs


def _merge_circular_runs(
    runs: List[Dict[str, int]], n_segments: int
) -> List[Dict[str, int]]:
    """Merge runs that wrap around circular boundary.

    If first run starts at 0 and last run ends at n_segments-1,
    merge them into a wrapped run.
    """
    if len(runs) <= 1:
        return runs
    first, last = runs[0], runs[-1]
    if first["start"] == 0 and last["stop"] == n_segments - 1:
        merged = {
            "start": last["start"],
            "stop": first["stop"] + n_segments,  # linearized wrapped coordinate
            "length": last["length"] + first["length"],
            "wraps": True,
        }
        return [merged] + runs[1:-1]
    return runs


def select_apertures(
    contrast_profile: Dict[str, Any],
    threshold: str = "snr3",
    min_run_segments: int = 3,
    max_gap_segments: int = 1,
    require_sideband: bool = False,
) -> List[Dict[str, Any]]:
    """Select effective temporal apertures from contrast profile.

    Parameters
    ----------
    contrast_profile : dict
        Output from build_contrast_profile(), with "segments" key.
    threshold : str
        Threshold name: "snr3", "snr5", "contrast2", "contrast5".
    min_run_segments : int
        Minimum consecutive segments for an aperture.
    max_gap_segments : int
        Maximum gap segments allowed within an aperture.
    require_sideband : bool
        If True, exclude sideband_zero segments from scoring.

    Returns
    -------
    list of dict
        Aperture information for each detected aperture.
    """
    segments = contrast_profile.get("segments", [])
    if not segments:
        return []
    n_seg = len(segments)

    # Determine score mask
    scores = np.zeros(n_seg, dtype=bool)
    for i, seg in enumerate(segments):
        # If require_sideband, exclude sideband_zero segments
        if require_sideband and seg.get("sideband_zero", False):
            continue
        if threshold == "snr3":
            # Prefer snr_valid_bg if available, fall back to snr
            snr_val = seg.get("snr_valid_bg", seg["snr"])
            scores[i] = snr_val is not None and float(snr_val) >= 3.0
        elif threshold == "snr5":
            snr_val = seg.get("snr_valid_bg", seg["snr"])
            scores[i] = snr_val is not None and float(snr_val) >= 5.0
        elif threshold == "contrast2":
            cr = seg["contrast_ratio"]
            scores[i] = cr is not None and float(cr) >= 2.0
        elif threshold == "contrast5":
            cr = seg["contrast_ratio"]
            scores[i] = cr is not None and float(cr) >= 5.0
        else:
            raise ValueError(f"Unknown threshold: {threshold}")

    # Run-length detection
    runs = _run_length_threshold(scores, min_run_segments, max_gap_segments)
    if not runs:
        return []

    # Merge circular wrap runs
    runs = _merge_circular_runs(runs, n_seg)

    # Build aperture info
    segment_size_ps = float(segments[0]["segment_stop_ps"]) - float(segments[0]["segment_start_ps"])
    apertures: List[Dict[str, Any]] = []
    for idx, run in enumerate(runs):
        wraps = run.get("wraps", False)
        if wraps:
            # Wrapped aperture: from circular start to stop, spanning boundary
            # linearized stop is >= n_segments; map back to [0, n_segments)
            real_start = run["start"]
            real_stop = run["stop"] - n_seg  # wrapped end
            # Collect segments: real_start to n_segments-1, then 0 to real_stop
            seg_indices = list(range(real_start, n_seg)) + list(range(0, real_stop + 1))
        else:
            real_start = run["start"]
            real_stop = run["stop"]
            seg_indices = list(range(real_start, real_stop + 1))

        # Aggregate statistics (contrast_ratio may be None for sideband_zero)
        crs = [float(segments[i]["contrast_ratio"]) for i in seg_indices if segments[i]["contrast_ratio"] is not None]
        snrs = [float(segments[i]["snr"]) for i in seg_indices]
        on_counts = sum(int(segments[i]["on_diag_counts"]) for i in seg_indices)
        bg_scaled = sum(float(segments[i]["bg_scaled_counts"]) for i in seg_indices)

        if wraps:
            start_ps = float(segments[real_start]["segment_start_ps"])
            stop_ps = float(segments[real_stop]["segment_stop_ps"]) + n_seg * segment_size_ps
        else:
            start_ps = float(segments[real_start]["segment_start_ps"])
            stop_ps = float(segments[real_stop]["segment_stop_ps"])

        aperture = {
            "aperture_id": idx,
            "threshold": threshold,
            "start_segment": real_start,
            "stop_segment": real_stop,
            "wraps_boundary": wraps,
            "start_ps": start_ps,
            "stop_ps": stop_ps,
            "duration_ps": stop_ps - start_ps,
            "n_segments": len(seg_indices),
            "n_sideband_zero_segments": sum(1 for i in seg_indices if segments[i]["sideband_zero"]),
            "mean_contrast_ratio": float(np.mean(crs)) if crs else None,
            "median_contrast_ratio": float(np.median(crs)) if crs else None,
            "mean_snr": float(np.mean(snrs)),
            "min_snr": float(np.min(snrs)),
            "total_on_counts": on_counts,
            "total_bg_scaled_counts": bg_scaled,
            "segment_indices": seg_indices,
        }
        apertures.append(aperture)

    return apertures
