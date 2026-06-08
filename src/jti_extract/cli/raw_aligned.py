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

    # --- Delay range resolution ---
    if args.delay_min_ps is not None and args.delay_max_ps is not None:
        delay_min_ps = int(args.delay_min_ps)
        delay_max_ps = int(args.delay_max_ps)
    elif args.delay_window_ps is not None:
        w = int(args.delay_window_ps)
        delay_min_ps, delay_max_ps = -w, w
    else:
        frame_period_ps = dim * bw
        guard_ps = guard_bins * bw
        half_margin = frame_period_ps // 2 - guard_ps
        delay_min_ps, delay_max_ps = -half_margin, half_margin
        print(
            f"NOTE: No --delay-min-ps/--delay-max-ps or --delay-window-ps specified.\n"
            f"      Using default delay range [{delay_min_ps}, {delay_max_ps}] ps.\n"
            f"      Consider inspecting residual_tau_histogram.png and setting\n"
            f"      --delay-min-ps / --delay-max-ps explicitly for optimal range."
        )

    frame_period_ps = dim * bw
    delay_span_ps = delay_max_ps - delay_min_ps
    delay_span_warning: str | None = None
    if delay_span_ps >= frame_period_ps:
        delay_span_warning = (
            f"delay_span_ps ({delay_span_ps}) >= frame_period_ps ({frame_period_ps}), "
            f"expect heavy cross-frame rejection"
        )
        warnings.warn(delay_span_warning, stacklevel=2)
        print(f"WARNING: {delay_span_warning}")

    # --- Load timetags ---
    ttbin = Path(args.ttbin)
    cache_dir = out_dir / "_tag_cache"
    tags = load_tags(ttbin, cache_dir, int(args.raw_ch_a_id), int(args.raw_ch_b_id), args.max_events)
    if tags.t_a.size == 0 or tags.t_b.size == 0:
        raise RuntimeError(f"No events found in {ttbin}")
    print(f"Loaded {tags.t_a.size:,} A events, {tags.t_b.size:,} B events from {ttbin.name}")

    # --- Resolve tau_align_ps ---
    peaks_csv = Path(args.peaks_csv)
    tau_align_ps, tau_align_source = infer_tau_align_brightest(peaks_csv, args.tau_align_ps)
    print(f"tau_align_ps = {tau_align_ps:.0f} ps (source: {tau_align_source})")
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
