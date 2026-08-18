#!/usr/bin/env python3
"""Raw-aligned FPC JTI extraction.

Preserves the full joint arrival-time structure observed in TimeTagger
raw timestamps.  Only one calibration is applied: a global B-channel
delay correction derived from the brightest peak in pminus_peaks.csv.

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
import sys
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
        max_peak = max(peaks, key=lambda p: float(p.get("counts", 0)))
        delay = float(max_peak.get("delay_ps", 0))
        if delay != 0:
            return delay, "brightest_peak"

    raise SystemExit(
        "Cannot determine tau_align_ps: provide --tau-align-ps or a peaks_csv "
        "with at least one peak having counts > 0"
    )


def same_frame_delay_range_ps(dim: int, bw: int, guard_bins: int) -> tuple[int, int]:
    """Return the delay range that covers all same-frame, guard-kept JTI bins."""
    usable_bins = int(dim) - 2 * int(guard_bins)
    if usable_bins <= 0:
        raise ValueError(f"dimension ({dim}) must be larger than 2*guard_bins ({2 * int(guard_bins)})")
    max_abs_ps = usable_bins * int(bw)
    return -max_abs_ps, max_abs_ps


def detect_residual_peaks(
    bin_centers: np.ndarray,
    counts: np.ndarray,
    *,
    min_relative_height: float = 0.05,
) -> list[dict[str, Any]]:
    """Return separated local maxima in a residual-delay histogram.

    This deliberately uses one-bin local maxima: the histogram bin width is the
    analysis bin width, so peak merging is left to the explicit peak window.
    """
    if bin_centers.size != counts.size:
        raise ValueError("bin_centers and counts must have the same length")
    if not 0.0 <= min_relative_height <= 1.0:
        raise ValueError("min_relative_height must be in [0, 1]")
    if counts.size < 3 or int(np.max(counts, initial=0)) == 0:
        return []
    threshold = float(np.max(counts)) * min_relative_height
    peaks: list[dict[str, Any]] = []
    for i in range(1, counts.size - 1):
        if counts[i] >= threshold and counts[i] > counts[i - 1] and counts[i] >= counts[i + 1]:
            peaks.append({"delay_ps": float(bin_centers[i]), "counts": int(counts[i])})
    return peaks


def _non_overlapping_peak_windows(
    selected: list[tuple[int, dict[str, Any]]],
    detected: list[dict[str, Any]],
    *,
    requested_half_window_ps: int | None,
    histogram_binwidth_ps: int,
) -> list[tuple[int, dict[str, Any], int, int, str]]:
    """Choose disjoint residual-delay windows for independently reported peaks."""
    centers = [int(round(peak["delay_ps"])) for peak in detected]
    if requested_half_window_ps is None:
        windows: list[tuple[int, dict[str, Any], int, int, str]] = []
        for index, peak in selected:
            separations = [abs(centers[index] - centers[j]) for j in range(len(centers)) if j != index]
            if not separations:
                half_window = max(1, histogram_binwidth_ps)
            else:
                # Leave one histogram-bin gap between neighbouring inclusive windows.
                half_window = (min(separations) - histogram_binwidth_ps) // 2
                if half_window <= 0:
                    raise ValueError(
                        "Detected residual peaks are not sufficiently separated for independent JTI extraction; "
                        "use a coarser residual histogram or select a resolved peak set."
                    )
            center = centers[index]
            windows.append((index, peak, center - half_window, center + half_window, "nearest_peak_midpoint"))
    else:
        if requested_half_window_ps <= 0:
            raise ValueError("--peak-window-ps must be positive")
        windows = [
            (index, peak, centers[index] - requested_half_window_ps, centers[index] + requested_half_window_ps,
             "explicit")
            for index, peak in selected
        ]

    ordered = sorted(windows, key=lambda item: item[2])
    for previous, current in zip(ordered, ordered[1:]):
        if current[2] <= previous[3]:
            raise ValueError("Per-peak residual-delay windows overlap; reduce --peak-window-ps or select fewer peaks.")
    return windows


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
    tau_align = np.int64(int(tau_align_ps))
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


def _save_raw_aligned_artifacts(
    out_dir: Path,
    H: np.ndarray,
    jti_meta: dict[str, Any],
    *,
    bw: int,
    dim: int,
    origin_ps: int,
    guard_bins: int,
    tau_align_ps: float,
    tau_align_source: str,
    delay_min_ps: int,
    delay_max_ps: int,
    frame_period_ps: int,
    input_meta: dict[str, Any],
    peak_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write one independently reproducible JTI result directory."""
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_csv_matrix(out_dir / "H_raw_aligned.csv", H)
    np.savez_compressed(
        str(out_dir / "H_raw_aligned.npz"), jti_counts=H, dimension=dim,
        bin_width_ps=bw, frame_origin_ps=origin_ps, tau_align_ps=tau_align_ps,
        delay_min_ps=delay_min_ps, delay_max_ps=delay_max_ps, guard_bins=guard_bins,
    )
    _plot_png(out_dir / "H_raw_aligned.png", H, title="Raw-aligned FPC JTI")

    edges = jti_meta["tau_hist_bin_edges"]
    hist = jti_meta["tau_hist_counts"]
    centers = (edges[:-1] + edges[1:]) / 2.0
    _write_csv_rows(
        out_dir / "residual_tau_histogram.csv", ["residual_tau_ps", "counts"],
        [{"residual_tau_ps": float(c), "counts": int(n)} for c, n in zip(centers, hist)],
    )
    _plot_residual_tau_histogram(out_dir / "residual_tau_histogram.png", centers, hist,
                                 tau_align_ps=tau_align_ps)

    count_balance_error = (jti_meta["accepted_pairs_input"] - jti_meta["retained_in_jti"]
                           - jti_meta["cross_frame_rejected"] - jti_meta["edge_rejected"]
                           - jti_meta["invalid_bin"])
    meta: dict[str, Any] = {
        "analysis_mode": "raw_aligned_fpc_jti",
        "pairing_mode": "all_ordered_a_b_pairs_inclusive_residual_delay_window",
        "time_unit": "ps", "normalization": "none",
        "tau_align_ps": tau_align_ps, "tau_align_source": tau_align_source,
        "frame_origin_ps": origin_ps, "binwidth_ps": bw, "dimension": dim,
        "frame_period_ps": frame_period_ps, "guard_bins": guard_bins,
        "delay_min_ps": delay_min_ps, "delay_max_ps": delay_max_ps,
        "background_subtracted": False, "peaks_merged": False,
        "accepted_pairs_input": jti_meta["accepted_pairs_input"],
        "retained_in_jti": jti_meta["retained_in_jti"],
        "cross_frame_rejected": jti_meta["cross_frame_rejected"],
        "edge_rejected": jti_meta["edge_rejected"], "invalid_bin": jti_meta["invalid_bin"],
        "count_balance_error": count_balance_error, **_compute_diagonal_diagnostics(H, bw),
        "input": input_meta,
    }
    if peak_info:
        meta["peak"] = peak_info
    (out_dir / "raw_aligned_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8",
    )
    return meta


def _input_summary(tag_meta: dict[str, Any]) -> dict[str, Any]:
    """Keep reproducibility-relevant TimeTagger input facts in result metadata."""
    fields = ("ttbin", "ch_a", "ch_b", "max_events", "n_events_read", "n_ch_a", "n_ch_b", "span_ps", "span_s")
    return {field: tag_meta.get(field) for field in fields}


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
    recommended_delay_min_ps, recommended_delay_max_ps = same_frame_delay_range_ps(dim, bw, guard_bins)

    # --- Delay range resolution ---
    if args.delay_min_ps is not None and args.delay_max_ps is not None:
        delay_min_ps = int(args.delay_min_ps)
        delay_max_ps = int(args.delay_max_ps)
    elif args.delay_window_ps is not None:
        w = int(args.delay_window_ps)
        delay_min_ps, delay_max_ps = -w, w
    else:
        delay_min_ps, delay_max_ps = recommended_delay_min_ps, recommended_delay_max_ps
        print(
            f"NOTE: No --delay-min-ps/--delay-max-ps or --delay-window-ps specified.\n"
            f"      Using default delay range [{delay_min_ps}, {delay_max_ps}] ps.\n"
            f"      This covers all same-frame JTI offsets after edge guard."
        )

    delay_span_ps = delay_max_ps - delay_min_ps
    delay_span_warning: str | None = None
    if delay_min_ps < recommended_delay_min_ps or delay_max_ps > recommended_delay_max_ps:
        delay_span_warning = (
            f"delay range [{delay_min_ps}, {delay_max_ps}] ps is wider than same-frame "
            f"JTI coverage [{recommended_delay_min_ps}, {recommended_delay_max_ps}] ps; "
            "extra candidates must be rejected by the same-frame filter"
        )
        warnings.warn(delay_span_warning, stacklevel=2)
        print(f"WARNING: {delay_span_warning}")

    delay_clips_same_frame_jti = (
        delay_min_ps > recommended_delay_min_ps
        or delay_max_ps < recommended_delay_max_ps
    )
    delay_clip_warning: str | None = None
    if delay_clips_same_frame_jti:
        delay_clip_warning = (
            f"delay range [{delay_min_ps}, {delay_max_ps}] ps is narrower than same-frame "
            f"JTI coverage [{recommended_delay_min_ps}, {recommended_delay_max_ps}] ps; "
            "large diagonal offsets will be clipped"
        )
        warnings.warn(delay_clip_warning, stacklevel=2)
        print(f"WARNING: {delay_clip_warning}")

    # --- Load timetags ---
    ttbin = Path(args.ttbin)
    cache_dir = out_dir / "_tag_cache"
    tags = load_tags(ttbin, cache_dir, int(args.raw_ch_a_id), int(args.raw_ch_b_id), args.max_events)
    if tags.t_a.size == 0 or tags.t_b.size == 0:
        raise RuntimeError(f"No events found in {ttbin}")
    print(f"Loaded {tags.t_a.size:,} A events, {tags.t_b.size:,} B events from {ttbin.name}")
    input_meta = _input_summary(tags.meta)

    # --- Resolve tau_align_ps ---
    peaks_csv = Path(args.peaks_csv)
    tau_align_ps, tau_align_source = infer_tau_align_brightest(peaks_csv, args.tau_align_ps)
    print(f"tau_align_ps = {tau_align_ps:.0f} ps (source: {tau_align_source})")
    print(f"Delay range: [{delay_min_ps}, {delay_max_ps}] ps  (span = {delay_span_ps} ps)")

    peak_mode = getattr(args, "peak_mode", "single")
    if peak_mode != "single":
        # First use the requested global window only to catalogue resolved peaks.
        # Each selected peak is then counted afresh in its own, unmerged window.
        _, discovery = build_raw_aligned_jti(
            tags.t_a, tags.t_b, tau_align_ps, bw=bw, dim=dim, origin_ps=origin_ps,
            guard_bins=guard_bins, delay_min_ps=delay_min_ps, delay_max_ps=delay_max_ps,
            chunk_size=chunk_size,
        )
        edges = discovery["tau_hist_bin_edges"]
        centers = (edges[:-1] + edges[1:]) / 2.0
        detected = detect_residual_peaks(
            centers, discovery["tau_hist_counts"],
            min_relative_height=float(getattr(args, "peak_min_relative_height", 0.05)),
        )
        detected.sort(key=lambda p: p["delay_ps"])
        if peak_mode == "selected":
            requested = getattr(args, "peak_indices", None)
            if not requested:
                raise ValueError("--peak-indices is required with --peak-mode selected")
            try:
                indices = [int(x.strip()) for x in requested.split(",") if x.strip()]
            except ValueError as exc:
                raise ValueError("--peak-indices must be comma-separated integers") from exc
            if not indices or min(indices) < 0 or max(indices) >= len(detected):
                raise ValueError(f"--peak-indices must be within 0..{len(detected) - 1}")
            selected = [(i, detected[i]) for i in indices]
        else:
            selected = list(enumerate(detected))
        if not selected:
            raise RuntimeError("No residual-delay peaks found; lower --peak-min-relative-height or widen delay range")

        requested_peak_window = getattr(args, "peak_window_ps", None)
        peak_windows = _non_overlapping_peak_windows(
            selected, detected,
            requested_half_window_ps=None if requested_peak_window is None else int(requested_peak_window),
            histogram_binwidth_ps=bw,
        )

        catalog: list[dict[str, Any]] = []
        peak_root = out_dir / "peaks"
        for output_index, (detected_index, peak, peak_min, peak_max, window_source) in enumerate(peak_windows):
            center = int(round(peak["delay_ps"]))
            H_peak, peak_meta = build_raw_aligned_jti(
                tags.t_a, tags.t_b, tau_align_ps, bw=bw, dim=dim, origin_ps=origin_ps,
                guard_bins=guard_bins, delay_min_ps=peak_min, delay_max_ps=peak_max,
                chunk_size=chunk_size,
            )
            peak_info = {"catalog_index": detected_index, "center_ps": center,
                         "half_window_ps": (peak_max - peak_min) // 2,
                         "window_min_ps": peak_min, "window_max_ps": peak_max,
                         "window_source": window_source, "histogram_peak_counts": peak["counts"]}
            result_dir = peak_root / f"peak_{output_index:03d}"
            result_meta = _save_raw_aligned_artifacts(
                result_dir, H_peak, peak_meta, bw=bw, dim=dim, origin_ps=origin_ps,
                guard_bins=guard_bins, tau_align_ps=tau_align_ps, tau_align_source=tau_align_source,
                delay_min_ps=peak_min, delay_max_ps=peak_max, frame_period_ps=frame_period_ps,
                input_meta=input_meta,
                peak_info=peak_info,
            )
            catalog.append({**peak_info, "output_directory": str(result_dir.relative_to(out_dir)),
                            "retained_in_jti": result_meta["retained_in_jti"]})
        _write_csv_rows(out_dir / "peak_catalog.csv",
                        ["catalog_index", "center_ps", "half_window_ps", "window_min_ps", "window_max_ps",
                         "window_source", "histogram_peak_counts",
                         "output_directory", "retained_in_jti"], catalog)
        return {"analysis_mode": "raw_aligned_fpc_jti", "peak_mode": peak_mode,
                "tau_align_ps": tau_align_ps, "peak_count": len(catalog), "peaks": catalog}

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
        "pairing_mode": "all_ordered_a_b_pairs_inclusive_residual_delay_window",
        "time_unit": "ps",
        "normalization": "none",
        "tau_align_ps": tau_align_ps,
        "tau_align_source": tau_align_source,
        "frame_origin_ps": origin_ps,
        "binwidth_ps": bw,
        "dimension": dim,
        "frame_period_ps": frame_period_ps,
        "guard_bins": guard_bins,
        "delay_min_ps": delay_min_ps,
        "delay_max_ps": delay_max_ps,
        "delay_span_ps": delay_span_ps,
        "recommended_delay_min_ps": recommended_delay_min_ps,
        "recommended_delay_max_ps": recommended_delay_max_ps,
        "delay_clips_same_frame_jti": delay_clips_same_frame_jti,
        "delay_clip_warning": delay_clip_warning,
        "delay_span_exceeds_frame_period": delay_span_ps >= frame_period_ps,
        "delay_span_warning": delay_span_warning,
        "background_subtracted": False,
        "tooth_roi_filtered": False,
        "line_rearranged": False,
        "peak_id_assigned": False,
        "per_tooth_matrix_generated": False,
        "raw_noise_preserved": True,
        "input": input_meta,
        "accepted_pairs_input": jti_meta["accepted_pairs_input"],
        "retained_in_jti": jti_meta["retained_in_jti"],
        "cross_frame_rejected": jti_meta["cross_frame_rejected"],
        "edge_rejected": jti_meta["edge_rejected"],
        "invalid_bin": jti_meta["invalid_bin"],
        "count_balance_error": count_balance_error,
        **diag_diag,
    }

    meta_path = out_dir / "raw_aligned_meta.json"
    meta_path.write_text(
        json.dumps(raw_aligned_meta, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    print(f"Saved: {meta_path}")

    # --- SVD/K computation (optional) ---
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

        # Write summary.csv
        guard_ps = guard_bins * bw
        summary_row = {
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
    ap.add_argument("--peaks-csv", required=True, help="Path to pminus_peaks.csv.")
    ap.add_argument("--out", required=True, help="Output directory.")

    # Tau alignment
    ap.add_argument("--tau-align-ps", type=float, default=None,
                    help="Explicit tau_align_ps (ps). If omitted, auto-determined from peaks CSV.")

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
                    help="Shorthand: sets delay_min=-W, delay_max=+W.")

    # Multi-peak residual-delay extraction (microcavity / frequency-bin data)
    ap.add_argument("--peak-mode", choices=["single", "auto", "selected"], default="single",
                    help=("single keeps the original global window; auto writes one JTI per detected peak; "
                          "selected uses --peak-indices from that detected catalogue."))
    ap.add_argument("--peak-indices", default=None,
                    help="Comma-separated residual-peak catalogue indices for --peak-mode selected.")
    ap.add_argument("--peak-window-ps", type=int, default=None,
                    help="Half-width of each per-peak residual-delay window (default: delay-window or 2 bins).")
    ap.add_argument("--peak-min-relative-height", type=float, default=0.05,
                    help="Auto-detection local-maximum threshold relative to the brightest peak.")

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
    print(f"  tau_align_ps = {meta['tau_align_ps']:.0f}")
    if meta.get("peak_mode", "single") != "single":
        print(f"  peak mode    = {meta['peak_mode']} ({meta['peak_count']} peak directories)")
    else:
        print(f"  delay range  = [{meta['delay_min_ps']}, {meta['delay_max_ps']}] ps")
        print(f"  retained     = {meta['retained_in_jti']:,} / {meta['accepted_pairs_input']:,}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
