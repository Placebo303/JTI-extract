#!/usr/bin/env python3
"""Raw-aligned FPC JTI extraction.

Preserves the full joint arrival-time structure observed in TimeTagger
raw timestamps.  Only one calibration is applied: a global B-channel
delay correction tau_align_ps.  It is resolved in priority order from
--tau-align-ps, the brightest peak of --peaks-csv, or the A/B time-tag
cross-correlation measured directly on the .ttbin acquisition.

  t_B_corr = t_B - tau_align_ps

Pairs are selected by a single global residual-delay window
  residual_tau = t_B_corr - t_A
  delay_min_ps <= residual_tau <= delay_max_ps

No per-tooth ROI filtering, no peak_id assignment, no per-tooth
matrices, no comb-line rearrangement, no background subtraction.

Output is a true-coordinate, unwrapped, edge-guarded, non-cyclic JTI
matrix on the main diagonal.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import warnings
from pathlib import Path
from typing import Any

import numpy as np

from jti_extract.cli.tdc_layer_scan import load_tags


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json_default(obj: Any) -> Any:
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return str(obj)


def _write_csv_matrix(path: Path, mat: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([""] + list(range(int(mat.shape[1]))))
        for i in range(int(mat.shape[0])):
            w.writerow([i] + [float(x) for x in mat[i, :].tolist()])


def _write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


# ---------------------------------------------------------------------------
# Peak loading
# ---------------------------------------------------------------------------

def load_peaks(peaks_csv: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with peaks_csv.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            row = dict(raw)
            for key in ["delay_ps", "counts", "smoothed_counts", "relative_to_main", "bin_index"]:
                if row.get(key, "") != "":
                    try:
                        row[key] = float(row[key])
                    except (ValueError, TypeError):
                        pass
            rows.append(row)
    return rows


def infer_tau_align_brightest(
    peaks_csv: Path,
    explicit_tau_align: float | None,
) -> tuple[float, str]:
    """Resolve tau_align_ps: explicit > brightest peak in peaks_csv."""
    if explicit_tau_align is not None:
        return float(explicit_tau_align), "explicit"

    peaks = load_peaks(peaks_csv)
    if peaks:
        def _peak_count(peak: dict[str, Any]) -> float:
            try:
                return float(peak.get("counts") or 0.0)
            except (TypeError, ValueError):
                return 0.0

        max_peak = max(peaks, key=_peak_count)
        if _peak_count(max_peak) > 0.0:
            return float(max_peak.get("delay_ps") or 0.0), "brightest_peak"

    raise SystemExit(
        "Cannot determine tau_align_ps: provide --tau-align-ps or a peaks_csv "
        "with at least one peak having counts > 0"
    )


# ---------------------------------------------------------------------------
# Automatic delay calibration from the time-tag correlation
# ---------------------------------------------------------------------------
#
# The A/B coincidence histogram P(tau) = (t_B - t_A) inside a search window is
# exactly the windowed cross-correlation of the two raw time-tag streams, so
# tau_align_ps can be calibrated from the acquisition itself, without an
# external peak table.  Two passes are used:
#   1. coarse: +/- tau_search_window_ps, ~20 ps bins, boxcar smoothing, to find
#      the brightest coincidence cluster robustly against the accidental
#      background;
#   2. fine: +/- refine window around that cluster, ~2 ps bins, with parabolic
#      interpolation for a sub-bin peak position.
# The result is applied as the global B-channel correction
#   t_B_corr = t_B - tau_align_ps

DEFAULT_TAU_SEARCH_WINDOW_PS = 25_000
DEFAULT_TAU_COARSE_BIN_PS = 20
DEFAULT_TAU_SMOOTH_PS = 300
DEFAULT_TAU_REFINE_WINDOW_PS = 300
DEFAULT_TAU_REFINE_BIN_PS = 2
DEFAULT_TAU_REFINE_MARGIN_PS = 300
# Below this many A-B pairs inside the correlation window the automatic delay can
# lock onto a background fluctuation, so the result is reported as untrusted.
TAU_AUTO_MIN_TRUSTED_PAIRS = 5_000


def _block_delta_blocks(
    a_block: np.ndarray,
    t_b: np.ndarray,
    window_ps: np.int64,
    search_center_ps: np.int64,
    max_pairs_per_block: int,
):
    """Yield (t_B - t_A) arrays for one A block, splitting when a block is huge."""
    lo_bound = a_block + search_center_ps - window_ps
    hi_bound = a_block + search_center_ps + window_ps
    left = np.searchsorted(t_b, lo_bound, side="left")
    right = np.searchsorted(t_b, hi_bound, side="right")
    n = right - left
    total = int(n.sum())
    if total <= 0:
        return
    if total > int(max_pairs_per_block) and a_block.size > 1:
        half = int(a_block.size // 2)
        yield from _block_delta_blocks(a_block[:half], t_b, window_ps, search_center_ps, max_pairs_per_block)
        yield from _block_delta_blocks(a_block[half:], t_b, window_ps, search_center_ps, max_pairs_per_block)
        return
    starts = np.repeat(left, n)
    offsets = np.arange(total, dtype=np.int64) - np.repeat(np.cumsum(n) - n, n)
    deltas = t_b[starts + offsets] - np.repeat(a_block, n)
    yield deltas


def iter_delta_blocks(
    t_a: np.ndarray,
    t_b: np.ndarray,
    *,
    half_window_ps: int,
    center_ps: float = 0.0,
    block_events: int = 200_000,
    max_pairs_per_block: int = 4_000_000,
):
    """Yield deltas for all A-B pairs with |(t_B - t_A) - center| <= half window."""
    t_a = np.asarray(t_a, dtype=np.int64)
    t_b = np.asarray(t_b, dtype=np.int64)
    window = np.int64(int(half_window_ps))
    center = np.int64(int(round(float(center_ps))))
    for start in range(0, int(t_a.size), int(block_events)):
        block = t_a[start:start + int(block_events)]
        yield from _block_delta_blocks(block, t_b, window, center, int(max_pairs_per_block))


def delta_histogram(
    t_a: np.ndarray,
    t_b: np.ndarray,
    *,
    half_window_ps: int,
    bin_ps: int,
    center_ps: float = 0.0,
    block_events: int = 200_000,
) -> tuple[np.ndarray, np.ndarray]:
    """Histogram of t_B - t_A over [center - half, center + half].

    This is the sparse (pair-wise) form of the A/B cross-correlation: it stays
    exact for multi-second acquisitions instead of resampling the whole
    timestamp span into fine bins.
    """
    half = int(half_window_ps)
    width = int(bin_ps)
    if half <= 0:
        raise ValueError(f"half_window_ps must be positive, got {half_window_ps}")
    if width <= 0:
        raise ValueError(f"bin_ps must be positive, got {bin_ps}")

    n_bins = (2 * half) // width + 1
    low_edge = float(center_ps) - float(half)
    counts = np.zeros(n_bins, dtype=np.int64)
    for deltas in iter_delta_blocks(
        t_a, t_b, half_window_ps=half, center_ps=center_ps, block_events=block_events
    ):
        idx = np.floor((deltas.astype(np.float64) - low_edge) / float(width)).astype(np.int64)
        valid = (idx >= 0) & (idx < n_bins)
        if np.any(valid):
            counts += np.bincount(idx[valid], minlength=n_bins)
    centers = low_edge + (np.arange(n_bins, dtype=np.float64) + 0.5) * float(width)
    return centers, counts


def _boxcar_smooth(counts: np.ndarray, bins: int) -> np.ndarray:
    k = max(1, int(bins))
    if k == 1:
        return np.asarray(counts, dtype=np.float64)
    kernel = np.ones(k, dtype=np.float64) / float(k)
    return np.convolve(np.asarray(counts, dtype=np.float64), kernel, mode="same")


def _parabolic_peak_offset(y_left: float, y_mid: float, y_right: float) -> float:
    denom = float(y_left) - 2.0 * float(y_mid) + float(y_right)
    if denom == 0.0:
        return 0.0
    return float(np.clip(0.5 * (float(y_left) - float(y_right)) / denom, -0.5, 0.5))


def locate_histogram_peak(
    centers: np.ndarray,
    counts: np.ndarray,
    *,
    smooth_bins: int,
) -> dict[str, Any] | None:
    """Locate the brightest boxcar-smoothed peak with sub-bin interpolation."""
    if centers.size != counts.size or centers.size < 3:
        return None
    step = float(centers[1] - centers[0])
    k = max(1, int(smooth_bins))
    smoothed = _boxcar_smooth(counts, k)
    # Exclude a smoothing-kernel margin: np.convolve zero-pads, so the extreme
    # edges are artificially suppressed and must not be reported as peaks.
    margin = min(k, max(0, smoothed.size // 2 - 2))
    start = margin
    stop = smoothed.size - margin
    inner = smoothed[start:stop]
    if inner.size == 0 or not np.all(np.isfinite(inner)):
        return None
    local = int(np.argmax(inner))
    idx = local + start

    background = float(np.median(inner))
    height = float(smoothed[idx])
    excess = (height - background) * float(k)
    sigma = math.sqrt(max(background, 1e-12) * float(k))

    # Boxcar smoothing turns any peak narrower than the kernel into a flat-topped
    # plateau with an arbitrary argmax bin.  The plateau centre is the unbiased
    # peak position; a single-bin maximum keeps the parabolic sub-bin estimate.
    def _plateau_bounds(pos: int, value: float) -> tuple[int, int]:
        tol = max(1e-6 * value, 0.0)
        lo = pos
        while lo > start and abs(smoothed[lo - 1] - value) <= tol:
            lo -= 1
        hi = pos
        while hi + 1 < stop and abs(smoothed[hi + 1] - value) <= tol:
            hi += 1
        return lo, hi

    def _peak_position(pos: int) -> float:
        lo, hi = _plateau_bounds(pos, float(smoothed[pos]))
        if hi > lo:
            return float(np.mean(centers[lo:hi + 1]))
        left = smoothed[pos - 1] if pos > 0 else smoothed[pos]
        right = smoothed[pos + 1] if pos + 1 < smoothed.size else smoothed[pos]
        return float(centers[pos]) + _parabolic_peak_offset(left, smoothed[pos], right) * step

    peak_ps = _peak_position(idx)

    # Near-equal clusters (comb structure / multi-mode data) make the "brightest"
    # peak a mode selection rather than a unique delay, so report the candidates.
    near_equal_floor = 0.98 * height
    candidates: list[dict[str, Any]] = []
    last_pos = -10 ** 9
    for pos in range(start + 1, stop - 1):
        value = float(smoothed[pos])
        if value < near_equal_floor:
            continue
        if value < smoothed[pos - 1] or value < smoothed[pos + 1]:
            continue
        if pos - last_pos <= k:
            continue
        # Report each cluster by its local background-subtracted centroid in raw
        # counts (one kernel width), which is far more stable than the plateau bin.
        lo = max(0, pos - k)
        hi = min(counts.size, pos + k + 1)
        weights_c = np.clip(np.asarray(counts[lo:hi], dtype=np.float64) - background, 0.0, None)
        if float(weights_c.sum()) > 0.0:
            candidate_ps = float(
                (np.asarray(centers[lo:hi], dtype=np.float64) * weights_c).sum()
                / float(weights_c.sum())
            )
        else:
            candidate_ps = _peak_position(pos)
        candidates.append(
            {
                "peak_ps": candidate_ps,
                "smoothed_counts": value,
            }
        )
        last_pos = pos
        if len(candidates) >= 10:
            break

    return {
        "peak_ps": peak_ps,
        "peak_bin": idx,
        "peak_smoothed_counts": height,
        "background_smoothed_counts": background,
        "significance": float(excess / sigma) if sigma > 0.0 else 0.0,
        "at_search_edge": bool(idx < k + 1 or idx > smoothed.size - k - 2),
        "smooth_bins": k,
        "bin_ps": step,
        "near_equal_candidates": candidates,
        "n_near_equal": len(candidates),
    }


def refine_tau_by_local_centroid(
    t_a: np.ndarray,
    t_b: np.ndarray,
    coarse_peak_ps: float,
    *,
    half_window_ps: int = DEFAULT_TAU_REFINE_WINDOW_PS,
    bin_ps: int = DEFAULT_TAU_REFINE_BIN_PS,
    background_margin_ps: int = DEFAULT_TAU_REFINE_MARGIN_PS,
    block_events: int = 200_000,
) -> dict[str, Any] | None:
    """Re-centre the coarse peak on the centroid of its coincidence cluster.

    The fine histogram keeps 2 ps bins, but instead of taking another argmax
    (which can hop between near-equal comb teeth inside one broad cluster) the
    cluster centre is taken as the background-subtracted centre of mass inside
    +/- half_window_ps.  The background is estimated from the ring outside that
    window, so no external flat-background assumption is needed.
    """
    half = max(int(bin_ps), int(half_window_ps))
    margin = max(int(bin_ps), int(background_margin_ps))
    bin_width = max(1, int(bin_ps))
    centers, counts = delta_histogram(
        t_a,
        t_b,
        half_window_ps=half + margin,
        bin_ps=bin_width,
        center_ps=coarse_peak_ps,
        block_events=block_events,
    )
    offset = centers - float(coarse_peak_ps)
    inside = np.abs(offset) <= float(half)
    ring = (~inside) & (np.abs(offset) <= float(half + margin))
    if not np.any(inside) or not np.any(ring):
        return None
    background = float(np.median(counts[ring]))
    if background <= 0.0:
        # Sparse acquisitions can have a zero median; the mean is the Poisson MLE.
        background = float(np.mean(counts[ring]))
    inside_bins = int(np.count_nonzero(inside))
    weights = np.clip(counts[inside].astype(np.float64) - background, 0.0, None)
    total_weight = float(weights.sum())
    if total_weight <= 0.0:
        return None
    centroid = float((centers[inside] * weights).sum() / total_weight)
    background_total = background * float(inside_bins)
    sigma = math.sqrt(max(background_total, 1.0))
    return {
        "method": "local_centroid",
        "peak_ps": centroid,
        "half_window_ps": half,
        "background_margin_ps": margin,
        "bin_ps": bin_width,
        "n_pairs": int(counts[inside].sum()),
        "background_per_bin": background,
        "excess_counts": total_weight,
        "significance": float(total_weight / sigma),
    }


def estimate_tau_align_from_tags(
    t_a: np.ndarray,
    t_b: np.ndarray,
    *,
    search_window_ps: int = DEFAULT_TAU_SEARCH_WINDOW_PS,
    coarse_bin_ps: int = DEFAULT_TAU_COARSE_BIN_PS,
    smooth_ps: int = DEFAULT_TAU_SMOOTH_PS,
    refine: bool = True,
    refine_window_ps: int = DEFAULT_TAU_REFINE_WINDOW_PS,
    refine_bin_ps: int = DEFAULT_TAU_REFINE_BIN_PS,
    block_events: int = 200_000,
) -> dict[str, Any]:
    """Calibrate the global delay directly from the A/B time-tag correlation.

    The returned dict carries tau_align_ps (integer ps to apply) and
    tau_align_ps_exact (interpolated estimate) plus per-pass diagnostics.
    """
    t_a = np.asarray(t_a, dtype=np.int64)
    t_b = np.asarray(t_b, dtype=np.int64)
    if t_a.size == 0 or t_b.size == 0:
        raise RuntimeError(
            "cannot calibrate the delay from correlation: one of the selected channels has no events"
        )

    search_window = int(search_window_ps)
    coarse_bin = max(1, int(coarse_bin_ps))
    centers, counts = delta_histogram(
        t_a, t_b, half_window_ps=search_window, bin_ps=coarse_bin, block_events=block_events
    )
    n_pairs = int(counts.sum())
    if n_pairs <= 0:
        raise RuntimeError(
            f"cannot calibrate the delay from correlation: no A-B pairs within "
            f"+/-{search_window} ps. Check --raw-ch-a-id/--raw-ch-b-id and --tau-search-window-ps."
        )
    smooth_bins = max(1, int(round(float(smooth_ps) / float(coarse_bin))))
    coarse_peak = locate_histogram_peak(centers, counts, smooth_bins=smooth_bins)
    if coarse_peak is None:
        raise RuntimeError("cannot calibrate the delay from correlation: empty correlation histogram")

    info: dict[str, Any] = {
        "method": "auto_correlation",
        "search_window_ps": search_window,
        "coarse_bin_ps": coarse_bin,
        "smooth_ps": int(smooth_ps),
        "n_pairs": n_pairs,
        "coarse": coarse_peak,
    }

    tau_exact = float(coarse_peak["peak_ps"])
    if refine:
        refined = refine_tau_by_local_centroid(
            t_a,
            t_b,
            tau_exact,
            half_window_ps=refine_window_ps,
            bin_ps=refine_bin_ps,
            block_events=block_events,
        )
        if refined is not None:
            info["refine"] = refined
            # Only trust the refined centre when the cluster excess is significant.
            if refined["significance"] >= 5.0:
                tau_exact = float(refined["peak_ps"])
            else:
                info["refine_used"] = False

    info["tau_align_ps_exact"] = tau_exact
    info["tau_align_ps"] = int(round(tau_exact))
    return info


def resolve_tau_align_ps(
    *,
    t_a: np.ndarray,
    t_b: np.ndarray,
    explicit_tau_align_ps: float | None,
    peaks_csv: Path | None,
    force_auto: bool,
    auto_kwargs: dict[str, Any],
) -> tuple[float, str, dict[str, Any] | None]:
    """Resolve tau_align_ps: explicit > ttbin correlation > peaks-CSV brightest peak."""
    if explicit_tau_align_ps is not None:
        return float(explicit_tau_align_ps), "explicit", None
    if force_auto or peaks_csv is None:
        info = estimate_tau_align_from_tags(t_a, t_b, **auto_kwargs)
        return float(info["tau_align_ps"]), "auto_correlation", info
    if not peaks_csv.exists():
        raise SystemExit(
            f"peaks CSV not found: {peaks_csv}. Drop --peaks-csv to calibrate the "
            f"delay from the .ttbin time-tag correlation instead."
        )
    tau, source = infer_tau_align_brightest(peaks_csv, None)
    return float(tau), source, None


def _measure_residual_peak_ps(
    t_a: np.ndarray,
    t_b: np.ndarray,
    tau_align_ps: float,
    *,
    tau_auto: dict[str, Any] | None,
    auto_kwargs: dict[str, Any],
) -> float:
    """Residual delay peak (ps) after applying tau_align_ps, plus a trust verdict.

    The verdict guards --auto-delay-range: without enough A-B pairs (or without a
    >=5 sigma correlation peak) the measured residual peak is a background
    fluctuation and the window must stay centred on 0 ps.
    """
    if tau_auto is not None:
        residual = float(tau_auto["tau_align_ps_exact"]) - float(tau_align_ps)
        n_pairs = int(tau_auto["n_pairs"])
        return residual, n_pairs >= TAU_AUTO_MIN_TRUSTED_PAIRS, {
            "n_pairs": n_pairs,
            "significance": None,
        }
    probe = estimate_tau_align_from_tags(t_a, t_b, **auto_kwargs)
    n_pairs = int(probe["n_pairs"])
    refined = probe.get("refine")
    refine_used = refined is not None and bool(probe.get("refine_used", True))
    peak_info = refined if refine_used else probe["coarse"]
    significance = float(peak_info["significance"])
    residual = float(peak_info["peak_ps"]) - float(tau_align_ps)
    trusted = n_pairs >= TAU_AUTO_MIN_TRUSTED_PAIRS and significance >= 5.0
    return residual, trusted, {"n_pairs": n_pairs, "significance": significance}


# ---------------------------------------------------------------------------
# Core: raw-aligned JTI construction (chunk streaming)
# ---------------------------------------------------------------------------

def build_raw_aligned_jti(
    t_a: np.ndarray,
    t_b: np.ndarray,
    tau_align_ps: float,
    *,
    bw: int,
    dim: int,
    origin_ps: int,
    guard_bins: int,
    delay_min_ps: int,
    delay_max_ps: int,
    chunk_size: int = 50_000,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Construct raw-aligned JTI with chunk-streamed pairing.

    For each chunk of A events, find B events within the global
    residual-delay window, then directly compute frame/bin coordinates
    and accumulate into H and the residual-tau histogram without
    expanding the full paired arrays.

    Returns (H, meta) where meta contains all pair-count diagnostics
    and the residual-tau histogram (bins, counts).
    """
    tau_align = np.int64(int(round(float(tau_align_ps))))
    t_b_corr = t_b - tau_align  # globally corrected B timestamps

    origin = np.int64(origin_ps)
    bw_i = np.int64(bw)
    dim_i = np.int64(dim)
    frame_period = np.int64(dim) * bw_i
    guard_ps = np.int64(guard_bins) * bw_i

    dmin = np.int64(delay_min_ps)
    dmax = np.int64(delay_max_ps)

    # Residual-tau histogram bins (edges cover [dmin, dmax] inclusive of endpoints)
    n_tau_bins = int((dmax - dmin) // bw_i) + 1
    tau_bin_edges = np.linspace(float(dmin), float(dmin + n_tau_bins * bw_i), n_tau_bins + 1)
    tau_hist = np.zeros(n_tau_bins, dtype=np.int64)

    H = np.zeros((dim, dim), dtype=np.float64)

    accepted_pairs_input = 0
    cross_frame_rejected = 0
    edge_rejected = 0
    invalid_bin = 0

    for start in range(0, t_a.size, chunk_size):
        a_chunk = t_a[start : start + chunk_size]

        # Find B events in global delay window for each A event
        left = np.searchsorted(t_b_corr, a_chunk + dmin, side="left")
        right = np.searchsorted(t_b_corr, a_chunk + dmax, side="right")
        pair_counts = right - left
        accepted_pairs_input += int(np.sum(pair_counts))

        # Expand per A event (chunk-size bounded)
        for k in range(a_chunk.size):
            lo, hi = int(left[k]), int(right[k])
            if lo >= hi:
                continue

            a_val = np.int64(a_chunk[k])
            b_vals = t_b_corr[lo:hi]

            # --- residual tau histogram (before frame filter) ---
            res_tau = b_vals - a_val
            hist_idx = ((res_tau - dmin) // bw_i).astype(np.int64)
            valid_hist = (hist_idx >= 0) & (hist_idx < n_tau_bins)
            if np.any(valid_hist):
                np.add.at(tau_hist, hist_idx[valid_hist], 1)

            # --- frame coordinates (scalar A, vector B) ---
            ua = a_val - origin                    # scalar
            ub = b_vals - origin                   # vector

            frame_a = ua // frame_period           # scalar
            frame_b = ub // frame_period           # vector

            same = frame_a == frame_b              # boolean vector (broadcast)
            n_cross = int(np.sum(~same))
            cross_frame_rejected += n_cross

            if not np.any(same):
                continue

            ub_s = ub[same]
            xb = ub_s - frame_a * frame_period     # vector (frame-local B)

            # xa is scalar (same for all same-frame pairs from this A event)
            xa = ua - frame_a * frame_period

            # Edge guard
            in_guard = (
                (xa >= guard_ps) & (xa < frame_period - guard_ps) &
                (xb >= guard_ps) & (xb < frame_period - guard_ps)
            )
            edge_rejected += int(xb.size - np.sum(in_guard))

            if not np.any(in_guard):
                continue

            xb_g = xb[in_guard]

            # Bin into matrix (xa is scalar → same row for all)
            j = xb_g // bw_i
            valid_bins = (j >= 0) & (j < dim_i)
            invalid_bin += int(j.size - np.sum(valid_bins))
            if np.any(valid_bins):
                i_scalar = int(xa // bw_i)
                if 0 <= i_scalar < dim:
                    np.add.at(H, (i_scalar, j[valid_bins]), 1.0)

    retained = int(np.sum(H))

    meta: dict[str, Any] = {
        "accepted_pairs_input": accepted_pairs_input,
        "cross_frame_rejected": cross_frame_rejected,
        "edge_rejected": edge_rejected,
        "invalid_bin": invalid_bin,
        "retained_in_jti": retained,
        "retained_fraction": retained / accepted_pairs_input if accepted_pairs_input > 0 else 0.0,
        "tau_hist_bin_edges": tau_bin_edges,
        "tau_hist_counts": tau_hist,
    }
    return H, meta


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def _plot_png(path: Path, mat: np.ndarray, *, title: str) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        raise RuntimeError(f"matplotlib is required for PNG output: {exc}") from exc

    n = int(mat.shape[0])
    fig, ax = plt.subplots(figsize=(6.0, 5.0), dpi=160)
    im = ax.imshow(
        mat,
        origin="lower",
        cmap="viridis",
        extent=[-0.5, n - 0.5, -0.5, n - 0.5],
        aspect="equal",
    )
    ax.set_title(title)
    ax.set_xlabel("Signal time-bin index")
    ax.set_ylabel("Idler time-bin index")
    plt.colorbar(im, ax=ax, label="Counts")
    fig.tight_layout()
    fig.savefig(str(path))
    plt.close(fig)


def _compute_diagonal_diagnostics(H: np.ndarray, bw: int) -> dict[str, Any]:
    """Compute weighted diagonal-offset diagnostics for JTI matrix."""
    dim = H.shape[0]
    total = float(np.sum(H))
    if total <= 0:
        return {
            "weighted_mean_diag_offset_bins": 0.0,
            "weighted_std_diag_offset_bins": 0.0,
            "weighted_mean_diag_offset_ps": 0.0,
            "weighted_std_diag_offset_ps": 0.0,
            "max_diag_offset_bins": 0,
            "max_diag_offset_ps": 0,
        }
    i_idx, j_idx = np.meshgrid(np.arange(dim), np.arange(dim), indexing="ij")
    delta = j_idx - i_idx  # offset in bins
    mean_bins = float(np.sum(H * delta) / total)
    std_bins = float(np.sqrt(np.sum(H * (delta - mean_bins) ** 2) / total))
    max_abs = int(np.max(np.abs(delta[H > 0]))) if np.any(H > 0) else 0
    return {
        "weighted_mean_diag_offset_bins": round(mean_bins, 4),
        "weighted_std_diag_offset_bins": round(std_bins, 4),
        "weighted_mean_diag_offset_ps": round(mean_bins * bw, 2),
        "weighted_std_diag_offset_ps": round(std_bins * bw, 2),
        "max_diag_offset_bins": int(max_abs),
        "max_diag_offset_ps": int(max_abs) * bw,
    }


def _compute_svd_k(H: np.ndarray) -> dict[str, Any]:
    """Compute Schmidt-like K from JTI matrix via SVD of sqrt(P)."""
    total = float(np.sum(H))
    if total <= 0:
        return {
            "K_raw_aligned": float("nan"),
            "purity": float("nan"),
            "n_singular_values": 0,
            "singular_values": [],
            "lambda_weights": [],
        }
    P = H / total
    A = np.sqrt(P)
    s = np.linalg.svd(A, compute_uv=False)
    s = s[s > 1e-12]
    if s.size == 0:
        return {
            "K_raw_aligned": float("nan"),
            "purity": float("nan"),
            "n_singular_values": 0,
            "singular_values": [],
            "lambda_weights": [],
        }
    weights = s ** 2
    weights = weights / np.sum(weights)
    purity = float(np.sum(weights ** 2))
    K = float(1.0 / purity)
    return {
        "K_raw_aligned": K,
        "purity": purity,
        "n_singular_values": int(s.size),
        "singular_values": s.tolist(),
        "lambda_weights": weights.tolist(),
    }


def _plot_residual_tau_histogram(
    path: Path,
    bin_centers: np.ndarray,
    counts: np.ndarray,
    *,
    tau_align_ps: float,
) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        raise RuntimeError(f"matplotlib is required for PNG output: {exc}") from exc

    fig, ax = plt.subplots(figsize=(7.0, 4.0), dpi=150)
    ax.plot(bin_centers, counts, linewidth=0.8, color="steelblue")
    ax.fill_between(bin_centers, counts, alpha=0.15, color="steelblue")

    # Annotate residual_tau = 0
    ax.axvline(0, color="red", linestyle="--", linewidth=0.8, alpha=0.7, label="residual_tau = 0 ps")
    ax.legend(loc="upper right", fontsize=8)

    ax.set_xlabel("Residual delay (ps)")
    ax.set_ylabel("Counts")
    ax.set_title(
        f"Residual delay histogram (tau_align_ps = {tau_align_ps:.0f} ps)",
        fontsize=10,
    )
    ax.ticklabel_format(style="sci", axis="y", scilimits=(0, 0))
    fig.tight_layout()
    fig.savefig(str(path))
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def run_raw_aligned(args: argparse.Namespace) -> dict[str, Any]:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    bw = int(args.binwidth_ps)
    dim = int(args.dimensions)
    guard_bins = int(args.guard_bins)
    origin_ps = int(args.frame_origin_ps)
    chunk_size = int(args.chunk_size)
    frame_period_ps = dim * bw

    # --- Load timetags first: both the delay calibration and (optionally) the
    #     residual-delay window are derived from the acquisition itself ---
    ttbin = Path(args.ttbin)
    cache_dir = out_dir / "_tag_cache"
    tags = load_tags(ttbin, cache_dir, int(args.raw_ch_a_id), int(args.raw_ch_b_id), args.max_events)
    if tags.t_a.size == 0 or tags.t_b.size == 0:
        channel_counts = tags.meta.get("channel_counts") or {}
        present = sorted(int(k) for k in channel_counts.keys())
        raise RuntimeError(
            f"No events found for channel A={int(args.raw_ch_a_id)} / "
            f"B={int(args.raw_ch_b_id)} in {ttbin}. "
            f"Channels present in the file: {present if present else 'unknown'}. "
            f"Check --raw-ch-a-id / --raw-ch-b-id."
        )
    print(f"Loaded {tags.t_a.size:,} A events, {tags.t_b.size:,} B events from {ttbin.name}")

    # --- Resolve tau_align_ps: explicit > ttbin correlation > peaks CSV ---
    peaks_csv = Path(args.peaks_csv) if args.peaks_csv else None
    auto_kwargs: dict[str, Any] = {
        "search_window_ps": int(args.tau_search_window_ps),
        "coarse_bin_ps": int(args.tau_coarse_bin_ps),
        "smooth_ps": int(args.tau_smooth_ps),
        "refine": bool(args.tau_refine),
        "refine_window_ps": int(args.tau_refine_window_ps),
        "refine_bin_ps": int(args.tau_refine_bin_ps),
    }
    tau_align_ps, tau_align_source, tau_auto = resolve_tau_align_ps(
        t_a=tags.t_a,
        t_b=tags.t_b,
        explicit_tau_align_ps=args.tau_align_ps,
        peaks_csv=peaks_csv,
        force_auto=bool(args.tau_auto),
        auto_kwargs=auto_kwargs,
    )
    print(f"tau_align_ps = {tau_align_ps:.0f} ps (source: {tau_align_source})")
    if tau_auto is not None:
        coarse_peak = tau_auto["coarse"]
        refined = tau_auto.get("refine")
        print(
            f"  correlation: {tau_auto['n_pairs']:,} A-B pairs within "
            f"+/-{tau_auto['search_window_ps']} ps | coarse peak = "
            f"{coarse_peak['peak_ps']:.1f} ps ({coarse_peak['bin_ps']:g} ps bins, "
            f"{coarse_peak['significance']:.1f} sigma)"
        )
        if refined is not None:
            used = bool(tau_auto.get("refine_used", True))
            print(
                f"  refined: centre of +/-{refined['half_window_ps']} ps cluster = "
                f"{refined['peak_ps']:.2f} ps ({refined['bin_ps']:g} ps bins, "
                f"{refined['significance']:.1f} sigma, {'used' if used else 'rejected: weak'})"
            )
        if coarse_peak["significance"] < 5.0:
            print(
                "  WARNING: weak correlation peak (<5 sigma); the delay calibration may be "
                "unreliable. Check the channels/window or pass --tau-align-ps explicitly."
            )
        if int(tau_auto["n_pairs"]) < TAU_AUTO_MIN_TRUSTED_PAIRS:
            print(
                f"  WARNING: only {int(tau_auto['n_pairs']):,} A-B pairs inside the search window; "
                "the automatic delay can lock onto a background fluctuation. Verify "
                "residual_tau_histogram.png or pass --tau-align-ps."
            )
        if int(coarse_peak.get("n_near_equal", 0)) > 1:
            print(
                f"  note: {coarse_peak['n_near_equal']} near-equal correlation clusters "
                "(comb / multi-mode structure); the delay is a mode selection - pin it with "
                "--tau-align-ps or --peaks-csv when comparing runs."
            )
        if coarse_peak.get("at_search_edge"):
            print(
                f"  WARNING: correlation peak sits at the search-window edge; widen "
                f"--tau-search-window-ps (currently {tau_auto['search_window_ps']} ps)."
            )

    # --- Delay range resolution ---
    default_half_ps = frame_period_ps // 2 - guard_bins * bw
    delay_center_ps = 0
    delay_range_auto_centered = False
    if args.delay_min_ps is not None and args.delay_max_ps is not None:
        delay_min_ps = int(args.delay_min_ps)
        delay_max_ps = int(args.delay_max_ps)
    else:
        if bool(args.auto_delay_range):
            residual_peak_ps, residual_trusted, residual_info = _measure_residual_peak_ps(
                tags.t_a,
                tags.t_b,
                tau_align_ps,
                tau_auto=tau_auto,
                auto_kwargs=auto_kwargs,
            )
            if residual_trusted:
                delay_center_ps = int(round(residual_peak_ps))
                delay_range_auto_centered = True
                print(
                    f"NOTE: --auto-delay-range centers the residual window on the measured "
                    f"peak at {residual_peak_ps:+.1f} ps."
                )
            else:
                significance = residual_info.get("significance")
                significance_text = "n/a" if significance is None else f"{significance:.1f} sigma"
                print(
                    f"  WARNING: --auto-delay-range measured a residual peak at "
                    f"{residual_peak_ps:+.1f} ps but it is not trustworthy "
                    f"({residual_info['n_pairs']:,} pairs, {significance_text}); "
                    f"keeping the window centred at 0 ps. "
                    f"Pass --tau-align-ps / --peaks-csv or inspect residual_tau_histogram.png."
                )
        if args.delay_window_ps is not None:
            half_ps = int(args.delay_window_ps)
        else:
            half_ps = default_half_ps
            print(
                f"NOTE: No --delay-min-ps/--delay-max-ps or --delay-window-ps specified.\n"
                f"      Using default delay range "
                f"[{delay_center_ps - half_ps}, {delay_center_ps + half_ps}] ps.\n"
                f"      Inspect residual_tau_histogram.png if the residual peak is not near 0 ps."
            )
        delay_min_ps, delay_max_ps = delay_center_ps - half_ps, delay_center_ps + half_ps

    delay_span_ps = int(delay_max_ps - delay_min_ps)
    delay_span_warning: str | None = None
    if delay_span_ps >= frame_period_ps:
        delay_span_warning = (
            f"delay_span_ps ({delay_span_ps}) >= frame_period_ps ({frame_period_ps}), "
            f"expect heavy cross-frame rejection"
        )
        warnings.warn(delay_span_warning, stacklevel=2)
        print(f"WARNING: {delay_span_warning}")

    print(f"Delay range: [{delay_min_ps}, {delay_max_ps}] ps  (span = {delay_span_ps} ps)")

    # --- Build raw-aligned JTI ---
    H, jti_meta = build_raw_aligned_jti(
        tags.t_a, tags.t_b, tau_align_ps,
        bw=bw, dim=dim, origin_ps=origin_ps, guard_bins=guard_bins,
        delay_min_ps=delay_min_ps, delay_max_ps=delay_max_ps,
        chunk_size=chunk_size,
    )

    print(f"accepted_pairs_input  = {jti_meta['accepted_pairs_input']:,}")
    print(f"cross_frame_rejected  = {jti_meta['cross_frame_rejected']:,}")
    print(f"edge_rejected         = {jti_meta['edge_rejected']:,}")
    print(f"invalid_bin           = {jti_meta['invalid_bin']:,}")
    print(f"retained_in_jti       = {jti_meta['retained_in_jti']:,}")

    # --- Save JTI matrix ---
    csv_path = out_dir / "H_raw_aligned.csv"
    _write_csv_matrix(csv_path, H)
    print(f"Saved: {csv_path}")

    npz_path = out_dir / "H_raw_aligned.npz"
    np.savez_compressed(
        str(npz_path),
        jti_counts=H,
        dimension=dim,
        bin_width_ps=bw,
        frame_origin_ps=origin_ps,
        tau_align_ps=tau_align_ps,
        delay_min_ps=delay_min_ps,
        delay_max_ps=delay_max_ps,
        guard_bins=guard_bins,
    )
    print(f"Saved: {npz_path}")

    png_path = out_dir / "H_raw_aligned.png"
    _plot_png(png_path, H, title="Raw-aligned FPC JTI")
    print(f"Saved: {png_path}")

    # --- Residual-tau histogram ---
    tau_bin_edges = jti_meta["tau_hist_bin_edges"]
    tau_hist = jti_meta["tau_hist_counts"]
    bin_centers = (tau_bin_edges[:-1] + tau_bin_edges[1:]) / 2.0

    tau_csv_path = out_dir / "residual_tau_histogram.csv"
    _write_csv_rows(
        tau_csv_path,
        ["residual_tau_ps", "counts"],
        [{"residual_tau_ps": float(c), "counts": int(n)} for c, n in zip(bin_centers, tau_hist)],
    )
    print(f"Saved: {tau_csv_path}")

    tau_png_path = out_dir / "residual_tau_histogram.png"
    _plot_residual_tau_histogram(tau_png_path, bin_centers, tau_hist, tau_align_ps=tau_align_ps)
    print(f"Saved: {tau_png_path}")

    # --- Metadata ---
    count_balance_error = (
        jti_meta["accepted_pairs_input"]
        - jti_meta["retained_in_jti"]
        - jti_meta["cross_frame_rejected"]
        - jti_meta["edge_rejected"]
        - jti_meta["invalid_bin"]
    )
    diag_diag = _compute_diagonal_diagnostics(H, bw)

    raw_aligned_meta = {
        "analysis_mode": "raw_aligned_fpc_jti",
        "pairing_mode": "global_residual_delay_window",
        "tau_align_ps": tau_align_ps,
        "tau_align_source": tau_align_source,
        "tau_auto": tau_auto,
        "delay_window_center_ps": delay_center_ps,
        "delay_range_auto_centered": delay_range_auto_centered,
        "frame_origin_ps": origin_ps,
        "binwidth_ps": bw,
        "dimension": dim,
        "frame_period_ps": frame_period_ps,
        "guard_bins": guard_bins,
        "delay_min_ps": delay_min_ps,
        "delay_max_ps": delay_max_ps,
        "delay_span_ps": delay_span_ps,
        "delay_span_exceeds_frame_period": delay_span_ps >= frame_period_ps,
        "delay_span_warning": delay_span_warning,
        "background_subtracted": False,
        "tooth_roi_filtered": False,
        "line_rearranged": False,
        "peak_id_assigned": False,
        "per_tooth_matrix_generated": False,
        "raw_noise_preserved": True,
        "accepted_pairs_input": jti_meta["accepted_pairs_input"],
        "retained_in_jti": jti_meta["retained_in_jti"],
        "cross_frame_rejected": jti_meta["cross_frame_rejected"],
        "edge_rejected": jti_meta["edge_rejected"],
        "invalid_bin": jti_meta["invalid_bin"],
        "count_balance_error": count_balance_error,
        **diag_diag,
    }

    # --- SVD/K computation (optional, must run before the metadata is written
    #     so that K/purity/lambda fields land in raw_aligned_meta.json) ---
    if getattr(args, "compute_svd", False):
        svd = _compute_svd_k(H)
        raw_aligned_meta.update(svd)

        # Lambda cumulative sums
        lam = np.array(svd["lambda_weights"])
        cumsum = np.cumsum(lam)
        lambda1 = float(lam[0]) if lam.size > 0 else float("nan")
        lambda2 = float(lam[1]) if lam.size > 1 else float("nan")
        lambda3 = float(lam[2]) if lam.size > 2 else float("nan")
        lambda5_cumsum = float(cumsum[4]) if lam.size > 4 else float("nan")
        lambda10_cumsum = float(cumsum[9]) if lam.size > 9 else float("nan")
        raw_aligned_meta.update(
            {
                "lambda1": lambda1,
                "lambda2": lambda2,
                "lambda3": lambda3,
                "lambda5_cumsum": lambda5_cumsum,
                "lambda10_cumsum": lambda10_cumsum,
            }
        )

        # Write summary.csv
        guard_ps = guard_bins * bw
        summary_row = {
            "tau_align_ps": tau_align_ps,
            "tau_align_source": tau_align_source,
            "binwidth_ps": bw,
            "dimension": dim,
            "frame_period_ps": frame_period_ps,
            "guard_bins": guard_bins,
            "guard_ps": guard_ps,
            "delay_min_ps": delay_min_ps,
            "delay_max_ps": delay_max_ps,
            "accepted_pairs_input": jti_meta["accepted_pairs_input"],
            "retained_in_jti": jti_meta["retained_in_jti"],
            "retained_fraction": round(jti_meta["retained_fraction"], 6),
            "cross_frame_rejected": jti_meta["cross_frame_rejected"],
            "edge_rejected": jti_meta["edge_rejected"],
            "invalid_bin": jti_meta["invalid_bin"],
            "count_balance_error": count_balance_error,
            "weighted_mean_diag_offset_ps": diag_diag["weighted_mean_diag_offset_ps"],
            "weighted_std_diag_offset_ps": diag_diag["weighted_std_diag_offset_ps"],
            "K_raw_aligned": svd["K_raw_aligned"],
            "purity": svd["purity"],
            "n_singular_values": svd["n_singular_values"],
            "lambda1": lambda1,
            "lambda2": lambda2,
            "lambda3": lambda3,
            "lambda5_cumsum": lambda5_cumsum,
            "lambda10_cumsum": lambda10_cumsum,
        }
        summary_path = out_dir / "summary.csv"
        _write_csv_rows(summary_path, list(summary_row.keys()), [summary_row])
        print(f"Saved: {summary_path}")
        print(f"  K_raw_aligned = {svd['K_raw_aligned']:.4f}, purity = {svd['purity']:.6f}, "
              f"n_sv = {svd['n_singular_values']}")

    meta_path = out_dir / "raw_aligned_meta.json"
    meta_path.write_text(
        json.dumps(raw_aligned_meta, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    print(f"Saved: {meta_path}")

    return raw_aligned_meta


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Raw-aligned FPC JTI extraction with global residual-delay window.",
    )

    # Required
    ap.add_argument("--ttbin", required=True, help="Path to .1.ttbin file.")
    ap.add_argument("--out", required=True, help="Output directory.")

    # Tau alignment (delay calibration)
    ap.add_argument("--peaks-csv", default=None,
                    help="Optional peaks CSV with delay_ps/counts columns used to infer "
                         "tau_align_ps from its brightest peak. Omit it to calibrate the delay "
                         "directly from the .ttbin time-tag correlation.")
    ap.add_argument("--tau-align-ps", type=float, default=None,
                    help="Explicit tau_align_ps (ps); overrides every automatic estimate.")
    ap.add_argument("--tau-auto", action="store_true", default=False,
                    help="Calibrate tau_align_ps from the .ttbin time-tag correlation even "
                         "when --peaks-csv is given.")
    ap.add_argument("--tau-search-window-ps", type=int, default=DEFAULT_TAU_SEARCH_WINDOW_PS,
                    help="Half-width of the A-B correlation search window (ps).")
    ap.add_argument("--tau-coarse-bin-ps", type=int, default=DEFAULT_TAU_COARSE_BIN_PS,
                    help="Coarse correlation histogram bin width (ps).")
    ap.add_argument("--tau-smooth-ps", type=int, default=DEFAULT_TAU_SMOOTH_PS,
                    help="Boxcar smoothing width applied to the coarse correlation histogram (ps).")
    ap.add_argument("--tau-refine", action=argparse.BooleanOptionalAction, default=True,
                    help="Refine the coarse delay with a fine second correlation pass (default: on).")
    ap.add_argument("--tau-refine-window-ps", type=int, default=DEFAULT_TAU_REFINE_WINDOW_PS,
                    help="Half-width of the cluster used for the fine centroid re-centring (ps).")
    ap.add_argument("--tau-refine-bin-ps", type=int, default=DEFAULT_TAU_REFINE_BIN_PS,
                    help="Fine correlation histogram bin width used by the centroid pass (ps).")

    # Frame geometry
    ap.add_argument("--frame-origin-ps", type=float, default=0.0,
                    help="Frame origin (ps).")
    ap.add_argument("--binwidth-ps", type=int, default=20,
                    help="Bin width (ps).")
    ap.add_argument("--dimensions", type=int, default=128,
                    help="JTI dimension.")
    ap.add_argument("--guard-bins", type=int, default=2,
                    help="Edge guard bins.")

    # Delay range
    ap.add_argument("--delay-min-ps", type=int, default=None,
                    help="Lower bound of global residual-delay window (ps).")
    ap.add_argument("--delay-max-ps", type=int, default=None,
                    help="Upper bound of global residual-delay window (ps).")
    ap.add_argument("--delay-window-ps", type=int, default=None,
                    help="Shorthand for the residual-delay half-width: delay_min=-W, delay_max=+W "
                         "(or center+/-W with --auto-delay-range).")
    ap.add_argument("--auto-delay-range", action="store_true", default=False,
                    help="Center the residual-delay window on the measured residual peak instead "
                         "of 0 ps; useful after an explicit or peaks-CSV tau that sits off zero.")

    # TimeTagger channels
    ap.add_argument("--raw-ch-a-id", type=int, default=2,
                    help="TimeTagger channel A.")
    ap.add_argument("--raw-ch-b-id", type=int, default=3,
                    help="TimeTagger channel B.")

    # Performance / limits
    ap.add_argument("--max-events", type=int, default=None,
                    help="Max events to read.")
    ap.add_argument("--chunk-size", type=int, default=50_000,
                    help="Chunk size for streaming pairing.")
    ap.add_argument("--compute-svd", action="store_true", default=False,
                    help="Compute SVD/K and write summary.csv.")

    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    meta = run_raw_aligned(args)

    print("\n=== Raw-Aligned FPC JTI ===")
    print(f"  tau_align_ps = {meta['tau_align_ps']:.0f} ({meta['tau_align_source']})")
    print(f"  delay range  = [{meta['delay_min_ps']}, {meta['delay_max_ps']}] ps")
    print(f"  retained     = {meta['retained_in_jti']:,} / {meta['accepted_pairs_input']:,}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
