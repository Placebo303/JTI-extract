#!/usr/bin/env python3
"""Delay-peak to JTI diagonal-offset alignment diagnostic."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import warnings
from pathlib import Path
from typing import Any

import numpy as np

try:
    import pandas as pd
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"pandas is required for this standalone tool: {exc}") from exc

try:
    import matplotlib.pyplot as plt
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"matplotlib is required for plotting: {exc}") from exc

try:  # scipy is optional.
    from scipy.signal import find_peaks as scipy_find_peaks
    from scipy.signal import peak_widths as scipy_peak_widths
except Exception:  # pragma: no cover
    scipy_find_peaks = None
    scipy_peak_widths = None


def json_default(obj: Any) -> Any:
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


def parse_candidate_bws(text: str) -> np.ndarray:
    s = str(text).strip()
    if ":" in s:
        parts = [float(x) for x in s.split(":")]
        if len(parts) != 3:
            raise ValueError("--candidate-bw-ps range must be start:stop:step")
        start, stop, step = parts
        if step <= 0:
            raise ValueError("candidate bw step must be positive")
        values = np.arange(start, stop + step * 0.5, step, dtype=float)
    else:
        values = np.asarray([float(x.strip()) for x in s.split(",") if x.strip()], dtype=float)
    values = values[np.isfinite(values) & (values > 0)]
    if values.size == 0:
        raise ValueError("no positive candidate bin widths")
    return np.unique(np.round(values, 12))


def detect_column(columns: list[str], requested: str, kind: str) -> str:
    if requested != "auto":
        if requested not in columns:
            raise ValueError(f"{kind} column not found: {requested}")
        return requested
    lowered = {c.lower().strip(): c for c in columns}
    if kind == "delay":
        candidates = ["delay_ps", "tau_ps", "tau", "delay", "time_ps", "center_ps"]
        contains = ["delay", "tau"]
    else:
        candidates = ["counts", "count", "coincidence_counts", "bg_sub_counts", "height"]
        contains = ["count", "coinc"]
    for name in candidates:
        if name in lowered:
            return lowered[name]
    for c in columns:
        lc = c.lower()
        if any(token in lc for token in contains):
            return c
    numeric_cols = columns
    if len(numeric_cols) >= 2:
        return numeric_cols[0] if kind == "delay" else numeric_cols[1]
    raise ValueError(f"could not auto-detect {kind} column")


def load_delay_histogram(path: Path, delay_col: str, counts_col: str) -> tuple[np.ndarray, np.ndarray, str, str]:
    df = pd.read_csv(path)
    numeric = df.apply(pd.to_numeric, errors="coerce")
    numeric = numeric.dropna(axis=1, how="all")
    cols = list(numeric.columns)
    dcol = detect_column(cols, delay_col, "delay")
    ccol = detect_column(cols, counts_col, "counts")
    out = numeric[[dcol, ccol]].dropna().sort_values(dcol)
    tau = out[dcol].to_numpy(dtype=float)
    counts = out[ccol].to_numpy(dtype=float)
    if tau.size < 3:
        raise ValueError("delay histogram must contain at least 3 numeric rows")
    return tau, counts, dcol, ccol


def moving_average(y: np.ndarray, width: int) -> np.ndarray:
    width = max(1, int(width))
    if width <= 1:
        return y.astype(float, copy=True)
    kernel = np.ones(width, dtype=float) / float(width)
    return np.convolve(y.astype(float), kernel, mode="same")


def estimate_baseline(counts: np.ndarray, percentile: float, smooth_bins: int) -> np.ndarray:
    y = np.asarray(counts, dtype=float)
    base = float(np.percentile(y[np.isfinite(y)], float(percentile))) if y.size else 0.0
    baseline = np.full(y.shape, base, dtype=float)
    if smooth_bins > 1:
        # Keep intentionally conservative: a smoothed low constant baseline avoids
        # fitting away broad real peaks in sparse histograms.
        baseline = moving_average(baseline, smooth_bins)
    return baseline


def fallback_find_peaks(y: np.ndarray, min_height: float, min_distance: int) -> np.ndarray:
    candidates: list[int] = []
    for i in range(1, len(y) - 1):
        if y[i] >= min_height and y[i] >= y[i - 1] and y[i] >= y[i + 1]:
            candidates.append(i)
    candidates.sort(key=lambda i: y[i], reverse=True)
    selected: list[int] = []
    for idx in candidates:
        if all(abs(idx - j) >= min_distance for j in selected):
            selected.append(idx)
    return np.asarray(sorted(selected), dtype=int)


def local_prominence(y: np.ndarray, idx: int, radius: int) -> float:
    lo = max(0, idx - radius)
    hi = min(len(y), idx + radius + 1)
    left_min = float(np.min(y[lo : idx + 1]))
    right_min = float(np.min(y[idx:hi]))
    return float(y[idx] - max(left_min, right_min))


def interpolate_crossing(x0: float, y0: float, x1: float, y1: float, level: float) -> float:
    if y1 == y0:
        return float((x0 + x1) * 0.5)
    return float(x0 + (level - y0) * (x1 - x0) / (y1 - y0))


def fractional_index_to_tau(tau: np.ndarray, idx: float) -> float:
    if not np.isfinite(idx):
        return math.nan
    if idx <= 0:
        return float(tau[0])
    if idx >= len(tau) - 1:
        return float(tau[-1])
    lo = int(math.floor(idx))
    hi = lo + 1
    frac = float(idx - lo)
    return float(tau[lo] + frac * (tau[hi] - tau[lo]))


def explicit_fwhm(tau: np.ndarray, y: np.ndarray, peak_idx: int, left_bound: int = 0, right_bound: int | None = None) -> tuple[float, float, float]:
    if right_bound is None:
        right_bound = len(y) - 1
    peak_h = float(y[peak_idx])
    if peak_h <= 0:
        return math.nan, math.nan, math.nan
    half = 0.5 * peak_h
    left = math.nan
    for i in range(peak_idx, max(0, int(left_bound)), -1):
        if y[i - 1] <= half <= y[i] or y[i - 1] >= half >= y[i]:
            left = interpolate_crossing(float(tau[i - 1]), float(y[i - 1]), float(tau[i]), float(y[i]), half)
            break
    right = math.nan
    for i in range(peak_idx, min(len(y) - 1, int(right_bound))):
        if y[i] >= half >= y[i + 1] or y[i] <= half <= y[i + 1]:
            right = interpolate_crossing(float(tau[i]), float(y[i]), float(tau[i + 1]), float(y[i + 1]), half)
            break
    if not (np.isfinite(left) and np.isfinite(right) and right >= left):
        return math.nan, left, right
    return float(right - left), float(left), float(right)


def detect_peaks(
    tau: np.ndarray,
    counts: np.ndarray,
    *,
    smooth_bins: int,
    min_prominence: float | None,
    min_height_fraction: float,
    min_distance_ps: float,
    baseline_percentile: float,
) -> tuple[pd.DataFrame, np.ndarray]:
    baseline = estimate_baseline(counts, baseline_percentile, smooth_bins)
    bg = np.maximum(np.asarray(counts, dtype=float) - baseline, 0.0)
    smoothed = moving_average(bg, smooth_bins)
    max_y = float(np.max(smoothed)) if smoothed.size else 0.0
    min_height = max_y * float(min_height_fraction)
    dt = float(np.median(np.diff(tau))) if tau.size > 1 else 1.0
    min_distance_bins = max(1, int(round(float(min_distance_ps) / max(abs(dt), 1e-12))))
    prominence_arg = min_prominence if min_prominence is not None else max_y * 0.03
    if scipy_find_peaks is not None:
        peak_idx, props = scipy_find_peaks(
            smoothed,
            height=min_height,
            distance=min_distance_bins,
            prominence=prominence_arg,
        )
        scipy_prom = props.get("prominences", np.full(peak_idx.shape, np.nan))
    else:
        peak_idx = fallback_find_peaks(smoothed, min_height=min_height, min_distance=min_distance_bins)
        scipy_prom = np.asarray([local_prominence(smoothed, int(i), min_distance_bins) for i in peak_idx], dtype=float)
    rows: list[dict[str, Any]] = []
    max_bg_height = float(np.max(bg[peak_idx])) if peak_idx.size else 0.0
    peak_idx = np.asarray(sorted(set(int(i) for i in peak_idx.tolist())), dtype=int)
    bounds: dict[int, tuple[int, int]] = {}
    for pos, idx in enumerate(peak_idx.tolist()):
        left_bound = 0 if pos == 0 else int((peak_idx[pos - 1] + idx) // 2)
        right_bound = len(bg) - 1 if pos + 1 == len(peak_idx) else int((idx + peak_idx[pos + 1]) // 2)
        bounds[int(idx)] = (left_bound, right_bound)
    for n, idx in enumerate(peak_idx.tolist()):
        left_bound, right_bound = bounds[int(idx)]
        fwhm_ps, left_ps, right_ps = explicit_fwhm(tau, bg, int(idx), left_bound, right_bound)
        if (not np.isfinite(fwhm_ps) or fwhm_ps <= 0) and scipy_peak_widths is not None:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    widths, _, left_ips, right_ips = scipy_peak_widths(bg, np.asarray([int(idx)]), rel_height=0.5)
                left_ps = fractional_index_to_tau(tau, float(left_ips[0]))
                right_ps = fractional_index_to_tau(tau, float(right_ips[0]))
                fwhm_ps = float(right_ps - left_ps) if right_ps >= left_ps else math.nan
            except Exception:
                pass
        if not np.isfinite(fwhm_ps) or fwhm_ps <= 0:
            peak_tau = float(tau[idx])
            if int(left_bound) == 0 and int(right_bound) > int(idx):
                half_width = abs(float(tau[right_bound]) - peak_tau)
                left_ps = peak_tau - half_width
                right_ps = peak_tau + half_width
            elif int(right_bound) >= len(bg) - 1 and int(left_bound) < int(idx):
                half_width = abs(peak_tau - float(tau[left_bound]))
                left_ps = peak_tau - half_width
                right_ps = peak_tau + half_width
            else:
                left_ps = float(tau[left_bound])
                right_ps = float(tau[right_bound])
            fwhm_ps = float(right_ps - left_ps) if right_ps >= left_ps else math.nan
        prom = float(scipy_prom[n]) if n < len(scipy_prom) and np.isfinite(scipy_prom[n]) else local_prominence(bg, int(idx), min_distance_bins)
        rows.append(
            {
                "peak_index": int(idx),
                "tau_ps": float(tau[idx]),
                "counts": float(counts[idx]),
                "bg_sub_counts": float(bg[idx]),
                "norm_height": float(bg[idx] / max_bg_height) if max_bg_height > 0 else math.nan,
                "prominence": prom,
                "fwhm_ps": fwhm_ps,
                "left_ips_ps": left_ps,
                "right_ips_ps": right_ps,
            }
        )
    df = pd.DataFrame(rows).sort_values(["tau_ps"]).reset_index(drop=True)
    return df, bg


def choose_tau0(peaks: pd.DataFrame, tau0_arg: str) -> float:
    if peaks.empty:
        raise ValueError("no peaks detected")
    if str(tau0_arg).lower() != "auto":
        return float(tau0_arg)
    idx = peaks["bg_sub_counts"].astype(float).idxmax()
    return float(peaks.loc[idx, "tau_ps"])


def filter_peak_side(peaks: pd.DataFrame, tau0_ps: float, side: str) -> pd.DataFrame:
    out = peaks.copy()
    out["tau_rel_ps"] = out["tau_ps"].astype(float) - float(tau0_ps)
    eps = 1e-9
    if side == "positive":
        out = out[out["tau_rel_ps"] >= -eps]
    elif side == "negative":
        out = out[out["tau_rel_ps"] <= eps]
    elif side != "all":
        raise ValueError("--peak-side must be all, positive, or negative")
    out = out.sort_values("tau_rel_ps").reset_index(drop=True)
    out.insert(0, "peak_id", [f"p{i}" for i in range(len(out))])
    return out


def median_spacing(peaks: pd.DataFrame) -> float:
    vals = np.sort(peaks["tau_ps"].to_numpy(dtype=float))
    if vals.size < 2:
        return math.nan
    diffs = np.diff(vals)
    diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
    return float(np.median(diffs)) if diffs.size else math.nan


def score_bw_candidates(peaks: pd.DataFrame, candidate_bws: np.ndarray, median_fwhm: float, median_spacing_ps: float) -> pd.DataFrame:
    tau_rel = peaks["tau_rel_ps"].to_numpy(dtype=float)
    rows = []
    spacing_enabled = np.isfinite(median_spacing_ps) and median_spacing_ps > 0 and len(tau_rel) >= 2
    for bw in candidate_bws.astype(float):
        offsets_float = tau_rel / bw
        rounded = np.rint(offsets_float)
        err_bins = np.abs(offsets_float - rounded)
        err_ps = np.abs(tau_rel - rounded * bw)
        fwhm_bins = float(median_fwhm / bw) if np.isfinite(median_fwhm) else math.nan
        spacing_bins = float(median_spacing_ps / bw) if spacing_enabled else math.nan
        if not np.isfinite(fwhm_bins):
            resolution_penalty = 10.0
        elif fwhm_bins < 2.0:
            resolution_penalty = (2.0 - fwhm_bins) ** 2
        elif fwhm_bins > 6.0:
            resolution_penalty = ((fwhm_bins - 6.0) / 2.0) ** 2
        else:
            resolution_penalty = 0.0
        unique_offsets = len(set(int(x) for x in rounded.tolist()))
        duplicate_count = len(rounded) - unique_offsets
        duplicate_penalty = float(duplicate_count) * 25.0
        if spacing_enabled:
            spacing_nearest = round(spacing_bins)
            spacing_penalty = abs(spacing_bins - spacing_nearest) if spacing_nearest > 0 else 5.0
            if spacing_bins < 1.0:
                spacing_penalty += (1.0 - spacing_bins) * 5.0
        else:
            spacing_penalty = 0.0
        alignment_penalty = float(np.nanmean(err_bins)) if err_bins.size else 0.0
        total = resolution_penalty + duplicate_penalty + spacing_penalty + alignment_penalty
        rows.append(
            {
                "bw_ps": float(bw),
                "fwhm_bins": fwhm_bins,
                "spacing_bins": spacing_bins,
                "integer_alignment_error_bins": float(np.nanmean(err_bins)) if err_bins.size else math.nan,
                "integer_alignment_error_ps": float(np.nanmean(err_ps)) if err_ps.size else math.nan,
                "num_unique_offsets": int(unique_offsets),
                "total_score": float(total),
            }
        )
    df = pd.DataFrame(rows).sort_values(["total_score", "bw_ps"]).reset_index(drop=True)
    df["recommended_rank"] = np.arange(1, len(df) + 1)
    return df.sort_values("bw_ps").reset_index(drop=True)


def selected_offsets(peaks: pd.DataFrame, chosen_bw: float) -> pd.DataFrame:
    out = peaks.copy()
    offsets = np.rint(out["tau_rel_ps"].astype(float) / float(chosen_bw)).astype(int)
    out["chosen_bw_ps"] = float(chosen_bw)
    out["diagonal_offset_bin"] = offsets
    out["alignment_error_ps"] = out["tau_rel_ps"].astype(float) - offsets.astype(float) * float(chosen_bw)
    out["fwhm_bins"] = out["fwhm_ps"].astype(float) / float(chosen_bw)
    out["half_width_bins"] = 0.5 * out["fwhm_bins"].astype(float)
    out["rounded_left_offset_bin"] = np.rint((out["tau_rel_ps"].astype(float) - 0.5 * out["fwhm_ps"].astype(float)) / float(chosen_bw)).astype("Int64")
    out["rounded_right_offset_bin"] = np.rint((out["tau_rel_ps"].astype(float) + 0.5 * out["fwhm_ps"].astype(float)) / float(chosen_bw)).astype("Int64")
    return out[
        [
            "peak_id",
            "tau_rel_ps",
            "chosen_bw_ps",
            "diagonal_offset_bin",
            "alignment_error_ps",
            "norm_height",
            "fwhm_ps",
            "fwhm_bins",
            "half_width_bins",
            "rounded_left_offset_bin",
            "rounded_right_offset_bin",
        ]
    ]


def load_jti_csv(path: Path, fmt: str) -> np.ndarray:
    raw = pd.read_csv(path)
    cols = [c.lower().strip() for c in raw.columns]
    long_like = {"signal_bin", "idler_bin", "counts"}.issubset(set(cols))
    if fmt == "long" or (fmt == "auto" and long_like):
        colmap = {c.lower().strip(): c for c in raw.columns}
        sig = raw[colmap["signal_bin"]].to_numpy(dtype=int)
        idl = raw[colmap["idler_bin"]].to_numpy(dtype=int)
        cnt = raw[colmap["counts"]].to_numpy(dtype=float)
        n = int(max(sig.max(initial=0), idl.max(initial=0)) + 1)
        mat = np.zeros((n, n), dtype=float)
        np.add.at(mat, (sig, idl), cnt)
        return mat
    if fmt == "long":
        raise ValueError("long JTI format requires signal_bin,idler_bin,counts columns")
    df = pd.read_csv(path, index_col=0)
    mat = df.apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    if mat.ndim != 2 or mat.size == 0:
        raise ValueError("JTI matrix CSV is empty or invalid")
    mat = np.nan_to_num(mat, nan=0.0)
    return mat


def infer_jti_bw(path: Path) -> float | None:
    patterns = [r"bw(?P<bw>\d+(?:\.\d+)?)ps", r"bin(?:width)?[_-]?(?P<bw>\d+(?:\.\d+)?)ps"]
    text = str(path)
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return float(m.group("bw"))
    meta_candidates = [
        path.with_suffix(".meta.json"),
        path.with_name(path.name.replace(".counts.csv", ".meta.json")),
        path.parent / "publication_jti.meta.json",
        path.parent / "jti_summary.json",
    ]
    for meta in meta_candidates:
        if meta.exists():
            try:
                data = json.loads(meta.read_text(encoding="utf-8"))
                for key in ["bin_width_ps", "binwidth_ps", "publication_bin_width_ps"]:
                    if key in data:
                        return float(data[key])
            except Exception:
                continue
    return None


def infer_k0(mat: np.ndarray) -> int:
    n = int(min(mat.shape))
    best_k = 0
    best_sum = -1.0
    for k in range(-(n - 1), n):
        s = float(np.trace(mat, offset=k))
        if s > best_sum:
            best_sum = s
            best_k = k
    return int(best_k)


def plot_delay_peaks(path_base: Path, tau: np.ndarray, bg: np.ndarray, peaks: pd.DataFrame, tau0_ps: float) -> None:
    x_ns = (tau - float(tau0_ps)) / 1000.0
    denom = float(np.max(bg)) if bg.size and float(np.max(bg)) > 0 else 1.0
    fig, ax = plt.subplots(figsize=(8.0, 4.2), dpi=160)
    ax.plot(x_ns, bg / denom, color="black", linewidth=0.8)
    ax.axvline(0.0, color="tab:red", linestyle="--", linewidth=0.8)
    for _, row in peaks.iterrows():
        x = float(row["tau_rel_ps"]) / 1000.0
        y = float(row["bg_sub_counts"]) / denom
        ax.plot([x], [y], "o", color="tab:red", markersize=3)
        ax.text(x, min(1.02, y + 0.04), str(row["peak_id"]), color="tab:red", fontsize=8, ha="center")
    ax.set_xlabel("tau_rel (ns)")
    ax.set_ylabel("normalized bg-sub counts")
    ax.set_title("Delay peaks")
    ax.grid(True, linewidth=0.3, alpha=0.35)
    fig.tight_layout()
    for ext in ["png", "pdf"]:
        fig.savefig(str(path_base.with_suffix(f".{ext}")))
    plt.close(fig)


def plot_bw_scan(path_base: Path, bw_scan: pd.DataFrame, recommended_bw: float) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 4.0), dpi=160)
    ax.plot(bw_scan["bw_ps"], bw_scan["total_score"], marker="o", markersize=2.5, linewidth=0.8)
    ax.axvline(float(recommended_bw), color="tab:red", linestyle="--", linewidth=0.9, label=f"recommended {recommended_bw:g} ps")
    ax.set_xlabel("bw_ps")
    ax.set_ylabel("total_score")
    ax.set_title("JTI bin-width scan")
    ax.legend()
    ax.grid(True, linewidth=0.3, alpha=0.35)
    fig.tight_layout()
    for ext in ["png", "pdf"]:
        fig.savefig(str(path_base.with_suffix(f".{ext}")))
    plt.close(fig)


def plot_jti_overlay(path_base: Path, mat: np.ndarray, offsets: pd.DataFrame, peaks: pd.DataFrame, tau: np.ndarray, bg: np.ndarray, tau0_ps: float, k0: int, vmax: float | None) -> None:
    from mpl_toolkits.axes_grid1.inset_locator import inset_axes

    positive = mat[mat > 0]
    vv = float(vmax) if vmax is not None else (float(np.percentile(positive, 99.5)) if positive.size else 1.0)
    vv = max(1.0, vv)
    n = int(min(mat.shape))
    fig, ax = plt.subplots(figsize=(7.0, 6.0), dpi=170)
    img = ax.imshow(mat.T, origin="lower", aspect="equal", interpolation="nearest", vmax=vv)
    xs = np.arange(n)
    for _, row in offsets.iterrows():
        off = int(k0) + int(row["diagonal_offset_bin"])
        ys = xs + off
        keep = (ys >= 0) & (ys < n)
        if np.any(keep):
            ax.plot(xs[keep], ys[keep], linewidth=0.9, alpha=0.8)
            mid = np.flatnonzero(keep)[len(np.flatnonzero(keep)) // 2]
            ax.text(xs[mid], ys[mid], str(row["peak_id"]), fontsize=8, color="red", fontweight="bold")
    ax.set_xlabel("Signal bin")
    ax.set_ylabel("Idler bin")
    ax.set_title("JTI with delay-peak diagonal predictions")
    cbar = fig.colorbar(img, ax=ax, fraction=0.047, pad=0.035)
    cbar.set_label("Counts")
    inset = inset_axes(ax, width="34%", height="27%", loc="upper left", borderpad=1.0)
    denom = float(np.max(bg)) if bg.size and float(np.max(bg)) > 0 else 1.0
    inset.plot((tau - tau0_ps) / 1000.0, bg / denom, color="black", linewidth=0.7)
    for _, row in peaks.iterrows():
        inset.plot(float(row["tau_rel_ps"]) / 1000.0, float(row["bg_sub_counts"]) / denom, "o", color="red", markersize=2.5)
        inset.text(float(row["tau_rel_ps"]) / 1000.0, min(1.02, float(row["bg_sub_counts"]) / denom + 0.04), str(row["peak_id"]), color="red", fontsize=7)
    inset.set_xlabel("tau_rel (ns)", fontsize=7)
    inset.set_ylabel("norm.", fontsize=7)
    inset.tick_params(labelsize=7, length=2)
    fig.tight_layout()
    for ext in ["png", "pdf"]:
        fig.savefig(str(path_base.with_suffix(f".{ext}")))
    plt.close(fig)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Map delay-histogram peaks to JTI diagonal offsets and score JTI bin widths.")
    ap.add_argument("--delay-csv", required=True)
    ap.add_argument("--jti-csv", default=None)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--delay-col", default="auto")
    ap.add_argument("--counts-col", default="auto")
    ap.add_argument("--tau0-ps", default="auto")
    ap.add_argument("--candidate-bw-ps", default="40:400:10")
    ap.add_argument("--chosen-bw-ps", default="auto")
    ap.add_argument("--peak-side", choices=["all", "positive", "negative"], default="all")
    ap.add_argument("--jti-format", choices=["matrix", "long", "auto"], default="auto")
    ap.add_argument("--jti-k0", default=None)
    ap.add_argument("--vmax", type=float, default=None)
    ap.add_argument("--smooth-bins", type=int, default=3)
    ap.add_argument("--baseline-percentile", type=float, default=10.0)
    ap.add_argument("--min-height-fraction", type=float, default=0.04)
    ap.add_argument("--min-prominence", type=float, default=None)
    ap.add_argument("--min-peak-distance-ps", type=float, default=50.0)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    tau, counts, dcol, ccol = load_delay_histogram(Path(args.delay_csv), args.delay_col, args.counts_col)
    all_peaks, bg = detect_peaks(
        tau,
        counts,
        smooth_bins=int(args.smooth_bins),
        min_prominence=args.min_prominence,
        min_height_fraction=float(args.min_height_fraction),
        min_distance_ps=float(args.min_peak_distance_ps),
        baseline_percentile=float(args.baseline_percentile),
    )
    tau0 = choose_tau0(all_peaks, args.tau0_ps)
    peaks = filter_peak_side(all_peaks, tau0, args.peak_side)
    if peaks.empty:
        raise SystemExit("no peaks remain after --peak-side filtering")
    median_fwhm = float(np.nanmedian(peaks["fwhm_ps"].to_numpy(dtype=float)))
    med_spacing = median_spacing(peaks)
    candidate_bws = parse_candidate_bws(args.candidate_bw_ps)
    bw_scan = score_bw_candidates(peaks, candidate_bws, median_fwhm, med_spacing)
    recommended_row = bw_scan.sort_values(["total_score", "bw_ps"]).iloc[0]
    recommended_bw = float(recommended_row["bw_ps"])
    chosen_bw = recommended_bw if str(args.chosen_bw_ps).lower() == "auto" else float(args.chosen_bw_ps)
    offsets = selected_offsets(peaks, chosen_bw)

    delay_out = peaks[
        ["peak_id", "tau_ps", "tau_rel_ps", "counts", "bg_sub_counts", "norm_height", "prominence", "fwhm_ps", "left_ips_ps", "right_ips_ps"]
    ].copy()
    delay_out.to_csv(outdir / "delay_peaks.csv", index=False)
    bw_scan.to_csv(outdir / "bw_scan.csv", index=False)
    offsets.to_csv(outdir / "selected_peak_offsets.csv", index=False)
    plot_delay_peaks(outdir / "delay_peaks_plot", tau, bg, peaks, tau0)
    plot_bw_scan(outdir / "bw_scan_plot", bw_scan, recommended_bw)

    jti_bw = None
    if args.jti_csv:
        jti_path = Path(args.jti_csv)
        mat = load_jti_csv(jti_path, args.jti_format)
        k0 = int(args.jti_k0) if args.jti_k0 is not None else infer_k0(mat)
        plot_jti_overlay(outdir / "jti_with_peak_lines", mat, offsets, peaks, tau, bg, tau0, k0, args.vmax)
        jti_bw = infer_jti_bw(jti_path)
        if jti_bw is None:
            print("JTI bin width unknown; overlay assumes chosen_bw_ps is consistent with the JTI construction.")
        elif abs(float(jti_bw) - float(chosen_bw)) > 1e-9:
            print("The provided JTI was generated with a different bin width if known. To see sharper diagonal lines, rerun JTI extraction with the recommended bw and then rerun this alignment tool.")

    rec_for_chosen = score_bw_candidates(peaks, np.asarray([chosen_bw], dtype=float), median_fwhm, med_spacing).iloc[0]
    summary = {
        "tau0_ps": float(tau0),
        "selected_peak_count": int(len(peaks)),
        "median_FWHM_ps": median_fwhm,
        "median_spacing_ps": med_spacing,
        "recommended_bw_ps": recommended_bw,
        "chosen_bw_ps": chosen_bw,
        "recommended_score": float(recommended_row["total_score"]),
        "fwhm_bins": float(rec_for_chosen["fwhm_bins"]),
        "spacing_bins": float(rec_for_chosen["spacing_bins"]) if np.isfinite(rec_for_chosen["spacing_bins"]) else math.nan,
        "mean_alignment_error_ps": float(rec_for_chosen["integer_alignment_error_ps"]),
        "mean_alignment_error_bins": float(rec_for_chosen["integer_alignment_error_bins"]),
        "output_dir": str(outdir),
        "delay_column": dcol,
        "counts_column": ccol,
        "jti_bin_width_ps": jti_bw,
    }
    (outdir / "alignment_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=json_default), encoding="utf-8")
    print(
        "\n".join(
            [
                f"tau0_ps: {summary['tau0_ps']:.6g}",
                f"median_FWHM_ps: {summary['median_FWHM_ps']:.6g}",
                f"median_spacing_ps: {summary['median_spacing_ps']:.6g}",
                f"recommended_bw_ps: {summary['recommended_bw_ps']:.6g}",
                f"fwhm_bins at chosen bw: {summary['fwhm_bins']:.6g}",
                f"spacing_bins at chosen bw: {summary['spacing_bins']:.6g}",
                f"integer_alignment_error_ps: {summary['mean_alignment_error_ps']:.6g}",
                f"output_dir: {summary['output_dir']}",
            ]
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
