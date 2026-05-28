#!/usr/bin/env python3
"""Direct P_plus extraction and auto-dim pilot for Type0ppln JTI data."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from jti_extract.cli.extract import (
    _iter_frame_origins,
    _select_best_frame_origin,
    _time_tags_to_bins,
)
from jti_extract.cli.tdc_layer_scan import Tags, greedy_unique_pairs, load_tags, nearest_pairs


DEFAULT_DATA_ROOT = r"D:\Data\Raw Data\Type0ppln JTI"
DEFAULT_STATUS_OK = "OK"

SUMMARY_FIELDS = [
    "logical_id",
    "file_name",
    "file_path",
    "dim",
    "bin_width_ps",
    "frame_length_ps",
    "frame_origin_ps",
    "tau0_ps",
    "channels",
    "pairing_rule",
    "coincidence_window_ps",
    "diag_band_bins",
    "total_pairs",
    "pairs_in_diag_band",
    "diag_band_fraction",
    "P_plus_total",
    "P_plus_peak",
    "P_plus_peak_index",
    "P_plus_FWHM_ps",
    "P_plus_central_50_width_ps",
    "P_plus_central_90_width_ps",
    "P_plus_central_95_width_ps",
    "P_plus_sigma_ps",
    "P_plus_participation_time_ps",
    "width_ratio_95",
    "edge_fraction",
    "relative_change_W95",
    "covered",
    "P_minus_peak_delta_bins",
    "P_minus_FWHM_ps",
    "P_minus_sigma_ps",
    "P_minus_central_90_width_ps",
    "P_minus_central_95_width_ps",
    "profile_storage",
    "n_nonzero_P_plus_bins",
    "estimated_profile_bytes",
    "frame_origin_method",
    "status",
    "error",
    "suggestion",
]
FILE_SUMMARY_FIELDS = [
    "logical_id",
    "kept_file",
    "duplicate_count",
    "n_pairs",
    "tau0_ps",
    "final_dim",
    "final_frame_length_ps",
    "final_W95_ps",
    "final_width_ratio_95",
    "final_edge_fraction",
    "final_covered",
    "final_status",
    "stop_reason",
    "output_profile_path",
    "output_plot_path",
]
DEDUPE_FIELDS = [
    "logical_id",
    "kept_path",
    "duplicate_paths",
    "dedupe_method",
    "total_events",
    "selected_channel_counts",
    "status",
    "error",
    "suggestion",
]
AUTO_DECISION_FIELDS = [
    "logical_id",
    "dim",
    "frame_length_ps",
    "W95_ps",
    "width_ratio_95",
    "edge_fraction",
    "relative_change_W95",
    "covered",
    "stop_reason",
]
CHECK_FIELDS = [
    "logical_id",
    "dim",
    "bin_width_ps",
    "frame_origin_ps",
    "max_abs_diff",
    "total_abs_diff",
    "relative_l1_diff",
]


@dataclass(frozen=True)
class LogicalDataset:
    """One logical dataset after dedupe."""

    logical_id: str
    kept_path: Path
    duplicate_paths: tuple[Path, ...]
    dedupe_method: str
    total_events: int | None
    selected_channel_counts: dict[str, int]
    filewriter_filename: str | None


@dataclass(frozen=True)
class Config:
    """Resolved runtime settings."""

    data_root: Path
    channels: tuple[int, int]
    pairing_rule: str
    coincidence_window_ps: int
    bin_width_ps: int
    dims: tuple[int, ...]
    auto_dim: bool
    auto_stop: bool
    diag_band_bins: int
    edge_bins_fraction: float
    edge_fraction_threshold: float
    stop_width_ratio: float
    stop_width_change: float
    dedupe_ttbin: bool
    output_dir: Path
    dims_explicit: bool
    jobs: int
    dense_profile_max_bins: int
    continue_from_existing: Path | None
    min_next_dim: int | None
    high_dim_max_dim: int | None
    profile_storage: str


def normalize_path(raw: str) -> Path:
    """Accept a native path or convert a Windows path under WSL/Linux."""
    s = str(raw).strip().strip('"')
    is_windows_abs = len(s) >= 3 and s[1] == ":" and s[2] in ("\\", "/")
    if not is_windows_abs:
        return Path(s)
    if os.name == "nt":
        return Path(s)
    try:
        out = subprocess.check_output(["wslpath", "-a", s], text=True).strip()
        if out:
            return Path(out)
    except Exception:
        drive = s[0].lower()
        rest = s[2:].replace("\\", "/").lstrip("/")
        return Path(f"/mnt/{drive}/{rest}")
    return Path(s)


def safe_stem(text: str) -> str:
    """Return a filesystem-safe identifier."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text)).strip("_") or "dataset"


def unique_output_dir(base: Path) -> Path:
    """Allocate an output directory path that does not exist yet."""
    if not base.exists():
        return base
    for idx in range(1, 1000):
        candidate = base.with_name(f"{base.name}_{idx:03d}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not allocate a unique output directory under {base.parent}")


def planned_output_dir(data_root: Path, raw_output_dir: str | None) -> Path:
    """Resolve the output directory without creating it."""
    if raw_output_dir:
        return unique_output_dir(normalize_path(raw_output_dir).resolve())
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return unique_output_dir((data_root / f"pplus_auto_dim_{stamp}").resolve())


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    """Write a UTF-8 CSV using a fixed schema."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def find_ttbin_files(data_root: Path) -> list[Path]:
    """Recursively list TTBIN files."""
    return sorted(p for p in data_root.rglob("*.ttbin") if p.is_file())


def pair_events(t_a: np.ndarray, t_b: np.ndarray, rule: str, window_ps: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pair timestamps using an existing project rule."""
    if rule == "nearest":
        return nearest_pairs(t_a, t_b, window_ps=window_ps)
    if rule == "greedy_unique":
        return greedy_unique_pairs(t_a, t_b, window_ps=window_ps)
    raise ValueError(f"unsupported pairing rule: {rule}")


def estimate_tau0_ps(dt: np.ndarray, bin_width_ps: int) -> float:
    """Estimate one global tau0 from the paired delay histogram peak."""
    if dt.size == 0:
        raise ValueError("cannot estimate tau0 from zero pairs")
    values = np.asarray(dt, dtype=np.float64)
    lo = float(np.min(values))
    hi = float(np.max(values))
    if lo == hi:
        return lo
    width = max(1.0, float(bin_width_ps))
    bins = int(min(20000, max(50, math.ceil((hi - lo) / width))))
    hist, edges = np.histogram(values, bins=bins, range=(lo, hi))
    idx = int(np.argmax(hist))
    return float((edges[idx] + edges[idx + 1]) * 0.5)


def frame_origin_score_for_pairs(pa: np.ndarray, pb_shifted: np.ndarray, dim: int, bin_width_ps: int, frame_origin_ps: float) -> dict[str, Any]:
    """Score one frame origin from paired events without allocating a dense JTI."""
    x_global = _time_tags_to_bins(pa, bin_width_ps=int(bin_width_ps), frame_origin_ps=float(frame_origin_ps))
    y_global = _time_tags_to_bins(pb_shifted, bin_width_ps=int(bin_width_ps), frame_origin_ps=float(frame_origin_ps))
    x_bin = np.mod(x_global, int(dim)).astype(np.int64, copy=False)
    y_bin = np.mod(y_global, int(dim)).astype(np.int64, copy=False)
    total = int(x_bin.size)
    diag_main = int(np.count_nonzero(x_bin == y_bin))
    pm1 = int(np.count_nonzero((x_bin < int(dim) - 1) & (y_bin == x_bin + 1)))
    pm1 += int(np.count_nonzero((x_bin > 0) & (y_bin == x_bin - 1)))
    total_sum = float(total)
    diag_main_fraction = float(diag_main / total_sum) if total else 0.0
    diag_pm1_fraction = float(pm1 / total_sum) if total else 0.0
    return {
        "frame_origin_ps": float(frame_origin_ps),
        "dimension": int(dim),
        "bin_width_ps": int(bin_width_ps),
        "n_pairs": total,
        "total_sum": total_sum,
        "diag_main_sum": float(diag_main),
        "diag_pm1_sum": float(pm1),
        "diag_main_fraction": diag_main_fraction,
        "diag_pm1_fraction": diag_pm1_fraction,
        "diag_contrast": diag_main_fraction - diag_pm1_fraction,
    }


def scan_best_frame_origin_direct(pa: np.ndarray, pb: np.ndarray, tau0_ps: float, dim: int, bin_width_ps: int, jobs: int) -> float:
    """Reuse the existing frame-origin selection rule with direct paired-event scoring."""
    origins = _iter_frame_origins(0.0, float(bin_width_ps), 1.0)
    pb_shifted = pb.astype(np.float64, copy=False) - float(tau0_ps)
    if int(jobs) <= 1:
        rows = [frame_origin_score_for_pairs(pa, pb_shifted, dim, bin_width_ps, origin) for origin in origins]
    else:
        with ThreadPoolExecutor(max_workers=int(jobs)) as executor:
            rows = list(executor.map(lambda origin: frame_origin_score_for_pairs(pa, pb_shifted, dim, bin_width_ps, origin), origins))
    return float(_select_best_frame_origin(rows)["best_frame_origin_ps"])


def circular_delta(x_bin: np.ndarray, y_bin: np.ndarray, dim: int) -> np.ndarray:
    """Compute circular diagonal offsets in bins."""
    half = int(dim // 2)
    delta = ((y_bin - x_bin + half) % int(dim)) - half
    return delta.astype(np.int64, copy=False)


def min_width_for_mass(profile: np.ndarray, fraction: float) -> int:
    """Return the minimal contiguous width reaching the requested mass in rolled coordinates."""
    total = float(np.sum(profile))
    if total <= 0:
        return 0
    target = total * float(fraction)
    if target <= 0:
        return 0
    prefix = np.concatenate(([0.0], np.cumsum(profile.astype(np.float64))))
    best = profile.size
    left = 0
    for right in range(1, profile.size + 1):
        while left < right and (prefix[right] - prefix[left]) >= target:
            best = min(best, right - left)
            left += 1
    return int(best)


def contiguous_true_width(mask: np.ndarray) -> int:
    """Return the longest contiguous width in a boolean mask."""
    if mask.size == 0 or not np.any(mask):
        return 0
    idx = np.flatnonzero(mask)
    splits = np.where(np.diff(idx) > 1)[0]
    starts = np.concatenate(([0], splits + 1))
    ends = np.concatenate((splits + 1, [idx.size]))
    return int(max(idx[end - 1] - idx[start] + 1 for start, end in zip(starts, ends)))


def profile_metrics(profile: np.ndarray, bin_width_ps: int) -> dict[str, float]:
    """Compute peak-centered circular-safe profile metrics."""
    counts = np.asarray(profile, dtype=np.float64)
    total = float(np.sum(counts))
    if total <= 0:
        return {
            "total": 0.0,
            "peak": 0.0,
            "peak_index": math.nan,
            "FWHM_ps": math.nan,
            "central_50_width_ps": math.nan,
            "central_90_width_ps": math.nan,
            "central_95_width_ps": math.nan,
            "sigma_ps": math.nan,
            "participation_time_ps": math.nan,
            "rolled": counts.copy(),
        }
    peak_index = int(np.argmax(counts))
    center = counts.size // 2
    shift = center - peak_index
    rolled = np.roll(counts, shift)
    coords = (np.arange(counts.size, dtype=np.float64) - center) * float(bin_width_ps)
    mean = float(np.sum(coords * rolled) / total)
    sigma = float(np.sqrt(max(0.0, np.sum(((coords - mean) ** 2) * rolled) / total)))
    peak = float(np.max(rolled))
    half = peak * 0.5
    fwhm_bins = contiguous_true_width(rolled >= half)
    p2 = float(np.sum(rolled**2))
    participation = (total**2 / p2) * float(bin_width_ps) if p2 > 0 else math.nan
    return {
        "total": total,
        "peak": peak,
        "peak_index": peak_index,
        "FWHM_ps": float(fwhm_bins * bin_width_ps),
        "central_50_width_ps": float(min_width_for_mass(rolled, 0.50) * bin_width_ps),
        "central_90_width_ps": float(min_width_for_mass(rolled, 0.90) * bin_width_ps),
        "central_95_width_ps": float(min_width_for_mass(rolled, 0.95) * bin_width_ps),
        "sigma_ps": sigma,
        "participation_time_ps": participation,
        "rolled": rolled,
    }


def sparse_min_width_for_mass(bin_indices: np.ndarray, counts: np.ndarray, dim: int, fraction: float) -> int:
    """Minimal circular interval width containing the requested weighted mass."""
    total = float(np.sum(counts))
    if total <= 0 or bin_indices.size == 0:
        return 0
    target = total * float(fraction)
    order = np.argsort(bin_indices, kind="mergesort")
    pos = np.asarray(bin_indices[order], dtype=np.int64)
    w = np.asarray(counts[order], dtype=np.float64)
    pos2 = np.concatenate((pos, pos + int(dim)))
    w2 = np.concatenate((w, w))
    left = 0
    current = 0.0
    best = int(dim)
    for right in range(pos2.size):
        current += float(w2[right])
        while left <= right and current >= target:
            best = min(best, int(pos2[right] - pos2[left] + 1))
            current -= float(w2[left])
            left += 1
    return int(best)


def sparse_fwhm_width(bin_indices: np.ndarray, counts: np.ndarray, dim: int) -> int:
    """Approximate FWHM as the longest contiguous observed run above half max."""
    if counts.size == 0:
        return 0
    half = float(np.max(counts)) * 0.5
    selected = np.sort(np.asarray(bin_indices[counts >= half], dtype=np.int64))
    if selected.size == 0:
        return 0
    if selected.size > 1 and selected[0] == 0 and selected[-1] == int(dim) - 1:
        gaps = np.diff(selected)
        split = int(np.argmax(gaps))
        if gaps[split] > 1:
            selected = np.concatenate((selected[split + 1 :], selected[: split + 1] + int(dim)))
    splits = np.where(np.diff(selected) > 1)[0] if selected.size > 1 else np.array([], dtype=np.int64)
    starts = np.concatenate(([0], splits + 1))
    ends = np.concatenate((splits + 1, [selected.size]))
    return int(max(selected[end - 1] - selected[start] + 1 for start, end in zip(starts, ends)))


def sparse_profile_metrics(bin_indices: np.ndarray, counts: np.ndarray, dim: int, bin_width_ps: int) -> dict[str, float]:
    """Compute circular-safe metrics from sparse profile bins."""
    counts_f = np.asarray(counts, dtype=np.float64)
    bins = np.asarray(bin_indices, dtype=np.int64)
    total = float(np.sum(counts_f))
    if total <= 0:
        return {
            "total": 0.0,
            "peak": 0.0,
            "peak_index": math.nan,
            "FWHM_ps": math.nan,
            "central_50_width_ps": math.nan,
            "central_90_width_ps": math.nan,
            "central_95_width_ps": math.nan,
            "sigma_ps": math.nan,
            "participation_time_ps": math.nan,
        }
    peak_pos = int(np.argmax(counts_f))
    peak_index = int(bins[peak_pos])
    centered_bins = ((bins - peak_index + int(dim) // 2) % int(dim)) - int(dim) // 2
    coords = centered_bins.astype(np.float64) * float(bin_width_ps)
    mean = float(np.sum(coords * counts_f) / total)
    sigma = float(np.sqrt(max(0.0, np.sum(((coords - mean) ** 2) * counts_f) / total)))
    p2 = float(np.sum(counts_f**2))
    return {
        "total": total,
        "peak": float(np.max(counts_f)),
        "peak_index": peak_index,
        "FWHM_ps": float(sparse_fwhm_width(bins, counts_f, dim) * bin_width_ps),
        "central_50_width_ps": float(sparse_min_width_for_mass(bins, counts_f, dim, 0.50) * bin_width_ps),
        "central_90_width_ps": float(sparse_min_width_for_mass(bins, counts_f, dim, 0.90) * bin_width_ps),
        "central_95_width_ps": float(sparse_min_width_for_mass(bins, counts_f, dim, 0.95) * bin_width_ps),
        "sigma_ps": sigma,
        "participation_time_ps": float((total**2 / p2) * bin_width_ps) if p2 > 0 else math.nan,
    }


def pminus_metrics(delta_values: np.ndarray, delta_counts: np.ndarray, bin_width_ps: int) -> dict[str, float]:
    """Compute width metrics for the P_minus profile."""
    counts = np.asarray(delta_counts, dtype=np.float64)
    total = float(np.sum(counts))
    if total <= 0:
        return {
            "peak_delta_bins": math.nan,
            "FWHM_ps": math.nan,
            "sigma_ps": math.nan,
            "central_90_width_ps": math.nan,
            "central_95_width_ps": math.nan,
        }
    peak_idx = int(np.argmax(counts))
    peak_delta = int(delta_values[peak_idx])
    center = counts.size // 2
    shift = center - peak_idx
    rolled = np.roll(counts, shift)
    coords = (np.arange(counts.size, dtype=np.float64) - center) * float(bin_width_ps)
    mean = float(np.sum(coords * rolled) / total)
    sigma = float(np.sqrt(max(0.0, np.sum(((coords - mean) ** 2) * rolled) / total)))
    half = float(np.max(rolled)) * 0.5
    return {
        "peak_delta_bins": float(peak_delta),
        "FWHM_ps": float(contiguous_true_width(rolled >= half) * bin_width_ps),
        "sigma_ps": sigma,
        "central_90_width_ps": float(min_width_for_mass(rolled, 0.90) * bin_width_ps),
        "central_95_width_ps": float(min_width_for_mass(rolled, 0.95) * bin_width_ps),
    }


def sparse_linear_width_for_mass(values: np.ndarray, counts: np.ndarray, fraction: float) -> int:
    """Minimal linear interval width over observed integer coordinates."""
    total = float(np.sum(counts))
    if total <= 0 or values.size == 0:
        return 0
    order = np.argsort(values, kind="mergesort")
    pos = np.asarray(values[order], dtype=np.int64)
    w = np.asarray(counts[order], dtype=np.float64)
    target = total * float(fraction)
    left = 0
    current = 0.0
    best = int(pos[-1] - pos[0] + 1)
    for right in range(pos.size):
        current += float(w[right])
        while left <= right and current >= target:
            best = min(best, int(pos[right] - pos[left] + 1))
            current -= float(w[left])
            left += 1
    return int(best)


def sparse_pminus_metrics(delta_values: np.ndarray, delta_counts: np.ndarray, bin_width_ps: int) -> dict[str, float]:
    """Compute P_minus metrics from sparse observed deltas."""
    values = np.asarray(delta_values, dtype=np.int64)
    counts = np.asarray(delta_counts, dtype=np.float64)
    total = float(np.sum(counts))
    if total <= 0:
        return {
            "peak_delta_bins": math.nan,
            "FWHM_ps": math.nan,
            "sigma_ps": math.nan,
            "central_90_width_ps": math.nan,
            "central_95_width_ps": math.nan,
        }
    peak_idx = int(np.argmax(counts))
    peak_delta = int(values[peak_idx])
    coords = values.astype(np.float64) * float(bin_width_ps)
    mean = float(np.sum(coords * counts) / total)
    sigma = float(np.sqrt(max(0.0, np.sum(((coords - mean) ** 2) * counts) / total)))
    half = float(np.max(counts)) * 0.5
    fwhm = sparse_linear_width_for_mass(values[counts >= half], counts[counts >= half], 1.0)
    return {
        "peak_delta_bins": float(peak_delta),
        "FWHM_ps": float(fwhm * bin_width_ps),
        "sigma_ps": sigma,
        "central_90_width_ps": float(sparse_linear_width_for_mass(values, counts, 0.90) * bin_width_ps),
        "central_95_width_ps": float(sparse_linear_width_for_mass(values, counts, 0.95) * bin_width_ps),
    }


def edge_fraction(profile: np.ndarray, fraction: float) -> float:
    """Compute the fraction of counts near the circular frame edges."""
    total = float(np.sum(profile))
    if total <= 0:
        return math.nan
    edge_bins = max(1, int(profile.size * float(fraction)))
    edge_total = float(np.sum(profile[:edge_bins]) + np.sum(profile[-edge_bins:]))
    return edge_total / total


def sparse_edge_fraction(bin_indices: np.ndarray, counts: np.ndarray, dim: int, fraction: float) -> float:
    """Compute edge count fraction from sparse bins."""
    total = float(np.sum(counts))
    if total <= 0:
        return math.nan
    edge_bins = max(1, int(int(dim) * float(fraction)))
    bins = np.asarray(bin_indices, dtype=np.int64)
    edge_mask = (bins < edge_bins) | (bins >= int(dim) - edge_bins)
    return float(np.sum(np.asarray(counts, dtype=np.float64)[edge_mask]) / total)


def unique_counts(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return sorted unique integer values and their counts."""
    if values.size == 0:
        return np.array([], dtype=np.int64), np.array([], dtype=np.int64)
    unique, counts = np.unique(np.asarray(values, dtype=np.int64), return_counts=True)
    return unique.astype(np.int64, copy=False), counts.astype(np.int64, copy=False)


def choose_profile_storage(dim: int, cfg: Config) -> str:
    """Choose dense or sparse profile storage for one dim."""
    if cfg.profile_storage in {"dense", "sparse"}:
        return cfg.profile_storage
    return "dense" if int(dim) <= int(cfg.dense_profile_max_bins) else "sparse"


def diag_profiles_for_dim(
    pa: np.ndarray,
    pb: np.ndarray,
    tau0_ps: float,
    dim: int,
    bin_width_ps: int,
    frame_origin_ps: float,
    diag_band_bins: int,
    storage: str,
) -> dict[str, Any]:
    """Directly accumulate P_plus and P_minus for one dim/frame mapping."""
    a_shifted = pa  # keep as int64
    b_shifted = pb - np.int64(int(tau0_ps))
    x_global = _time_tags_to_bins(a_shifted, bin_width_ps=int(bin_width_ps), frame_origin_ps=float(frame_origin_ps))
    y_global = _time_tags_to_bins(b_shifted, bin_width_ps=int(bin_width_ps), frame_origin_ps=float(frame_origin_ps))
    x_bin = np.mod(x_global, int(dim)).astype(np.int64, copy=False)
    y_bin = np.mod(y_global, int(dim)).astype(np.int64, copy=False)
    delta = circular_delta(x_bin, y_bin, int(dim))
    diag_mask = np.abs(delta) <= int(diag_band_bins)
    p_plus_bins, p_plus_counts = unique_counts(x_bin[diag_mask])
    p_minus_bins, p_minus_counts = unique_counts(delta)

    if storage == "dense":
        p_plus = np.zeros(int(dim), dtype=np.int64)
        if p_plus_bins.size:
            p_plus[p_plus_bins] = p_plus_counts
        delta_values = np.arange(-(int(dim) // 2), int(dim) - (int(dim) // 2), dtype=np.int64)
        p_minus = np.zeros(delta_values.size, dtype=np.int64)
        if p_minus_bins.size:
            p_minus[p_minus_bins + (int(dim) // 2)] = p_minus_counts
        estimated_bytes = int(p_plus.nbytes + p_minus.nbytes)
    else:
        p_plus = p_plus_counts
        delta_values = p_minus_bins
        p_minus = p_minus_counts
        estimated_bytes = int(p_plus_bins.nbytes + p_plus_counts.nbytes + p_minus_bins.nbytes + p_minus_counts.nbytes)

    return {
        "x_bin": x_bin,
        "y_bin": y_bin,
        "delta": delta,
        "P_plus_bins": p_plus_bins,
        "delta_values": delta_values,
        "P_plus": p_plus,
        "P_minus": p_minus,
        "profile_storage": storage,
        "estimated_profile_bytes": estimated_bytes,
        "pairs_in_diag_band": int(np.count_nonzero(diag_mask)),
    }


def save_profile_csv(path: Path, bin_width_ps: int, counts: np.ndarray, rolled_counts: np.ndarray | None = None, bin_indices: np.ndarray | None = None) -> None:
    """Save a P_plus profile CSV."""
    fieldnames = ["bin_index", "time_ps", "counts"]
    if rolled_counts is not None:
        fieldnames.extend(["rolled_bin_index", "rolled_time_ps", "rolled_counts"])
    rows = []
    bins = np.arange(counts.size, dtype=np.int64) if bin_indices is None else np.asarray(bin_indices, dtype=np.int64)
    center = (rolled_counts.size // 2) if rolled_counts is not None else 0
    for idx, value in zip(bins.tolist(), counts.tolist()):
        row = {
            "bin_index": idx,
            "time_ps": idx * int(bin_width_ps),
            "counts": int(value),
        }
        if rolled_counts is not None:
            row["rolled_bin_index"] = idx - center
            row["rolled_time_ps"] = (idx - center) * int(bin_width_ps)
            row["rolled_counts"] = int(rolled_counts[int(idx)])
        rows.append(row)
    write_csv(path, fieldnames, rows)


def save_pminus_csv(path: Path, delta_values: np.ndarray, bin_width_ps: int, counts: np.ndarray) -> None:
    """Save a P_minus profile CSV."""
    rows = [
        {
            "delta_bins": int(delta_bin),
            "delta_time_ps": int(delta_bin) * int(bin_width_ps),
            "counts": int(value),
        }
        for delta_bin, value in zip(delta_values.tolist(), counts.tolist())
    ]
    write_csv(path, ["delta_bins", "delta_time_ps", "counts"], rows)


def plot_profile(path: Path, x: np.ndarray, y: np.ndarray, xlabel: str, title: str) -> None:
    """Save a simple profile plot."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8.0, 4.5), dpi=160)
    ax.plot(x, y, linewidth=1.0)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("counts")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(str(path))
    plt.close(fig)


def load_config_from_reader(path: Path) -> dict[str, Any]:
    """Load TimeTagger configuration only."""
    from TimeTagger import FileReader  # type: ignore

    reader = FileReader(str(path))
    try:
        return dict(reader.getConfiguration())
    except Exception:
        return {}


def load_tags_from_cache(cache_root: Path, logical_id: str, channels: tuple[int, int]) -> Tags | None:
    """Load cached channel tags from a previous output directory when available."""
    cache = cache_root / "tag_cache" / logical_id / f"tags_cache_ch{int(channels[0])}_ch{int(channels[1])}.npz"
    if not cache.exists():
        return None
    with np.load(str(cache), allow_pickle=False) as z:
        meta = json.loads(str(z["meta_json"].item()))
        return Tags(np.asarray(z["t_a"], dtype=np.int64), np.asarray(z["t_b"], dtype=np.int64), meta)


def preview_ttbin_signature(path: Path, channels: tuple[int, int]) -> dict[str, Any]:
    """Collect a lightweight signature for dry-run dedupe preview."""
    from TimeTagger import FileReader  # type: ignore

    reader = FileReader(str(path))
    cfg = {}
    try:
        cfg = dict(reader.getConfiguration())
    except Exception:
        cfg = {}
    writer_filename = None
    for measurement in cfg.get("measurements", []):
        if measurement.get("name") == "FileWriter":
            writer_filename = measurement.get("params", {}).get("filename")
            break
    total_events = 0
    samples: list[int] = []
    channel_counts: dict[int, int] = defaultdict(int)
    while reader.hasData() and total_events < 200000:
        data = reader.getData(200000)
        ch = np.asarray(data.getChannels(), dtype=np.int64)
        ts = np.asarray(data.getTimestamps(), dtype=np.int64)
        total_events += int(ts.size)
        if ts.size and len(samples) < 8:
            samples.extend(int(x) for x in ts[: max(0, 8 - len(samples))].tolist())
        if ch.size:
            for value, count in zip(*np.unique(ch, return_counts=True)):
                if int(value) in channels:
                    channel_counts[int(value)] += int(count)
    return {
        "writer_filename": writer_filename,
        "total_events": total_events,
        "first_timestamps_sample": samples,
        "selected_channel_counts": {str(k): int(v) for k, v in sorted(channel_counts.items())},
    }


def dedupe_datasets(paths: list[Path], channels: tuple[int, int]) -> tuple[list[LogicalDataset], list[dict[str, Any]]]:
    """Collapse duplicate logical recordings."""
    by_key: dict[str, list[tuple[Path, dict[str, Any]]]] = defaultdict(list)
    report_rows: list[dict[str, Any]] = []
    for path in paths:
        try:
            sig = preview_ttbin_signature(path, channels)
            if sig["writer_filename"]:
                key = f"filewriter::{sig['writer_filename']}"
                method = "FileWriter.filename"
            else:
                key = json.dumps(
                    {
                        "first_timestamps_sample": sig["first_timestamps_sample"],
                        "total_events": sig["total_events"],
                        "selected_channel_counts": sig["selected_channel_counts"],
                    },
                    sort_keys=True,
                    ensure_ascii=False,
                )
                method = "fallback_signature"
            by_key[key].append((path, sig | {"dedupe_method": method}))
        except Exception as exc:
            report_rows.append(
                {
                    "logical_id": safe_stem(path.stem),
                    "kept_path": str(path),
                    "duplicate_paths": "",
                    "dedupe_method": "error",
                    "total_events": "",
                    "selected_channel_counts": "",
                    "status": "DEDUPE_FAILED",
                    "error": repr(exc),
                    "suggestion": "Check TimeTagger readability or disable dedupe if only one file should be processed.",
                }
            )
    datasets: list[LogicalDataset] = []
    for idx, (key, members) in enumerate(sorted(by_key.items(), key=lambda item: item[1][0][0].name)):
        members_sorted = sorted(members, key=lambda item: (len(item[0].name), item[0].name))
        kept_path, info = members_sorted[0]
        dup_paths = tuple(item[0] for item in members_sorted[1:])
        logical_id = f"{idx:03d}_{safe_stem(info['writer_filename'] or kept_path.stem)}"
        datasets.append(
            LogicalDataset(
                logical_id=logical_id,
                kept_path=kept_path,
                duplicate_paths=dup_paths,
                dedupe_method=str(info["dedupe_method"]),
                total_events=int(info["total_events"]) if info["total_events"] is not None else None,
                selected_channel_counts={k: int(v) for k, v in info["selected_channel_counts"].items()},
                filewriter_filename=info["writer_filename"],
            )
        )
        report_rows.append(
            {
                "logical_id": logical_id,
                "kept_path": str(kept_path),
                "duplicate_paths": ";".join(str(p) for p in dup_paths),
                "dedupe_method": str(info["dedupe_method"]),
                "total_events": info["total_events"],
                "selected_channel_counts": json.dumps(info["selected_channel_counts"], ensure_ascii=False),
                "status": DEFAULT_STATUS_OK,
                "error": "",
                "suggestion": "",
            }
        )
    return datasets, report_rows


def save_run_config(path: Path, cfg: Config, input_paths: list[Path], datasets: list[LogicalDataset]) -> None:
    """Persist the resolved configuration."""
    payload = {
        "data_root": str(cfg.data_root),
        "channels": list(cfg.channels),
        "pairing_rule": cfg.pairing_rule,
        "coincidence_window_ps": cfg.coincidence_window_ps,
        "bin_width_ps": cfg.bin_width_ps,
        "dims": list(cfg.dims),
        "auto_dim": cfg.auto_dim,
        "auto_stop": cfg.auto_stop,
        "diag_band_bins": cfg.diag_band_bins,
        "edge_bins_fraction": cfg.edge_bins_fraction,
        "edge_fraction_threshold": cfg.edge_fraction_threshold,
        "stop_width_ratio": cfg.stop_width_ratio,
        "stop_width_change": cfg.stop_width_change,
        "dedupe_ttbin": cfg.dedupe_ttbin,
        "dims_explicit": cfg.dims_explicit,
        "jobs": cfg.jobs,
        "dense_profile_max_bins": cfg.dense_profile_max_bins,
        "continue_from_existing": str(cfg.continue_from_existing) if cfg.continue_from_existing is not None else None,
        "profile_storage": cfg.profile_storage,
        "output_dir": str(cfg.output_dir),
        "input_ttbin_files": [str(p) for p in input_paths],
        "logical_datasets": [
            {
                "logical_id": d.logical_id,
                "kept_path": str(d.kept_path),
                "duplicate_paths": [str(p) for p in d.duplicate_paths],
                "dedupe_method": d.dedupe_method,
                "total_events": d.total_events,
                "selected_channel_counts": d.selected_channel_counts,
            }
            for d in datasets
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_csv_dicts(path: Path) -> list[dict[str, Any]]:
    """Read a CSV into dictionaries, returning an empty list if absent."""
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return [dict(row) for row in csv.DictReader(f)]


def previous_context(path: Path | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Load previous summary rows and per-logical final context."""
    if path is None:
        return [], [], {}
    summary_rows = read_csv_dicts(path / "pplus_auto_dim_summary.csv")
    decision_rows = read_csv_dicts(path / "auto_dim_decision.csv")
    file_rows = read_csv_dicts(path / "file_summary.csv")
    by_logical = {str(row.get("logical_id")): row for row in file_rows}
    return summary_rows, decision_rows, by_logical


def dense_vs_direct_check(logical_id: str, pa: np.ndarray, pb: np.ndarray, tau0_ps: float, dim: int, bin_width_ps: int, frame_origin_ps: float, diag_band_bins: int) -> dict[str, Any]:
    """Optional sanity check against a dense JTI reconstruction at one dim."""
    profiles = diag_profiles_for_dim(pa, pb, tau0_ps, dim, bin_width_ps, frame_origin_ps, diag_band_bins, "dense")
    x_bin = profiles["x_bin"]
    y_bin = profiles["y_bin"]
    counts = np.zeros((dim, dim), dtype=np.int64)
    np.add.at(counts, (x_bin, y_bin), 1)
    delta = circular_delta(np.arange(dim)[:, None], np.arange(dim)[None, :], dim)
    dense_mask = np.abs(delta) <= int(diag_band_bins)
    p_plus_dense = np.sum(counts * dense_mask, axis=1)
    p_plus_direct = profiles["P_plus"]
    diff = np.abs(p_plus_dense.astype(np.int64) - p_plus_direct.astype(np.int64))
    total_direct = float(np.sum(np.abs(p_plus_direct)))
    return {
        "logical_id": logical_id,
        "dim": dim,
        "bin_width_ps": bin_width_ps,
        "frame_origin_ps": frame_origin_ps,
        "max_abs_diff": int(np.max(diff)) if diff.size else 0,
        "total_abs_diff": int(np.sum(diff)),
        "relative_l1_diff": float(np.sum(diff) / total_direct) if total_direct > 0 else 0.0,
    }


def process_dataset(
    dataset: LogicalDataset,
    cfg: Config,
    run_paths: dict[str, Path],
    previous_info: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    """Process one deduped logical dataset across dims."""
    rows: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    previous_w95 = math.nan
    stop_reason = ""
    final_row: dict[str, Any] | None = None

    try:
        tags = load_tags_from_cache(cfg.continue_from_existing, dataset.logical_id, cfg.channels) if cfg.continue_from_existing is not None else None
        if tags is None:
            tags = load_tags(dataset.kept_path, run_paths["cache"] / dataset.logical_id, cfg.channels[0], cfg.channels[1], None)
    except Exception as exc:
        row = {
            "logical_id": dataset.logical_id,
            "file_name": dataset.kept_path.name,
            "file_path": str(dataset.kept_path),
            "dim": "",
            "status": "TTBIN_READ_FAILED",
            "error": repr(exc),
            "suggestion": "Check TimeTagger bindings, file accessibility, and selected channels.",
        }
        return [row], decisions, {
            "logical_id": dataset.logical_id,
            "kept_file": str(dataset.kept_path),
            "duplicate_count": len(dataset.duplicate_paths),
            "n_pairs": 0,
            "tau0_ps": math.nan,
            "final_dim": "",
            "final_frame_length_ps": "",
            "final_W95_ps": "",
            "final_width_ratio_95": "",
            "final_edge_fraction": "",
            "final_covered": False,
            "final_status": "TTBIN_READ_FAILED",
            "stop_reason": "read_failed",
            "output_profile_path": "",
            "output_plot_path": "",
        }, checks

    try:
        pa, pb, dt = pair_events(tags.t_a, tags.t_b, cfg.pairing_rule, cfg.coincidence_window_ps)
    except Exception as exc:
        row = {
            "logical_id": dataset.logical_id,
            "file_name": dataset.kept_path.name,
            "file_path": str(dataset.kept_path),
            "dim": "",
            "status": "PAIRING_FAILED",
            "error": repr(exc),
            "suggestion": "Verify channels and pairing rule, or adjust coincidence_window_ps.",
        }
        return [row], decisions, {
            "logical_id": dataset.logical_id,
            "kept_file": str(dataset.kept_path),
            "duplicate_count": len(dataset.duplicate_paths),
            "n_pairs": 0,
            "tau0_ps": math.nan,
            "final_dim": "",
            "final_frame_length_ps": "",
            "final_W95_ps": "",
            "final_width_ratio_95": "",
            "final_edge_fraction": "",
            "final_covered": False,
            "final_status": "PAIRING_FAILED",
            "stop_reason": "pairing_failed",
            "output_profile_path": "",
            "output_plot_path": "",
        }, checks

    if dt.size == 0:
        row = {
            "logical_id": dataset.logical_id,
            "file_name": dataset.kept_path.name,
            "file_path": str(dataset.kept_path),
            "dim": "",
            "status": "EMPTY_PAIRS",
            "error": "No pairs after pairing cutoff.",
            "suggestion": "Check channels or increase coincidence_window_ps if physically justified.",
        }
        return [row], decisions, {
            "logical_id": dataset.logical_id,
            "kept_file": str(dataset.kept_path),
            "duplicate_count": len(dataset.duplicate_paths),
            "n_pairs": 0,
            "tau0_ps": math.nan,
            "final_dim": "",
            "final_frame_length_ps": "",
            "final_W95_ps": "",
            "final_width_ratio_95": "",
            "final_edge_fraction": "",
            "final_covered": False,
            "final_status": "EMPTY_PAIRS",
            "stop_reason": "empty_pairs",
            "output_profile_path": "",
            "output_plot_path": "",
        }, checks

    try:
        prior_tau = None if previous_info is None else previous_info.get("tau0_ps")
        tau0_ps = float(prior_tau) if prior_tau not in (None, "") else estimate_tau0_ps(dt, cfg.bin_width_ps)
    except Exception as exc:
        row = {
            "logical_id": dataset.logical_id,
            "file_name": dataset.kept_path.name,
            "file_path": str(dataset.kept_path),
            "dim": "",
            "status": "TAU0_ESTIMATION_FAILED",
            "error": repr(exc),
            "suggestion": "Inspect dt histogram and pairing quality.",
        }
        return [row], decisions, {
            "logical_id": dataset.logical_id,
            "kept_file": str(dataset.kept_path),
            "duplicate_count": len(dataset.duplicate_paths),
            "n_pairs": int(dt.size),
            "tau0_ps": math.nan,
            "final_dim": "",
            "final_frame_length_ps": "",
            "final_W95_ps": "",
            "final_width_ratio_95": "",
            "final_edge_fraction": "",
            "final_covered": False,
            "final_status": "TAU0_ESTIMATION_FAILED",
            "stop_reason": "tau0_failed",
            "output_profile_path": "",
            "output_plot_path": "",
        }, checks

    if previous_info is not None and previous_info.get("final_W95_ps") not in (None, ""):
        try:
            previous_w95 = float(previous_info["final_W95_ps"])
        except Exception:
            previous_w95 = math.nan

    for dim in cfg.dims:
        status = DEFAULT_STATUS_OK
        error = ""
        suggestion = ""
        frame_length_ps = int(dim) * int(cfg.bin_width_ps)
        try:
            frame_origin_ps = scan_best_frame_origin_direct(pa, pb, tau0_ps, dim, cfg.bin_width_ps, cfg.jobs)
        except Exception as exc:
            rows.append(
                {
                    "logical_id": dataset.logical_id,
                    "file_name": dataset.kept_path.name,
                    "file_path": str(dataset.kept_path),
                    "dim": dim,
                    "bin_width_ps": cfg.bin_width_ps,
                    "frame_length_ps": frame_length_ps,
                    "frame_origin_ps": "",
                    "tau0_ps": tau0_ps,
                    "channels": f"{cfg.channels[0]},{cfg.channels[1]}",
                    "pairing_rule": cfg.pairing_rule,
                    "coincidence_window_ps": cfg.coincidence_window_ps,
                    "diag_band_bins": cfg.diag_band_bins,
                    "status": "FRAME_ORIGIN_FAILED",
                    "error": repr(exc),
                    "suggestion": "Inspect frame-origin scan metrics or simplify the scan range.",
                }
            )
            continue

        try:
            storage = choose_profile_storage(dim, cfg)
            profiles = diag_profiles_for_dim(pa, pb, tau0_ps, dim, cfg.bin_width_ps, frame_origin_ps, cfg.diag_band_bins, storage)
            p_plus = profiles["P_plus"]
            p_plus_bins = profiles["P_plus_bins"]
            p_minus = profiles["P_minus"]
            delta_values = profiles["delta_values"]
            pairs_in_diag_band = int(profiles["pairs_in_diag_band"])
            if pairs_in_diag_band <= 0:
                status = "EMPTY_DIAG_BAND"
                suggestion = "diag_band_bins may be too narrow for this dim."

            if storage == "dense":
                plus_metrics = profile_metrics(p_plus, cfg.bin_width_ps)
                minus_metrics = pminus_metrics(delta_values, p_minus, cfg.bin_width_ps)
                edge = edge_fraction(p_plus, cfg.edge_bins_fraction)
                rolled_counts = np.asarray(plus_metrics["rolled"], dtype=np.float64)
                pplus_csv_bins = None
            else:
                plus_metrics = sparse_profile_metrics(p_plus_bins, p_plus, dim, cfg.bin_width_ps)
                minus_metrics = sparse_pminus_metrics(delta_values, p_minus, cfg.bin_width_ps)
                edge = sparse_edge_fraction(p_plus_bins, p_plus, dim, cfg.edge_bins_fraction)
                rolled_counts = None
                pplus_csv_bins = p_plus_bins
        except Exception as exc:
            rows.append(
                {
                    "logical_id": dataset.logical_id,
                    "file_name": dataset.kept_path.name,
                    "file_path": str(dataset.kept_path),
                    "dim": dim,
                    "bin_width_ps": cfg.bin_width_ps,
                    "frame_length_ps": frame_length_ps,
                    "frame_origin_ps": frame_origin_ps,
                    "tau0_ps": tau0_ps,
                    "channels": f"{cfg.channels[0]},{cfg.channels[1]}",
                    "pairing_rule": cfg.pairing_rule,
                    "coincidence_window_ps": cfg.coincidence_window_ps,
                    "diag_band_bins": cfg.diag_band_bins,
                    "status": "PROFILE_METRIC_FAILED",
                    "error": repr(exc),
                    "suggestion": "Inspect P_plus/P_minus generation for this dim.",
                }
            )
            continue

        w95 = float(plus_metrics["central_95_width_ps"])
        width_ratio_95 = float(w95 / frame_length_ps) if frame_length_ps > 0 and np.isfinite(w95) else math.nan
        relative_change = (
            float(abs(w95 - previous_w95) / max(abs(w95), 1e-12))
            if np.isfinite(previous_w95) and np.isfinite(w95)
            else math.nan
        )
        covered = bool(
            np.isfinite(width_ratio_95)
            and np.isfinite(edge)
            and np.isfinite(relative_change)
            and width_ratio_95 < cfg.stop_width_ratio
            and edge < cfg.edge_fraction_threshold
            and relative_change < cfg.stop_width_change
        )
        if not np.isfinite(relative_change):
            covered = False
        if dim == cfg.dims[-1] and not covered:
            status = "NOT_SATURATED"
            suggestion = "Current max_dim only provides a lower bound on P_plus support."

        profile_base = run_paths["profiles"] / f"P_plus_{safe_stem(dataset.logical_id)}_dim{dim}.csv"
        pminus_base = run_paths["profiles"] / f"P_minus_{safe_stem(dataset.logical_id)}_dim{dim}.csv"
        save_profile_csv(profile_base, cfg.bin_width_ps, p_plus, rolled_counts=rolled_counts, bin_indices=pplus_csv_bins)
        save_pminus_csv(pminus_base, delta_values, cfg.bin_width_ps, p_minus)

        try:
            plot_profile(
                run_paths["plots"] / f"P_plus_{safe_stem(dataset.logical_id)}_dim{dim}.png",
                (np.arange(dim) if storage == "dense" else p_plus_bins) * cfg.bin_width_ps,
                p_plus.astype(np.float64),
                "time_ps",
                f"P_plus dim={dim} bw={cfg.bin_width_ps}ps frame={frame_length_ps}ps band={cfg.diag_band_bins} W95={w95:.1f}ps",
            )
            plot_profile(
                run_paths["plots"] / f"P_minus_{safe_stem(dataset.logical_id)}_dim{dim}.png",
                delta_values.astype(np.float64) * cfg.bin_width_ps,
                p_minus.astype(np.float64),
                "delta_time_ps",
                f"P_minus dim={dim} bw={cfg.bin_width_ps}ps",
            )
        except Exception as exc:
            status = "PLOT_FAILED" if status == DEFAULT_STATUS_OK else status
            error = repr(exc)
            suggestion = suggestion or "matplotlib plotting failed; CSV profiles are still available."

        row = {
            "logical_id": dataset.logical_id,
            "file_name": dataset.kept_path.name,
            "file_path": str(dataset.kept_path),
            "dim": int(dim),
            "bin_width_ps": cfg.bin_width_ps,
            "frame_length_ps": frame_length_ps,
            "frame_origin_ps": frame_origin_ps,
            "tau0_ps": tau0_ps,
            "channels": f"{cfg.channels[0]},{cfg.channels[1]}",
            "pairing_rule": cfg.pairing_rule,
            "coincidence_window_ps": cfg.coincidence_window_ps,
            "diag_band_bins": cfg.diag_band_bins,
            "total_pairs": int(dt.size),
            "pairs_in_diag_band": pairs_in_diag_band,
            "diag_band_fraction": float(pairs_in_diag_band / dt.size) if dt.size else math.nan,
            "P_plus_total": float(plus_metrics["total"]),
            "P_plus_peak": float(plus_metrics["peak"]),
            "P_plus_peak_index": float(plus_metrics["peak_index"]) if np.isfinite(plus_metrics["peak_index"]) else math.nan,
            "P_plus_FWHM_ps": float(plus_metrics["FWHM_ps"]),
            "P_plus_central_50_width_ps": float(plus_metrics["central_50_width_ps"]),
            "P_plus_central_90_width_ps": float(plus_metrics["central_90_width_ps"]),
            "P_plus_central_95_width_ps": w95,
            "P_plus_sigma_ps": float(plus_metrics["sigma_ps"]),
            "P_plus_participation_time_ps": float(plus_metrics["participation_time_ps"]),
            "width_ratio_95": width_ratio_95,
            "edge_fraction": edge,
            "relative_change_W95": relative_change,
            "covered": covered,
            "P_minus_peak_delta_bins": float(minus_metrics["peak_delta_bins"]),
            "P_minus_FWHM_ps": float(minus_metrics["FWHM_ps"]),
            "P_minus_sigma_ps": float(minus_metrics["sigma_ps"]),
            "P_minus_central_90_width_ps": float(minus_metrics["central_90_width_ps"]),
            "P_minus_central_95_width_ps": float(minus_metrics["central_95_width_ps"]),
            "profile_storage": storage,
            "n_nonzero_P_plus_bins": int(p_plus_bins.size) if storage == "sparse" else int(np.count_nonzero(p_plus)),
            "estimated_profile_bytes": int(profiles["estimated_profile_bytes"]),
            "frame_origin_method": "direct_paired_event_scan",
            "status": status,
            "error": error,
            "suggestion": suggestion,
        }
        rows.append(row)
        stop_reason = "covered" if covered else ""
        decisions.append(
            {
                "logical_id": dataset.logical_id,
                "dim": int(dim),
                "frame_length_ps": frame_length_ps,
                "W95_ps": w95,
                "width_ratio_95": width_ratio_95,
                "edge_fraction": edge,
                "relative_change_W95": relative_change,
                "covered": covered,
                "stop_reason": stop_reason,
            }
        )
        final_row = row
        previous_w95 = w95

        if dim == 32:
            try:
                checks.append(dense_vs_direct_check(dataset.logical_id, pa, pb, tau0_ps, dim, cfg.bin_width_ps, frame_origin_ps, cfg.diag_band_bins))
            except Exception:
                pass

        should_early_stop = cfg.auto_dim and covered and (not cfg.dims_explicit or cfg.auto_stop)
        if should_early_stop:
            break

    if final_row is None:
        return rows, decisions, {
            "logical_id": dataset.logical_id,
            "kept_file": str(dataset.kept_path),
            "duplicate_count": len(dataset.duplicate_paths),
            "n_pairs": int(dt.size),
            "tau0_ps": tau0_ps,
            "final_dim": "",
            "final_frame_length_ps": "",
            "final_W95_ps": "",
            "final_width_ratio_95": "",
            "final_edge_fraction": "",
            "final_covered": False,
            "final_status": "PROFILE_METRIC_FAILED",
            "stop_reason": "no_valid_dim",
            "output_profile_path": "",
            "output_plot_path": "",
        }, checks

    return rows, decisions, {
        "logical_id": dataset.logical_id,
        "kept_file": str(dataset.kept_path),
        "duplicate_count": len(dataset.duplicate_paths),
        "n_pairs": int(dt.size),
        "tau0_ps": tau0_ps,
        "final_dim": final_row["dim"],
        "final_frame_length_ps": final_row["frame_length_ps"],
        "final_W95_ps": final_row["P_plus_central_95_width_ps"],
        "final_width_ratio_95": final_row["width_ratio_95"],
        "final_edge_fraction": final_row["edge_fraction"],
        "final_covered": final_row["covered"],
        "final_status": final_row["status"],
        "stop_reason": stop_reason or ("max_dim_reached" if final_row["status"] == "NOT_SATURATED" else "completed"),
        "output_profile_path": str(run_paths["profiles"] / f"P_plus_{safe_stem(dataset.logical_id)}_dim{final_row['dim']}.csv"),
        "output_plot_path": str(run_paths["plots"] / f"time_support_vs_dim_{safe_stem(dataset.logical_id)}.png"),
    }, checks


def overlay_and_summary_plots(logical_id: str, rows: list[dict[str, Any]], run_paths: dict[str, Path]) -> None:
    """Create overlay and summary plots for one logical dataset."""
    import matplotlib.pyplot as plt

    subset = [row for row in rows if row.get("logical_id") == logical_id and row.get("dim") not in ("", None)]
    if not subset:
        return
    safe_id = safe_stem(logical_id)
    fig, ax = plt.subplots(figsize=(8.0, 4.5), dpi=160)
    for row in subset:
        dim = int(row["dim"])
        profile_path = run_paths["profiles"] / f"P_plus_{safe_id}_dim{dim}.csv"
        if not profile_path.exists():
            continue
        data = np.genfromtxt(str(profile_path), delimiter=",", names=True, dtype=None, encoding="utf-8")
        counts = np.asarray(data["counts"], dtype=np.float64)
        total = float(np.sum(counts))
        if total > 0:
            ax.plot(np.asarray(data["time_ps"], dtype=np.float64), counts / total, label=f"dim={dim}")
    ax.set_xlabel("time_ps")
    ax.set_ylabel("normalized counts")
    ax.set_title("P_plus overlay")
    ax.legend()
    fig.tight_layout()
    fig.savefig(str(run_paths["plots"] / f"P_plus_overlay_{safe_id}.png"))
    plt.close(fig)

    dims = np.asarray([int(row["dim"]) for row in subset], dtype=np.int64)
    frame_lengths = np.asarray([float(row["frame_length_ps"]) for row in subset], dtype=np.float64)
    fig, ax = plt.subplots(figsize=(8.0, 4.5), dpi=160)
    ax.plot(frame_lengths, np.asarray([float(row["P_plus_FWHM_ps"]) for row in subset], dtype=np.float64), label="FWHM")
    ax.plot(frame_lengths, np.asarray([float(row["P_plus_central_90_width_ps"]) for row in subset], dtype=np.float64), label="W90")
    ax.plot(frame_lengths, np.asarray([float(row["P_plus_central_95_width_ps"]) for row in subset], dtype=np.float64), label="W95")
    ax.plot(frame_lengths, np.asarray([float(row["P_plus_participation_time_ps"]) for row in subset], dtype=np.float64), label="participation")
    ax.set_xlabel("frame_length_ps")
    ax.set_ylabel("time support (ps)")
    ax.set_title("Time support vs dim")
    ax.legend()
    fig.tight_layout()
    fig.savefig(str(run_paths["plots"] / f"time_support_vs_dim_{safe_id}.png"))
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.0, 4.5), dpi=160)
    ax.plot(dims, np.asarray([float(row["diag_band_fraction"]) for row in subset], dtype=np.float64))
    ax.set_xlabel("dim")
    ax.set_ylabel("pairs_in_diag_band / total_pairs")
    ax.set_title("Diag band fraction vs dim")
    fig.tight_layout()
    fig.savefig(str(run_paths["plots"] / f"diag_band_fraction_vs_dim_{safe_id}.png"))
    plt.close(fig)


def write_readme(cfg: Config, datasets: list[LogicalDataset], file_summaries: list[dict[str, Any]], run_paths: dict[str, Path]) -> None:
    """Write the required README."""
    lines = [
        "# Type0ppln direct P_plus / auto-dim pilot",
        "",
        "This script estimates the JTI main-diagonal direction profile P_plus directly from paired events.",
        "It does not compute Schmidt number, does not compute K, and does not allocate a dense dim x dim JTI for the main run.",
        "",
        "## Definitions",
        "",
        "- `P_plus[x_bin] += 1` for pairs with `abs(circular_delta) <= diag_band_bins`.",
        "- `P_minus[delta] += 1` for all circular diagonal offsets, used to inspect the perpendicular relative-delay width.",
        "- `coincidence_window_ps` is the pairing cutoff.",
        "- `bin_width_ps` is the JTI/frame binning resolution.",
        "",
        "## Complexity",
        "",
        "The main accumulation is O(dim) in profile storage, not O(dim^2).",
        "",
        "## Reused project logic",
        "",
        "- `.ttbin` reading reuses `load_tags`.",
        "- pairing reuses `nearest_pairs` / `greedy_unique_pairs`.",
        "- `tau0_ps` is estimated once per logical file from the paired delay histogram peak.",
        "- `frame_origin` uses the existing dense-JTI selection rule: maximize main diagonal fraction, then minimize pm1 fraction, then maximize contrast, then take the smallest origin.",
        "",
        "## Dedupe",
        "",
        "Logical datasets are deduplicated by `FileWriter.filename` when available, otherwise by a fallback signature using a timestamp sample, total events, and selected channel counts.",
        "",
        "## Parameters",
        "",
        f"- channels={cfg.channels[0]},{cfg.channels[1]}",
        f"- pairing_rule={cfg.pairing_rule}",
        f"- coincidence_window_ps={cfg.coincidence_window_ps}",
        f"- bin_width_ps={cfg.bin_width_ps}",
        f"- diag_band_bins={cfg.diag_band_bins}",
        f"- dims={list(cfg.dims)}",
        "",
        "## Dim sweep interpretation",
        "",
        "- If P_plus width is close to frame length, the current dim only provides a lower bound.",
        "- If width saturates while edge_fraction is low, the final W90/W95 estimate is a plausible support estimate.",
        "- If `NOT_SATURATED` persists at max_dim, only a lower bound is available.",
        "",
        "## Processed logical files",
        "",
    ]
    for dataset in datasets:
        lines.append(f"- `{dataset.logical_id}` kept=`{dataset.kept_path}` duplicates={len(dataset.duplicate_paths)}")
    lines.extend(["", "## Final results", ""])
    for row in file_summaries:
        lines.append(
            f"- `{row['logical_id']}` status={row['final_status']} final_dim={row['final_dim']} final_W95_ps={row['final_W95_ps']} covered={row['final_covered']}"
        )
    (run_paths["root"] / "README.md").write_text("\n".join(lines), encoding="utf-8")


def log_message(log_path: Path, text: str) -> None:
    """Append a line to the run log."""
    with log_path.open("a", encoding="utf-8") as f:
        f.write(text.rstrip() + "\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    ap = argparse.ArgumentParser(description="Direct P_plus extraction / auto-dim pilot for Type0ppln JTI data.")
    ap.add_argument("--data-root", default=DEFAULT_DATA_ROOT)
    ap.add_argument("--channels", nargs=2, type=int, default=[1, 3])
    ap.add_argument("--pairing-rule", choices=["nearest", "greedy_unique"], default="nearest")
    ap.add_argument("--coincidence-window-ps", type=int, default=200)
    ap.add_argument("--bin-width-ps", type=int, default=100)
    ap.add_argument("--dims", default=None)
    ap.add_argument("--auto-dim", action="store_true", default=True)
    ap.add_argument("--auto-stop", action="store_true")
    ap.add_argument("--start-dim", type=int, default=32)
    ap.add_argument("--max-dim", type=int, default=65536)
    ap.add_argument("--dim-growth", type=int, default=2)
    ap.add_argument("--jobs", type=int, default=15)
    ap.add_argument("--dense-profile-max-bins", type=int, default=5_000_000)
    ap.add_argument("--continue-from-existing", default=None)
    ap.add_argument("--min-next-dim", type=int, default=None)
    ap.add_argument("--high-dim-max-dim", type=int, default=None)
    ap.add_argument("--profile-storage", choices=["auto", "dense", "sparse"], default="auto")
    ap.add_argument("--diag-band-bins", type=int, default=1)
    ap.add_argument("--edge-bins-fraction", type=float, default=0.05)
    ap.add_argument("--edge-fraction-threshold", type=float, default=0.05)
    ap.add_argument("--stop-width-ratio", type=float, default=0.7)
    ap.add_argument("--stop-width-change", type=float, default=0.05)
    ap.add_argument("--dedupe-ttbin", action="store_true", default=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--output-dir", default=None)
    return ap.parse_args(argv)


def dims_from_args(args: argparse.Namespace) -> tuple[int, ...]:
    """Resolve the requested dim sequence."""
    if args.dims:
        return tuple(int(part.strip()) for part in str(args.dims).split(",") if part.strip())
    dims: list[int] = []
    current = int(args.min_next_dim) if args.min_next_dim is not None else int(args.start_dim)
    max_dim = int(args.high_dim_max_dim) if args.high_dim_max_dim is not None else int(args.max_dim)
    while current <= max_dim:
        dims.append(int(current))
        current *= int(args.dim_growth)
    if not dims:
        raise SystemExit("no dims requested")
    return tuple(dims)


def make_config(args: argparse.Namespace) -> Config:
    """Resolve paths and normalized settings."""
    data_root = normalize_path(args.data_root).resolve()
    output_dir = planned_output_dir(data_root, args.output_dir)
    dims = dims_from_args(args)
    auto_dim = bool(args.auto_dim or args.dims is None)
    return Config(
        data_root=data_root,
        channels=(int(args.channels[0]), int(args.channels[1])),
        pairing_rule=str(args.pairing_rule),
        coincidence_window_ps=int(args.coincidence_window_ps),
        bin_width_ps=int(args.bin_width_ps),
        dims=dims,
        auto_dim=auto_dim,
        auto_stop=bool(args.auto_stop),
        diag_band_bins=int(args.diag_band_bins),
        edge_bins_fraction=float(args.edge_bins_fraction),
        edge_fraction_threshold=float(args.edge_fraction_threshold),
        stop_width_ratio=float(args.stop_width_ratio),
        stop_width_change=float(args.stop_width_change),
        dedupe_ttbin=bool(args.dedupe_ttbin),
        output_dir=output_dir,
        dims_explicit=bool(args.dims),
        jobs=max(1, int(args.jobs)),
        dense_profile_max_bins=int(args.dense_profile_max_bins),
        continue_from_existing=normalize_path(args.continue_from_existing).resolve() if args.continue_from_existing else None,
        min_next_dim=args.min_next_dim,
        high_dim_max_dim=args.high_dim_max_dim,
        profile_storage=str(args.profile_storage),
    )


def dry_run(cfg: Config, ttbin_files: list[Path], datasets: list[LogicalDataset], dedupe_rows: list[dict[str, Any]]) -> int:
    """Print a dry-run preview without heavy processing."""
    preview = {
        "dry_run": True,
        "data_root": str(cfg.data_root),
        "data_root_exists": cfg.data_root.exists(),
        "n_ttbin_files": len(ttbin_files),
        "ttbin_files": [str(p) for p in ttbin_files],
        "dedupe_preview": dedupe_rows,
        "logical_datasets": [
            {
                "logical_id": d.logical_id,
                "kept_path": str(d.kept_path),
                "duplicate_paths": [str(p) for p in d.duplicate_paths],
                "dedupe_method": d.dedupe_method,
            }
            for d in datasets
        ],
        "imports": {
            "load_tags": callable(load_tags),
            "nearest_pairs": callable(nearest_pairs),
            "greedy_unique_pairs": callable(greedy_unique_pairs),
            "_time_tags_to_bins": callable(_time_tags_to_bins),
            "_iter_frame_origins": callable(_iter_frame_origins),
            "_select_best_frame_origin": callable(_select_best_frame_origin),
        },
        "defaults": {
            "channels": list(cfg.channels),
            "pairing_rule": cfg.pairing_rule,
            "coincidence_window_ps": cfg.coincidence_window_ps,
            "bin_width_ps": cfg.bin_width_ps,
            "dims": list(cfg.dims),
            "diag_band_bins": cfg.diag_band_bins,
            "jobs": cfg.jobs,
            "dense_profile_max_bins": cfg.dense_profile_max_bins,
            "profile_storage": cfg.profile_storage,
        },
        "high_dim_estimate": {
            "continue_from_existing": str(cfg.continue_from_existing) if cfg.continue_from_existing else None,
            "continue_cache_exists": bool(cfg.continue_from_existing and (cfg.continue_from_existing / "tag_cache").exists()),
            "max_dense_profile_bytes": int(cfg.dense_profile_max_bins * 2 * 8),
            "planned_dim_count": len(cfg.dims),
        },
        "planned_output_dir": str(cfg.output_dir),
    }
    print(json.dumps(preview, indent=2, ensure_ascii=False))
    return 0 if cfg.data_root.exists() else 2


def main(argv: list[str] | None = None) -> int:
    """Run the direct P_plus auto-dim analysis."""
    args = parse_args(argv)
    cfg = make_config(args)
    ttbin_files = find_ttbin_files(cfg.data_root) if cfg.data_root.exists() else []
    if not cfg.data_root.exists():
        if args.dry_run:
            print(json.dumps({"status": "DATA_ROOT_NOT_FOUND", "data_root": str(cfg.data_root)}, ensure_ascii=False, indent=2))
            return 2
        raise SystemExit(f"data root not found: {cfg.data_root}")
    if not ttbin_files:
        if args.dry_run:
            print(json.dumps({"status": "NO_TTBIN_FOUND", "data_root": str(cfg.data_root)}, ensure_ascii=False, indent=2))
            return 3
        raise SystemExit(f"no TTBIN files found under {cfg.data_root}")

    if cfg.dedupe_ttbin:
        datasets, dedupe_rows = dedupe_datasets(ttbin_files, cfg.channels)
    else:
        datasets = [
            LogicalDataset(
                logical_id=f"{idx:03d}_{safe_stem(path.stem)}",
                kept_path=path,
                duplicate_paths=(),
                dedupe_method="disabled",
                total_events=None,
                selected_channel_counts={},
                filewriter_filename=None,
            )
            for idx, path in enumerate(ttbin_files)
        ]
        dedupe_rows = [
            {
                "logical_id": d.logical_id,
                "kept_path": str(d.kept_path),
                "duplicate_paths": "",
                "dedupe_method": d.dedupe_method,
                "total_events": "",
                "selected_channel_counts": "",
                "status": DEFAULT_STATUS_OK,
                "error": "",
                "suggestion": "",
            }
            for d in datasets
        ]

    if args.dry_run:
        return dry_run(cfg, ttbin_files, datasets, dedupe_rows)

    cfg.output_dir.mkdir(parents=True, exist_ok=False)
    run_paths = {
        "root": cfg.output_dir,
        "profiles": cfg.output_dir / "profiles",
        "plots": cfg.output_dir / "plots",
        "logs": cfg.output_dir / "logs",
        "cache": cfg.output_dir / "tag_cache",
    }
    for path in run_paths.values():
        path.mkdir(parents=True, exist_ok=True)
    log_path = run_paths["logs"] / "run.log"
    save_run_config(cfg.output_dir / "run_config.json", cfg, ttbin_files, datasets)
    write_csv(cfg.output_dir / "dedupe_report.csv", DEDUPE_FIELDS, dedupe_rows)

    previous_rows, previous_decisions, previous_by_logical = previous_context(cfg.continue_from_existing)
    all_rows: list[dict[str, Any]] = list(previous_rows)
    all_decisions: list[dict[str, Any]] = list(previous_decisions)
    file_summaries: list[dict[str, Any]] = []
    all_checks: list[dict[str, Any]] = []

    log_message(log_path, f"output_dir={cfg.output_dir}")
    for dataset in datasets:
        log_message(log_path, f"processing {dataset.logical_id} path={dataset.kept_path}")
        rows, decisions, file_summary, checks = process_dataset(dataset, cfg, run_paths, previous_by_logical.get(dataset.logical_id))
        all_rows.extend(rows)
        all_decisions.extend(decisions)
        file_summaries.append(file_summary)
        all_checks.extend(checks)
        overlay_and_summary_plots(dataset.logical_id, rows, run_paths)

    write_csv(cfg.output_dir / "pplus_auto_dim_summary.csv", SUMMARY_FIELDS, all_rows)
    write_csv(cfg.output_dir / "auto_dim_decision.csv", AUTO_DECISION_FIELDS, all_decisions)
    write_csv(cfg.output_dir / "file_summary.csv", FILE_SUMMARY_FIELDS, file_summaries)
    if all_checks:
        write_csv(cfg.output_dir / "pplus_dense_vs_direct_check.csv", CHECK_FIELDS, all_checks)
    write_readme(cfg, datasets, file_summaries, run_paths)

    print(json.dumps({"output_dir": str(cfg.output_dir), "logical_datasets": len(datasets)}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
