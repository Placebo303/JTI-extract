#!/usr/bin/env python3
"""FPC single-filter multiline delay and centered-JTI analysis."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jti_extract.cli.extract import (
    _frame_local_bins,
    _plot_png,
    _save_csv_matrix,
    _time_tags_to_bins,
    compute_alignment_centered_display_jti,
    compute_centered_line_jti,
    compute_multiline_raw_offset_jti,
    compute_jti_diagnostics,
    diagonal_coincidence_profile,
    iter_pair_chunks_centered,
)
from jti_extract.cli.tdc_layer_scan import Tags, load_tags


DEFAULT_DATA_ROOT = r"D:\Data\Raw Data\Time Tags\Time Tags"
DEFAULT_OUT = "results/fpc_multiline_analysis"


@dataclass(frozen=True)
class Dataset:
    angle: str
    ttbin: Path


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


def _write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def _angle_slug(angle: str) -> str:
    cleaned = angle.replace("°", "deg").replace(" ", "_")
    cleaned = re.sub(r"[^A-Za-z0-9_+-]+", "", cleaned)
    return cleaned or "unknown"


def discover_default_datasets(data_root: Path) -> list[Dataset]:
    datasets: list[Dataset] = []
    for path in sorted(data_root.glob("Type II FPC*Single Filter_*.1.ttbin")):
        match = re.search(r"FPC\s+(.+?)\s+Single", path.name)
        angle = match.group(1).strip() if match else path.stem
        datasets.append(Dataset(angle=angle, ttbin=path))
    if not datasets:
        raise RuntimeError(f"no default FPC .1.ttbin files found under {data_root}")
    return datasets


# Use core version from jti_extract.cli.extract
_iter_pair_chunks_centered = iter_pair_chunks_centered


def compute_delay_histogram_centered(
    t_a: np.ndarray,
    t_b: np.ndarray,
    *,
    window_ps: int,
    bin_width_ps: int,
) -> tuple[np.ndarray, np.ndarray, int]:
    edges = np.arange(-int(window_ps), int(window_ps) + int(bin_width_ps), int(bin_width_ps), dtype=np.float64)
    counts = np.zeros(edges.size - 1, dtype=np.int64)
    total_pairs = 0
    for _, _, deltas in _iter_pair_chunks_centered(t_a, t_b, center_ps=0, half_window_ps=int(window_ps)):
        hist, _ = np.histogram(deltas.astype(np.float64), bins=edges)
        counts += hist.astype(np.int64)
        total_pairs += int(deltas.size)
    return counts, edges, total_pairs


def save_delay_csv(path: Path, counts: np.ndarray, edges: np.ndarray) -> None:
    rows = []
    for i, count in enumerate(np.asarray(counts, dtype=np.int64)):
        center = float((edges[i] + edges[i + 1]) * 0.5)
        rows.append({"delay_ps": int(round(center)), "counts": int(count)})
    _write_csv(path, ["delay_ps", "counts"], rows)


def plot_delay(path: Path, counts: np.ndarray, edges: np.ndarray, peaks: list[dict[str, Any]], *, title: str) -> None:
    import matplotlib.pyplot as plt

    centers = (edges[:-1] + edges[1:]) * 0.5
    fig, ax = plt.subplots(figsize=(10.5, 5.0), dpi=160)
    ax.plot(centers / 1000.0, counts, linewidth=0.8)
    ax.axvline(0.0, color="tab:red", linestyle="--", linewidth=0.8, alpha=0.6)
    for peak in peaks[:12]:
        x = float(peak["delay_ps"]) / 1000.0
        ax.axvline(x, color="tab:orange", linewidth=0.6, alpha=0.45)
    ax.set_xlabel("Inter-channel delay tau = t_B - t_A (ns)")
    ax.set_ylabel("Counts")
    ax.set_title(title)
    ax.grid(True, linewidth=0.35, alpha=0.35)
    fig.tight_layout()
    fig.savefig(str(path))
    plt.close(fig)


def smooth_counts(counts: np.ndarray, bins: int) -> np.ndarray:
    bins = int(max(1, bins))
    if bins <= 1:
        return np.asarray(counts, dtype=np.float64)
    kernel = np.ones(bins, dtype=np.float64) / float(bins)
    return np.convolve(np.asarray(counts, dtype=np.float64), kernel, mode="same")


def find_delay_peaks(
    counts: np.ndarray,
    edges: np.ndarray,
    *,
    smooth_bins: int,
    min_prominence_fraction: float,
    min_distance_ps: int,
    max_peaks: int,
) -> list[dict[str, Any]]:
    y = smooth_counts(counts, smooth_bins)
    if y.size < 3 or float(np.max(y)) <= 0.0:
        return []
    centers = (edges[:-1] + edges[1:]) * 0.5
    bin_width = float(edges[1] - edges[0])
    distance_bins = max(1, int(round(float(min_distance_ps) / bin_width)))
    threshold = float(np.max(y)) * float(min_prominence_fraction)
    candidates: list[tuple[float, int]] = []
    for idx in range(1, y.size - 1):
        if y[idx] >= threshold and y[idx] >= y[idx - 1] and y[idx] >= y[idx + 1]:
            local_left = max(0, idx - distance_bins)
            local_right = min(y.size, idx + distance_bins + 1)
            baseline = max(float(np.min(y[local_left : idx + 1])), float(np.min(y[idx:local_right])))
            prominence = float(y[idx] - baseline)
            if prominence >= threshold * 0.25:
                candidates.append((prominence, idx))
    candidates.sort(reverse=True)
    refined_candidates: list[tuple[float, int]] = []
    refine_radius = max(1, distance_bins // 2)
    for prominence, idx in candidates:
        lo = max(0, idx - refine_radius)
        hi = min(counts.size, idx + refine_radius + 1)
        if hi <= lo:
            refined_candidates.append((prominence, idx))
            continue
        # Report the physical line at the raw-count maximum near the smoothed peak.
        raw_idx = int(lo + np.argmax(counts[lo:hi]))
        refined_candidates.append((prominence, raw_idx))
    refined_candidates.sort(reverse=True)

    selected: list[int] = []
    for _, idx in refined_candidates:
        if all(abs(idx - prev) >= distance_bins for prev in selected):
            selected.append(idx)
        if len(selected) >= int(max_peaks):
            break
    selected.sort(key=lambda i: centers[i])
    main_count = max(float(counts[i]) for i in selected) if selected else 0.0
    rows: list[dict[str, Any]] = []
    for rank, idx in enumerate(sorted(selected, key=lambda i: counts[i], reverse=True), start=1):
        rows.append(
            {
                "rank_by_count": int(rank),
                "delay_ps": int(round(float(centers[idx]))),
                "counts": int(counts[idx]),
                "smoothed_counts": float(y[idx]),
                "relative_to_main": float(counts[idx] / main_count) if main_count > 0 else math.nan,
                "bin_index": int(idx),
            }
        )
    rows.sort(key=lambda r: int(r["delay_ps"]))
    for i, row in enumerate(rows):
        prev_delay = int(rows[i - 1]["delay_ps"]) if i else None
        next_delay = int(rows[i + 1]["delay_ps"]) if i + 1 < len(rows) else None
        row["spacing_from_previous_ps"] = "" if prev_delay is None else int(row["delay_ps"]) - prev_delay
        row["spacing_to_next_ps"] = "" if next_delay is None else next_delay - int(row["delay_ps"])
    return rows


# Use core version from jti_extract.cli.extract
jti_for_centered_line = compute_centered_line_jti


# Use core version from jti_extract.cli.extract
jti_for_peak_union_raw_offsets = compute_multiline_raw_offset_jti


def save_jti_outputs(
    out_dir: Path,
    counts: np.ndarray,
    *,
    stem: str,
    dim: int,
    bin_width_ps: int,
    frame_origin_ps: float,
    dataset: Dataset,
    tags: Tags,
    line_meta: dict[str, Any],
    save_plot: bool,
    tau_center_required: bool = True,
    pairing_mode: str = "all_pairs_centered_line_window",
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    counts_csv = out_dir / f"{stem}.counts.csv"
    npz_path = out_dir / f"{stem}.npz"
    png_path = out_dir / f"{stem}.png"
    diag_csv = out_dir / f"{stem}.diagonal_profile.csv"
    meta_path = out_dir / f"{stem}.meta.json"
    _save_csv_matrix(counts_csv, counts)
    np.savez_compressed(
        str(npz_path),
        jti_counts=counts.astype(np.float64),
        dimension=np.int64(int(dim)),
        bin_width_ps=np.int64(int(bin_width_ps)),
        frame_origin_ps=np.float64(float(frame_origin_ps)),
        tau_center_ps=np.int64(int(line_meta.get("tau_center_ps", 0))),
        line_half_window_ps=np.int64(int(line_meta["line_half_window_ps"])),
    )
    profile = diagonal_coincidence_profile(counts, band_bins=1)
    _write_csv(
        diag_csv,
        ["bin_index", "time_ps", "coincidence_counts"],
        [
            {"bin_index": int(i), "time_ps": int(i) * int(bin_width_ps), "coincidence_counts": float(v)}
            for i, v in enumerate(profile)
        ],
    )
    if save_plot:
        if tau_center_required:
            title = f"{dataset.angle} tau={line_meta.get('tau_center_ps', 0)} ps centered JTI"
        else:
            title = f"{dataset.angle} raw-offset multiline JTI"
        _plot_png(
            png_path,
            counts,
            title=title,
        )
    diagnostics = compute_jti_diagnostics(counts)
    meta = {
        "dataset": {"angle": dataset.angle, "ttbin": str(dataset.ttbin)},
        "dimension": int(dim),
        "bin_width_ps": int(bin_width_ps),
        "frame_duration_ps": float(int(dim) * int(bin_width_ps)),
        "frame_origin_ps": float(frame_origin_ps),
        "pairing_mode": str(pairing_mode),
        "tau_center_ps": int(line_meta.get("tau_center_ps", 0)) if tau_center_required else None,
        "tau_centers_ps": line_meta.get("tau_centers_ps"),
        "line_half_window_ps": int(line_meta["line_half_window_ps"]),
        "n_pairs": int(line_meta["n_pairs"]),
        "events": {"channel_a": int(tags.t_a.size), "channel_b": int(tags.t_b.size)},
        "pairs_meta": line_meta,
        "diagnostics": diagnostics,
        "outputs": {
            "counts_csv": str(counts_csv),
            "npz": str(npz_path),
            "png": str(png_path) if save_plot else None,
            "diagonal_profile_csv": str(diag_csv),
            "meta": str(meta_path),
        },
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    return meta


def plot_angle_comparison(path: Path, angle_rows: list[dict[str, Any]]) -> None:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10.5, 5.2), dpi=160)
    for row in angle_rows:
        centers = np.asarray(row["centers_ps"], dtype=np.float64)
        counts = np.asarray(row["counts"], dtype=np.float64)
        denom = float(np.max(counts)) if counts.size and float(np.max(counts)) > 0 else 1.0
        ax.plot(centers / 1000.0, counts / denom, linewidth=0.8, label=str(row["angle"]))
    ax.axvline(0.0, color="tab:red", linestyle="--", linewidth=0.8, alpha=0.5)
    ax.set_xlabel("Inter-channel delay tau = t_B - t_A (ns)")
    ax.set_ylabel("Normalized counts")
    ax.set_title("FPC P_minus delay comparison")
    ax.legend()
    ax.grid(True, linewidth=0.35, alpha=0.35)
    fig.tight_layout()
    fig.savefig(str(path))
    plt.close(fig)


def plot_diagonal_band_heatmap(
    path: Path,
    counts: np.ndarray,
    *,
    bin_width_ps: int,
    half_width_bins: int,
    title: str,
) -> None:
    import matplotlib.pyplot as plt

    mat = np.asarray(counts, dtype=np.float64)
    dim = int(mat.shape[0])
    offsets = np.arange(-int(half_width_bins), int(half_width_bins) + 1, dtype=int)
    band = np.zeros((offsets.size, dim), dtype=np.float64)
    x = np.arange(dim, dtype=int)
    for row, offset in enumerate(offsets):
        y = x + int(offset)
        keep = (y >= 0) & (y < dim)
        band[row, keep] = mat[x[keep], y[keep]]

    fig, ax = plt.subplots(figsize=(10.0, 5.0), dpi=180)
    vmax = float(np.percentile(band[band > 0], 99.5)) if np.any(band > 0) else 1.0
    image = ax.imshow(
        band,
        origin="lower",
        aspect="auto",
        interpolation="nearest",
        cmap="viridis",
        vmin=0.0,
        vmax=max(1.0, vmax),
        extent=[
            0,
            dim,
            float(offsets[0] * int(bin_width_ps)),
            float(offsets[-1] * int(bin_width_ps)),
        ],
    )
    ax.axhline(0.0, color="white", linewidth=0.8, alpha=0.55)
    ax.set_xlabel("Signal time-bin index")
    ax.set_ylabel("Idler - signal offset (ps)")
    ax.set_title(title)
    cbar = fig.colorbar(image, ax=ax)
    cbar.set_label("Counts")
    fig.tight_layout()
    fig.savefig(str(path))
    plt.close(fig)


def _ascii_angle_label(angle: str) -> str:
    match = re.search(r"[-+]?\d+", str(angle))
    return f"{match.group(0)} deg" if match else str(angle).encode("ascii", "ignore").decode("ascii")


def _label_for_index(idx: int) -> str:
    letters = "abcdefghijklmnopqrstuvwxyz"
    if idx < len(letters):
        return f"{letters[idx]}*"
    return f"{idx + 1}*"


def save_publication_counts_csv(path: Path, counts: np.ndarray) -> None:
    _save_csv_matrix(path, np.asarray(counts, dtype=np.float64))


def plot_publication_jti(
    path: Path,
    counts: np.ndarray,
    *,
    angle: str,
    delay_counts: np.ndarray,
    delay_edges: np.ndarray,
    peaks: list[dict[str, Any]],
    tau_reference_ps: int,
    bin_width_ps: int,
    annotate_lines: int,
    gamma: float,
    vmax_percentile: float,
) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.colors import PowerNorm
    from mpl_toolkits.axes_grid1.inset_locator import inset_axes

    mat = np.asarray(counts, dtype=np.float64)
    dim = int(mat.shape[0])
    positive = mat[mat > 0]
    vmax = float(np.percentile(positive, float(vmax_percentile))) if positive.size else 1.0
    vmax = max(1.0, vmax)

    fig, ax = plt.subplots(figsize=(7.2, 6.1), dpi=220)
    image = ax.imshow(
        mat.T,
        origin="lower",
        interpolation="nearest",
        cmap="viridis",
        norm=PowerNorm(gamma=float(gamma), vmin=0.0, vmax=vmax),
        extent=[0, dim - 1, 0, dim - 1],
        aspect="equal",
    )
    ax.set_xlabel("Signal time-bin number")
    ax.set_ylabel("Idler time-bin number")
    ax.set_title(f"{_ascii_angle_label(angle)} FPC single-filter JTI")
    cbar = fig.colorbar(image, ax=ax, fraction=0.047, pad=0.035)
    cbar.set_label("Coincidence counts")

    strongest = sorted(peaks, key=lambda r: int(r.get("counts", 0)), reverse=True)[: int(annotate_lines)]
    for idx, peak in enumerate(strongest):
        tau = int(peak["delay_ps"])
        offset_bins = int(round((float(tau) - float(tau_reference_ps)) / float(bin_width_ps)))
        x = int(round(dim * (0.42 + 0.045 * (idx % 3))))
        y = x + offset_bins
        if y < 8:
            x = min(dim - 12, x + (8 - y))
            y = x + offset_bins
        if y > dim - 8:
            x = max(8, x - (y - (dim - 8)))
            y = x + offset_bins
        if 0 <= y < dim:
            ax.text(
                x,
                y,
                _label_for_index(idx),
                color="red",
                fontsize=9,
                fontweight="bold",
                ha="center",
                va="center",
            )

    inset = inset_axes(ax, width="34%", height="28%", loc="upper left", borderpad=1.0)
    centers_ns = ((delay_edges[:-1] + delay_edges[1:]) * 0.5) / 1000.0
    dcounts = np.asarray(delay_counts, dtype=np.float64)
    denom = float(np.max(dcounts)) if dcounts.size and float(np.max(dcounts)) > 0 else 1.0
    inset.plot(centers_ns, dcounts / denom, color="black", linewidth=0.75)
    for idx, peak in enumerate(strongest):
        tau_ns = float(peak["delay_ps"]) / 1000.0
        y = float(peak["counts"]) / denom
        inset.plot([tau_ns], [y], marker="o", markersize=2.8, color="red")
        inset.text(tau_ns + 0.025, min(1.0, y + 0.04), _label_for_index(idx), color="red", fontsize=7, fontweight="bold")
    inset.set_xlim(float(np.min(centers_ns)), float(np.max(centers_ns)))
    inset.set_ylim(0, 1.05)
    inset.set_xlabel("tau (ns)", fontsize=7)
    inset.set_ylabel("norm. counts", fontsize=7)
    inset.tick_params(axis="both", labelsize=7, length=2)
    inset.grid(True, linewidth=0.25, alpha=0.3)

    fig.tight_layout()
    fig.savefig(str(path))
    plt.close(fig)


def save_publication_outputs(
    out_dir: Path,
    *,
    dataset: Dataset,
    tags: Tags,
    peaks: list[dict[str, Any]],
    delay_counts: np.ndarray,
    delay_edges: np.ndarray,
    dim: int,
    bin_width_ps: int,
    half_window_ps: int,
    frame_origin_ps: float,
    annotate_lines: int,
    gamma: float,
    vmax_percentile: float,
) -> dict[str, Any] | None:
    if not peaks:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    tau_centers = sorted(int(p["delay_ps"]) for p in peaks)
    tau_reference = int(min(tau_centers))
    counts, meta = jti_for_peak_union_raw_offsets(
        tags.t_a,
        tags.t_b,
        tau_centers_ps=tau_centers,
        tau_reference_ps=tau_reference,
        half_window_ps=int(half_window_ps),
        dim=int(dim),
        bin_width_ps=int(bin_width_ps),
        frame_origin_ps=float(frame_origin_ps),
        require_same_frame=True,
    )
    counts_csv = out_dir / "publication_jti.counts.csv"
    png_path = out_dir / "publication_jti.png"
    meta_path = out_dir / "publication_jti.meta.json"
    save_publication_counts_csv(counts_csv, counts)
    plot_publication_jti(
        png_path,
        counts,
        angle=dataset.angle,
        delay_counts=delay_counts,
        delay_edges=delay_edges,
        peaks=peaks,
        tau_reference_ps=tau_reference,
        bin_width_ps=int(bin_width_ps),
        annotate_lines=int(annotate_lines),
        gamma=float(gamma),
        vmax_percentile=float(vmax_percentile),
    )
    payload = {
        "dataset": {"angle": dataset.angle, "ttbin": str(dataset.ttbin)},
        "dimension": int(dim),
        "bin_width_ps": int(bin_width_ps),
        "frame_duration_ps": float(int(dim) * int(bin_width_ps)),
        "frame_origin_ps": float(frame_origin_ps),
        "pairing_mode": "publication_peak_union_raw_offset_reference",
        "tau_reference_ps": int(tau_reference),
        "tau_centers_ps": tau_centers,
        "sideband_half_window_ps": int(half_window_ps),
        "n_pairs": int(meta["n_pairs"]),
        "events": {"channel_a": int(tags.t_a.size), "channel_b": int(tags.t_b.size)},
        "diagnostics": compute_jti_diagnostics(counts),
        "display": {
            "norm": "PowerNorm",
            "gamma": float(gamma),
            "vmax_percentile": float(vmax_percentile),
            "annotate_strongest_lines": int(annotate_lines),
        },
        "peaks": peaks,
        "pairs_meta": meta,
        "outputs": {
            "png": str(png_path),
            "counts_csv": str(counts_csv),
            "meta": str(meta_path),
        },
    }
    meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    return payload


def expand_diagonal_for_display(counts: np.ndarray) -> np.ndarray:
    """Fill the next pixel along each diagonal for display-only continuity."""
    mat = np.asarray(counts, dtype=np.float64)
    expanded = mat.copy()
    if mat.shape[0] > 1 and mat.shape[1] > 1:
        expanded[1:, 1:] += mat[:-1, :-1]
    return expanded


def _read_alignment_outputs(alignment_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    summary_path = alignment_dir / "alignment_summary.json"
    offsets_path = alignment_dir / "selected_peak_offsets.csv"
    if not summary_path.exists():
        raise FileNotFoundError(f"alignment summary not found: {summary_path}")
    if not offsets_path.exists():
        raise FileNotFoundError(f"selected peak offsets not found: {offsets_path}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    with offsets_path.open("r", newline="", encoding="utf-8-sig") as f:
        for raw in csv.DictReader(f):
            row = dict(raw)
            row["peak_id"] = str(row.get("peak_id", f"p{len(rows)}"))
            for key in [
                "tau_rel_ps",
                "chosen_bw_ps",
                "alignment_error_ps",
                "norm_height",
                "fwhm_ps",
                "fwhm_bins",
                "half_width_bins",
            ]:
                if row.get(key, "") != "":
                    row[key] = float(row[key])
            for key in ["diagonal_offset_bin", "rounded_left_offset_bin", "rounded_right_offset_bin"]:
                if row.get(key, "") != "":
                    row[key] = int(round(float(row[key])))
            rows.append(row)
    rows.sort(key=lambda r: (float(r.get("tau_rel_ps", 0.0)), str(r.get("peak_id", ""))))
    return summary, rows


def _ensure_alignment_outputs(
    args: argparse.Namespace,
    *,
    angle_dir: Path,
    delay_csv: Path,
) -> Path:
    requested = str(args.publication_use_alignment).strip()
    if requested and requested.lower() != "auto":
        return Path(requested)

    alignment_dir = angle_dir / "delay_alignment_auto"
    summary_path = alignment_dir / "alignment_summary.json"
    offsets_path = alignment_dir / "selected_peak_offsets.csv"
    if summary_path.exists() and offsets_path.exists():
        return alignment_dir

    tool_path = ROOT / "tools" / "jti_delay_alignment.py"
    if not tool_path.exists():
        raise FileNotFoundError(f"alignment diagnostic tool not found: {tool_path}")
    cmd = [
        sys.executable,
        str(tool_path),
        "--delay-csv",
        str(delay_csv),
        "--outdir",
        str(alignment_dir),
        "--delay-col",
        "auto",
        "--counts-col",
        "auto",
        "--tau0-ps",
        "auto",
        "--candidate-bw-ps",
        str(args.publication_alignment_candidate_bw_ps),
        "--chosen-bw-ps",
        "auto",
        "--peak-side",
        str(args.publication_alignment_peak_side),
    ]
    subprocess.run(cmd, cwd=str(ROOT), check=True)
    return alignment_dir


# Use core version from jti_extract.cli.extract
jti_for_alignment_centered_display = compute_alignment_centered_display_jti


def plot_centered_publication_jti(
    path: Path,
    counts: np.ndarray,
    *,
    angle: str,
    delay_counts: np.ndarray,
    delay_edges: np.ndarray,
    tau0_ps: float,
    peaks: list[dict[str, Any]],
    annotate_lines: int,
    gamma: float,
    vmax_percentile: float,
    title_suffix: str = "centered-bright multiline JTI",
) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.colors import PowerNorm
    from mpl_toolkits.axes_grid1.inset_locator import inset_axes

    mat = np.asarray(counts, dtype=np.float64)
    dim = int(mat.shape[0])
    positive = mat[mat > 0]
    vmax = float(np.percentile(positive, float(vmax_percentile))) if positive.size else 1.0
    vmax = max(1.0, vmax)

    fig, ax = plt.subplots(figsize=(7.2, 6.1), dpi=220)
    image = ax.imshow(
        mat.T,
        origin="lower",
        interpolation="nearest",
        cmap="viridis",
        norm=PowerNorm(gamma=float(gamma), vmin=0.0, vmax=vmax),
        extent=[0, dim - 1, 0, dim - 1],
        aspect="equal",
    )
    ax.set_xlabel("Signal time-bin number")
    ax.set_ylabel("Idler time-bin number")
    ax.set_title(f"{_ascii_angle_label(angle)} {title_suffix}")
    cbar = fig.colorbar(image, ax=ax, fraction=0.047, pad=0.035)
    cbar.set_label("Coincidence counts")

    strongest = sorted(peaks, key=lambda r: float(r.get("norm_height", 0.0)), reverse=True)[: int(annotate_lines)]
    for idx, peak in enumerate(strongest):
        offset = int(peak["display_offset_bin"])
        x = int(round(dim * (0.34 + 0.055 * (idx % 4))))
        y = x + offset
        if y < 7:
            x = min(dim - 10, x + (7 - y))
            y = x + offset
        if y > dim - 7:
            x = max(7, x - (y - (dim - 7)))
            y = x + offset
        if 0 <= y < dim:
            ax.text(
                x,
                y,
                str(peak.get("peak_id", f"p{idx}")),
                color="red",
                fontsize=8,
                fontweight="bold",
                ha="center",
                va="center",
            )

    inset = inset_axes(ax, width="34%", height="28%", loc="upper left", borderpad=1.0)
    centers_ps = (delay_edges[:-1] + delay_edges[1:]) * 0.5
    centers_ns = (centers_ps - float(tau0_ps)) / 1000.0
    dcounts = np.asarray(delay_counts, dtype=np.float64)
    baseline = float(np.percentile(dcounts, 20.0)) if dcounts.size else 0.0
    bg_sub = np.maximum(dcounts - baseline, 0.0)
    denom = float(np.max(bg_sub)) if bg_sub.size and float(np.max(bg_sub)) > 0 else 1.0
    inset.plot(centers_ns, bg_sub / denom, color="black", linewidth=0.75)
    for peak in strongest:
        tau_rel_ns = float(peak["tau_rel_ps"]) / 1000.0
        idx = int(np.argmin(np.abs(centers_ns - tau_rel_ns))) if centers_ns.size else 0
        y = float(bg_sub[idx] / denom) if bg_sub.size else float(peak.get("norm_height", 0.0))
        inset.plot([tau_rel_ns], [y], marker="o", markersize=2.8, color="red")
        inset.text(
            tau_rel_ns + 0.025,
            min(1.0, y + 0.04),
            str(peak.get("peak_id", "")),
            color="red",
            fontsize=7,
            fontweight="bold",
        )
    inset.axvline(0.0, color="red", linewidth=0.6, alpha=0.6)
    inset.set_xlim(float(np.min(centers_ns)), float(np.max(centers_ns)))
    inset.set_ylim(0, 1.05)
    inset.set_xlabel("tau_rel (ns)", fontsize=7)
    inset.set_ylabel("norm. counts", fontsize=7)
    inset.tick_params(axis="both", labelsize=7, length=2)
    inset.grid(True, linewidth=0.25, alpha=0.3)

    fig.tight_layout()
    fig.savefig(str(path))
    plt.close(fig)


def save_centered_publication_outputs(
    out_dir: Path,
    *,
    dataset: Dataset,
    tags: Tags,
    delay_counts: np.ndarray,
    delay_edges: np.ndarray,
    alignment_dir: Path,
    dim: int,
    half_window_ps: int,
    frame_origin_ps: float,
    center_offset_bin: int,
    annotate_lines: int,
    gamma: float,
    vmax_percentile: float,
) -> dict[str, Any] | None:
    summary, selected_offsets = _read_alignment_outputs(alignment_dir)
    if not selected_offsets:
        return None
    tau0_ps = float(summary["tau0_ps"])
    chosen_bw_ps = int(round(float(summary["chosen_bw_ps"])))
    out_dir.mkdir(parents=True, exist_ok=True)
    counts, peak_meta = jti_for_alignment_centered_display(
        tags.t_a,
        tags.t_b,
        selected_offsets=selected_offsets,
        tau0_ps=tau0_ps,
        center_offset_bin=int(center_offset_bin),
        half_window_ps=int(half_window_ps),
        dim=int(dim),
        bin_width_ps=int(chosen_bw_ps),
        frame_origin_ps=float(frame_origin_ps),
    )
    counts_csv = out_dir / "centered_publication_jti.counts.csv"
    png_path = out_dir / "centered_publication_jti.png"
    meta_path = out_dir / "centered_publication_jti.meta.json"
    save_publication_counts_csv(counts_csv, counts)
    plot_centered_publication_jti(
        png_path,
        counts,
        angle=dataset.angle,
        delay_counts=delay_counts,
        delay_edges=delay_edges,
        tau0_ps=tau0_ps,
        peaks=peak_meta,
        annotate_lines=int(annotate_lines),
        gamma=float(gamma),
        vmax_percentile=float(vmax_percentile),
    )
    payload = {
        "dataset": {"angle": dataset.angle, "ttbin": str(dataset.ttbin)},
        "dimension": int(dim),
        "bin_width_ps": int(chosen_bw_ps),
        "frame_duration_ps": float(int(dim) * int(chosen_bw_ps)),
        "frame_origin_ps": float(frame_origin_ps),
        "pairing_mode": "alignment_centered_brightest_display",
        "source_alignment_dir": str(alignment_dir),
        "tau0_ps": float(tau0_ps),
        "center_offset_bin": int(center_offset_bin),
        "sideband_half_window_ps": int(half_window_ps),
        "n_pairs": int(np.sum(counts)),
        "events": {"channel_a": int(tags.t_a.size), "channel_b": int(tags.t_b.size)},
        "diagnostics": compute_jti_diagnostics(counts),
        "display": {
            "norm": "PowerNorm",
            "gamma": float(gamma),
            "vmax_percentile": float(vmax_percentile),
            "annotate_strongest_lines": int(annotate_lines),
            "note": "Diagnostic display: brightest delay peak is shifted to the visual center offset; no modulo wrap is used for idler bins.",
        },
        "alignment_summary": summary,
        "selected_peaks": peak_meta,
        "outputs": {
            "png": str(png_path),
            "counts_csv": str(counts_csv),
            "meta": str(meta_path),
        },
    }
    meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    return payload


def _single_side_offsets_from_peaks(
    peaks: list[dict[str, Any]],
    *,
    bin_width_ps: int,
    side: str,
) -> tuple[float, list[dict[str, Any]]]:
    if not peaks:
        return float("nan"), []
    strongest = max(peaks, key=lambda r: int(r.get("counts", 0)))
    tau0_ps = float(strongest["delay_ps"])
    max_counts = max(1.0, float(strongest.get("counts", 1)))
    side_norm = str(side).lower()
    rows: list[dict[str, Any]] = []
    for peak in peaks:
        tau_ps = float(peak["delay_ps"])
        tau_rel = tau_ps - tau0_ps
        if side_norm == "negative" and tau_rel > 0:
            continue
        if side_norm == "positive" and tau_rel < 0:
            continue
        offset = int(round(tau_rel / float(bin_width_ps)))
        rows.append(
            {
                "peak_id": f"p{len(rows)}",
                "tau_rel_ps": float(tau_rel),
                "chosen_bw_ps": float(bin_width_ps),
                "diagonal_offset_bin": int(offset),
                "alignment_error_ps": float(tau_rel - offset * int(bin_width_ps)),
                "norm_height": float(peak.get("counts", 0)) / max_counts,
                "fwhm_ps": float("nan"),
                "fwhm_bins": float("nan"),
                "source_delay_ps": float(tau_ps),
                "source_counts": int(peak.get("counts", 0)),
                "source_rank_by_count": int(peak.get("rank_by_count", 0)),
            }
        )
    rows.sort(key=lambda r: int(r["diagonal_offset_bin"]))
    for idx, row in enumerate(rows):
        row["peak_id"] = f"p{idx}"
    return tau0_ps, rows


def save_main_diagonal_single_side_outputs(
    out_dir: Path,
    *,
    dataset: Dataset,
    tags: Tags,
    peaks: list[dict[str, Any]],
    delay_counts: np.ndarray,
    delay_edges: np.ndarray,
    dim: int,
    bin_width_ps: int,
    half_window_ps: int,
    frame_origin_ps: float,
    side: str,
    annotate_lines: int,
    gamma: float,
    vmax_percentile: float,
) -> dict[str, Any] | None:
    tau0_ps, selected_offsets = _single_side_offsets_from_peaks(peaks, bin_width_ps=int(bin_width_ps), side=str(side))
    if not selected_offsets:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    counts, peak_meta = jti_for_alignment_centered_display(
        tags.t_a,
        tags.t_b,
        selected_offsets=selected_offsets,
        tau0_ps=float(tau0_ps),
        center_offset_bin=0,
        half_window_ps=int(half_window_ps),
        dim=int(dim),
        bin_width_ps=int(bin_width_ps),
        frame_origin_ps=float(frame_origin_ps),
    )
    for meta, row in zip(peak_meta, selected_offsets):
        meta["source_delay_ps"] = float(row.get("source_delay_ps", meta["tau_ps"]))
        meta["source_counts"] = int(row.get("source_counts", 0))
        meta["source_rank_by_count"] = int(row.get("source_rank_by_count", 0))

    counts_csv = out_dir / "centered_publication_jti.counts.csv"
    png_path = out_dir / "centered_publication_jti.png"
    display_counts_csv = out_dir / "centered_publication_jti.display_expanded.counts.csv"
    display_png_path = out_dir / "centered_publication_jti.display_expanded.png"
    meta_path = out_dir / "centered_publication_jti.meta.json"
    save_publication_counts_csv(counts_csv, counts)
    plot_centered_publication_jti(
        png_path,
        counts,
        angle=dataset.angle,
        delay_counts=delay_counts,
        delay_edges=delay_edges,
        tau0_ps=float(tau0_ps),
        peaks=peak_meta,
        annotate_lines=int(annotate_lines),
        gamma=float(gamma),
        vmax_percentile=float(vmax_percentile),
        title_suffix="main-diagonal single-side JTI",
    )
    display_counts = expand_diagonal_for_display(counts)
    save_publication_counts_csv(display_counts_csv, display_counts)
    plot_centered_publication_jti(
        display_png_path,
        display_counts,
        angle=dataset.angle,
        delay_counts=delay_counts,
        delay_edges=delay_edges,
        tau0_ps=float(tau0_ps),
        peaks=peak_meta,
        annotate_lines=int(annotate_lines),
        gamma=float(gamma),
        vmax_percentile=float(vmax_percentile),
        title_suffix="main-diagonal single-side JTI (display-expanded)",
    )
    payload = {
        "dataset": {"angle": dataset.angle, "ttbin": str(dataset.ttbin)},
        "dimension": int(dim),
        "bin_width_ps": int(bin_width_ps),
        "frame_duration_ps": float(int(dim) * int(bin_width_ps)),
        "frame_origin_ps": float(frame_origin_ps),
        "pairing_mode": "main_diagonal_single_side_delay_peaks",
        "tau0_ps": float(tau0_ps),
        "center_offset_bin": 0,
        "side": str(side),
        "sideband_half_window_ps": int(half_window_ps),
        "n_pairs": int(np.sum(counts)),
        "events": {"channel_a": int(tags.t_a.size), "channel_b": int(tags.t_b.size)},
        "diagnostics": compute_jti_diagnostics(counts),
        "display": {
            "norm": "PowerNorm",
            "gamma": float(gamma),
            "vmax_percentile": float(vmax_percentile),
            "annotate_strongest_lines": int(annotate_lines),
            "note": "Display JTI: the brightest delay peak is forced onto the main diagonal; only one side of tau_rel peaks is retained; idler bins are not wrapped.",
            "display_expansion": "Additional display-only matrix fills one neighboring pixel along each diagonal: expanded[1:,1:] += counts[:-1,:-1].",
        },
        "selected_peaks": peak_meta,
        "outputs": {
            "png": str(png_path),
            "counts_csv": str(counts_csv),
            "display_expanded_png": str(display_png_path),
            "display_expanded_counts_csv": str(display_counts_csv),
            "meta": str(meta_path),
        },
    }
    meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    return payload


def analyze_dataset(args: argparse.Namespace, dataset: Dataset, out_root: Path) -> dict[str, Any]:
    angle_dir = out_root / _angle_slug(dataset.angle)
    for stale_subdir in [angle_dir / "jti_lines", angle_dir / "jti_merged_lines"]:
        if stale_subdir.exists():
            shutil.rmtree(stale_subdir)
    tags = load_tags(dataset.ttbin, angle_dir / "_tag_cache", int(args.ch_a), int(args.ch_b), args.max_events)
    if tags.t_a.size == 0 or tags.t_b.size == 0:
        raise RuntimeError(f"{dataset.ttbin}: selected channels contain no events")

    counts, edges, total_pairs = compute_delay_histogram_centered(
        tags.t_a,
        tags.t_b,
        window_ps=int(args.window_ps),
        bin_width_ps=int(args.delay_bin_width_ps),
    )
    centers = (edges[:-1] + edges[1:]) * 0.5
    peaks = find_delay_peaks(
        counts,
        edges,
        smooth_bins=int(args.peak_smooth_bins),
        min_prominence_fraction=float(args.min_prominence_fraction),
        min_distance_ps=int(args.min_peak_distance_ps),
        max_peaks=int(args.max_peaks),
    )
    edge_bins = max(1, int(round(1000.0 / float(args.delay_bin_width_ps))))
    edge_max = int(max(np.max(counts[:edge_bins]), np.max(counts[-edge_bins:]))) if counts.size else 0
    global_max = int(np.max(counts)) if counts.size else 0
    edge_fraction_of_peak = float(edge_max / global_max) if global_max else 0.0

    save_delay_csv(angle_dir / "pminus_delay_histogram.csv", counts, edges)
    _write_csv(
        angle_dir / "pminus_peaks.csv",
        [
            "rank_by_count",
            "delay_ps",
            "counts",
            "smoothed_counts",
            "relative_to_main",
            "bin_index",
            "spacing_from_previous_ps",
            "spacing_to_next_ps",
        ],
        peaks,
    )
    plot_delay(
        angle_dir / "pminus_delay_histogram.png",
        counts,
        edges,
        peaks,
        title=f"{dataset.angle} FPC P_minus | ch {args.ch_a}-{args.ch_b} | +/-{args.window_ps} ps",
    )

    peaks_by_count = sorted(peaks, key=lambda r: int(r["counts"]), reverse=True)
    selected_peaks = peaks_by_count if int(args.jti_lines) <= 0 else peaks_by_count[: int(args.jti_lines)]
    jti_outputs: list[dict[str, Any]] = []
    merged_counts = np.zeros((int(args.jti_dim), int(args.jti_dim)), dtype=np.float64)
    for peak in selected_peaks:
        tau = int(peak["delay_ps"])
        line_dir = angle_dir / "jti_lines" / f"line_tau_{tau:+d}ps"
        line_counts, line_meta = jti_for_centered_line(
            tags.t_a,
            tags.t_b,
            tau_center_ps=tau,
            half_window_ps=int(args.line_half_window_ps),
            dim=int(args.jti_dim),
            bin_width_ps=int(args.jti_bin_width_ps),
            frame_origin_ps=float(args.frame_origin_ps),
        )
        line_meta["peak_histogram_counts"] = int(peak["counts"])
        line_meta["peak_relative_to_main"] = float(peak["relative_to_main"])
        merged_counts += line_counts
        jti_outputs.append(
            save_jti_outputs(
                line_dir,
                line_counts,
                stem=f"jti_tau_{tau:+d}ps_dim{int(args.jti_dim)}_bw{int(args.jti_bin_width_ps)}ps",
                dim=int(args.jti_dim),
                bin_width_ps=int(args.jti_bin_width_ps),
                frame_origin_ps=float(args.frame_origin_ps),
                dataset=dataset,
                tags=tags,
            line_meta=line_meta,
            save_plot=not bool(args.no_jti_plots),
            pairing_mode="all_pairs_centered_line_window",
        )
        )

    merged_meta = None
    if selected_peaks:
        merged_meta = save_jti_outputs(
            angle_dir / "jti_merged_lines",
            merged_counts,
            stem=f"jti_merged_top{len(selected_peaks)}_dim{int(args.jti_dim)}_bw{int(args.jti_bin_width_ps)}ps",
            dim=int(args.jti_dim),
            bin_width_ps=int(args.jti_bin_width_ps),
            frame_origin_ps=float(args.frame_origin_ps),
            dataset=dataset,
            tags=tags,
            line_meta={
                "tau_center_ps": 0,
                "line_half_window_ps": int(args.line_half_window_ps),
                "n_pairs": int(np.sum(merged_counts)),
                "included_tau_centers_ps": [int(p["delay_ps"]) for p in selected_peaks],
                "note": "Merged reference JTI: sum of separately tau-centered line JTIs; use individual lines for physical interpretation.",
            },
            save_plot=not bool(args.no_jti_plots),
            pairing_mode="tau_centered_merged_reference",
        )

    raw_multiline_meta = None
    if selected_peaks:
        raw_tau_centers = sorted(int(p["delay_ps"]) for p in selected_peaks)
        if str(args.raw_multiline_tau_reference_ps).lower() == "min":
            raw_tau_reference = int(min(raw_tau_centers))
        elif str(args.raw_multiline_tau_reference_ps).lower() == "zero":
            raw_tau_reference = 0
        else:
            raw_tau_reference = int(args.raw_multiline_tau_reference_ps)
        raw_counts, raw_meta = jti_for_peak_union_raw_offsets(
            tags.t_a,
            tags.t_b,
            tau_centers_ps=raw_tau_centers,
            tau_reference_ps=raw_tau_reference,
            half_window_ps=int(args.raw_multiline_half_window_ps),
            dim=int(args.raw_multiline_dim),
            bin_width_ps=int(args.raw_multiline_bin_width_ps),
            frame_origin_ps=float(args.frame_origin_ps),
        )
        raw_multiline_meta = save_jti_outputs(
            angle_dir / "jti_multiline_raw_offsets",
            raw_counts,
            stem=f"jti_multiline_raw_offsets_top{len(raw_tau_centers)}_dim{int(args.raw_multiline_dim)}_bw{int(args.raw_multiline_bin_width_ps)}ps",
            dim=int(args.raw_multiline_dim),
            bin_width_ps=int(args.raw_multiline_bin_width_ps),
            frame_origin_ps=float(args.frame_origin_ps),
            dataset=dataset,
            tags=tags,
            line_meta=raw_meta,
            save_plot=not bool(args.no_jti_plots),
            tau_center_required=False,
            pairing_mode="peak_union_raw_offset_window",
        )
        band_png = (
            angle_dir
            / "jti_multiline_raw_offsets"
            / f"jti_multiline_raw_offsets_top{len(raw_tau_centers)}_diagband_pm{int(args.raw_multiline_band_half_width_bins)}bins.png"
        )
        plot_diagonal_band_heatmap(
            band_png,
            raw_counts,
            bin_width_ps=int(args.raw_multiline_bin_width_ps),
            half_width_bins=int(args.raw_multiline_band_half_width_bins),
            title=f"{dataset.angle} raw-offset multiline JTI diagonal-band zoom",
        )
        raw_multiline_meta["outputs"]["diagonal_band_zoom_png"] = str(band_png)

    publication_meta = None
    if bool(args.publication_plot):
        publication_meta = save_publication_outputs(
            angle_dir / "publication_jti",
            dataset=dataset,
            tags=tags,
            peaks=peaks,
            delay_counts=counts,
            delay_edges=edges,
            dim=int(args.publication_dim),
            bin_width_ps=int(args.publication_bin_width_ps),
            half_window_ps=int(args.publication_half_window_ps),
            frame_origin_ps=float(args.frame_origin_ps),
            annotate_lines=int(args.publication_annotate_lines),
            gamma=float(args.publication_gamma),
            vmax_percentile=float(args.publication_vmax_percentile),
        )

    centered_publication_meta = None
    center_mode = str(args.publication_center_mode).lower()
    if center_mode == "brightest":
        alignment_dir = _ensure_alignment_outputs(args, angle_dir=angle_dir, delay_csv=angle_dir / "pminus_delay_histogram.csv")
        center_offset_bin = (
            int(args.publication_center_offset_bin)
            if args.publication_center_offset_bin is not None
            else int(args.publication_dim) // 2 - int(args.publication_dim) // 4
        )
        centered_publication_meta = save_centered_publication_outputs(
            angle_dir / "centered_publication_jti",
            dataset=dataset,
            tags=tags,
            delay_counts=counts,
            delay_edges=edges,
            alignment_dir=alignment_dir,
            dim=int(args.publication_dim),
            half_window_ps=int(args.publication_center_half_window_ps),
            frame_origin_ps=float(args.frame_origin_ps),
            center_offset_bin=int(center_offset_bin),
            annotate_lines=int(args.publication_annotate_lines),
            gamma=float(args.publication_gamma),
            vmax_percentile=float(args.publication_vmax_percentile),
        )
    elif center_mode == "main-diagonal":
        centered_publication_meta = save_main_diagonal_single_side_outputs(
            angle_dir / "centered_publication_jti",
            dataset=dataset,
            tags=tags,
            peaks=peaks,
            delay_counts=counts,
            delay_edges=edges,
            dim=int(args.publication_dim),
            bin_width_ps=int(args.publication_bin_width_ps),
            half_window_ps=int(args.publication_center_half_window_ps),
            frame_origin_ps=float(args.frame_origin_ps),
            side=str(args.publication_single_side),
            annotate_lines=int(args.publication_annotate_lines),
            gamma=float(args.publication_gamma),
            vmax_percentile=float(args.publication_vmax_percentile),
        )

    summary = {
        "angle": dataset.angle,
        "ttbin": str(dataset.ttbin),
        "output_dir": str(angle_dir),
        "events": {"channel_a": int(tags.t_a.size), "channel_b": int(tags.t_b.size)},
        "delay_histogram": {
            "window_ps": int(args.window_ps),
            "bin_width_ps": int(args.delay_bin_width_ps),
            "total_pairs": int(total_pairs),
            "max_count": int(global_max),
            "edge_max_last_1ns": int(edge_max),
            "edge_fraction_of_peak": float(edge_fraction_of_peak),
            "csv": str(angle_dir / "pminus_delay_histogram.csv"),
            "png": str(angle_dir / "pminus_delay_histogram.png"),
        },
        "peaks": peaks,
        "selected_jti_peaks": selected_peaks,
        "jti_outputs": jti_outputs,
        "merged_jti": merged_meta,
        "raw_offset_multiline_jti": raw_multiline_meta,
        "publication_jti": publication_meta,
        "centered_publication_jti": centered_publication_meta,
    }
    (angle_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    return {
        **summary,
        "_comparison": {"angle": dataset.angle, "centers_ps": centers, "counts": counts},
    }


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Analyze FPC single-filter multiline P_minus peaks and tau-centered JTIs.")
    ap.add_argument("--data-root", default=DEFAULT_DATA_ROOT, help="Directory containing the FPC .1.ttbin files.")
    ap.add_argument("--ttbin", action="append", default=None, help="Explicit ttbin path. Can be passed multiple times.")
    ap.add_argument("--out", default=DEFAULT_OUT, help="Output directory.")
    ap.add_argument("--ch-a", type=int, default=2, help="TimeTagger hardware channel A.")
    ap.add_argument("--ch-b", type=int, default=3, help="TimeTagger hardware channel B.")
    ap.add_argument("--window-ps", type=int, default=20000, help="Wide P_minus half-window in ps.")
    ap.add_argument("--delay-bin-width-ps", type=int, default=20, help="P_minus histogram bin width in ps.")
    ap.add_argument("--peak-smooth-bins", type=int, default=3, help="Moving-average bins before peak detection.")
    ap.add_argument("--min-prominence-fraction", type=float, default=0.04, help="Peak threshold as a fraction of the smoothed maximum.")
    ap.add_argument("--min-peak-distance-ps", type=int, default=60, help="Minimum distance between detected peaks.")
    ap.add_argument("--max-peaks", type=int, default=40, help="Maximum peaks to report per dataset.")
    ap.add_argument("--jti-lines", type=int, default=5, help="Number of strongest peaks to extract as separate JTIs. Use 0 for all detected peaks.")
    ap.add_argument("--line-half-window-ps", type=int, default=200, help="Half-window around each tau peak for line JTI.")
    ap.add_argument("--jti-dim", type=int, default=1024, help="JTI dimension.")
    ap.add_argument("--jti-bin-width-ps", type=int, default=200, help="JTI bin width in ps.")
    ap.add_argument("--raw-multiline-dim", type=int, default=1024, help="Raw-offset multiline heatmap dimension.")
    ap.add_argument("--raw-multiline-bin-width-ps", type=int, default=20, help="Raw-offset multiline heatmap bin width in ps.")
    ap.add_argument("--raw-multiline-half-window-ps", type=int, default=40, help="Half-window around each detected tau peak for raw-offset multiline heatmap.")
    ap.add_argument("--raw-multiline-band-half-width-bins", type=int, default=70, help="Half-width in bins for raw-offset diagonal-band zoom plot.")
    ap.add_argument("--raw-multiline-tau-reference-ps", default="zero", help="Reference delay for raw-offset display. Use 'zero', 'min', or an integer ps value.")
    ap.add_argument("--publication-plot", action="store_true", help="Generate publication-style JTI heatmaps with P_minus inset.")
    ap.add_argument("--publication-dim", type=int, default=256, help="Publication-style JTI dimension.")
    ap.add_argument("--publication-bin-width-ps", type=int, default=20, help="Publication-style JTI bin width in ps.")
    ap.add_argument("--publication-half-window-ps", type=int, default=30, help="Half-window around each sideband for publication-style JTI.")
    ap.add_argument("--publication-annotate-lines", type=int, default=6, help="Number of strongest sidebands to label in publication-style plots.")
    ap.add_argument("--publication-gamma", type=float, default=0.55, help="PowerNorm gamma for publication-style heatmaps.")
    ap.add_argument("--publication-vmax-percentile", type=float, default=99.5, help="Nonzero count percentile used as publication-style heatmap vmax.")
    ap.add_argument("--publication-center-mode", choices=["none", "brightest", "main-diagonal"], default="none", help="Optional centered publication display mode.")
    ap.add_argument("--publication-use-alignment", default="auto", help="Alignment output directory, or 'auto' to run/reuse delay alignment diagnostics.")
    ap.add_argument("--publication-alignment-candidate-bw-ps", default="10:200:10", help="Candidate bw range/list passed to the alignment diagnostic in auto mode.")
    ap.add_argument("--publication-alignment-peak-side", choices=["all", "positive", "negative"], default="all", help="Peak-side passed to the alignment diagnostic in auto mode.")
    ap.add_argument("--publication-center-offset-bin", type=int, default=None, help="Display offset for the brightest line. Default: publication_dim//2 - publication_dim//4.")
    ap.add_argument("--publication-center-half-window-ps", type=int, default=30, help="Half-window around each alignment peak for centered publication JTI.")
    ap.add_argument("--publication-single-side", choices=["negative", "positive", "all"], default="negative", help="Peak side retained by main-diagonal publication mode after tau_rel=tau-tau0.")
    ap.add_argument("--frame-origin-ps", type=float, default=0.0, help="Frame origin for JTI binning.")
    ap.add_argument("--max-events", type=int, default=None, help="Optional maximum raw events to read.")
    ap.add_argument("--no-jti-plots", action="store_true", help="Skip JTI PNG heatmaps.")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    if args.ttbin:
        datasets = []
        for raw in args.ttbin:
            path = Path(str(raw).strip().strip('"'))
            match = re.search(r"FPC\s+(.+?)\s+Single", path.name)
            angle = match.group(1).strip() if match else path.stem
            datasets.append(Dataset(angle=angle, ttbin=path))
    else:
        datasets = discover_default_datasets(Path(str(args.data_root).strip().strip('"')))

    summaries = []
    comparison_rows = []
    for dataset in datasets:
        print(f"Analyzing {dataset.angle}: {dataset.ttbin}")
        summary = analyze_dataset(args, dataset, out_root)
        comparison_rows.append(summary.pop("_comparison"))
        summaries.append(summary)
        main_peak = max(summary["peaks"], key=lambda r: int(r["counts"])) if summary["peaks"] else None
        print(
            json.dumps(
                {
                    "angle": dataset.angle,
                    "total_pairs_wide_window": summary["delay_histogram"]["total_pairs"],
                    "main_peak": main_peak,
                    "n_peaks": len(summary["peaks"]),
                    "n_jti_lines": len(summary["jti_outputs"]),
                    "edge_fraction_of_peak": summary["delay_histogram"]["edge_fraction_of_peak"],
                },
                ensure_ascii=False,
                default=_json_default,
            )
        )

    plot_angle_comparison(out_root / "pminus_angle_comparison.png", comparison_rows)
    peak_rows: list[dict[str, Any]] = []
    jti_rows: list[dict[str, Any]] = []
    for summary in summaries:
        for peak in summary["peaks"]:
            peak_rows.append({"angle": summary["angle"], **peak})
        for output in summary["jti_outputs"]:
            jti_rows.append(
                {
                    "angle": summary["angle"],
                    "tau_center_ps": output["tau_center_ps"],
                    "line_half_window_ps": output["line_half_window_ps"],
                    "n_pairs": output["n_pairs"],
                    "diag_main_fraction": output["diagnostics"]["diag_main_fraction"],
                    "diag_pm1_fraction": output["diagnostics"]["diag_pm1_fraction"],
                    "counts_csv": output["outputs"]["counts_csv"],
                    "meta": output["outputs"]["meta"],
                }
            )
        raw = summary.get("raw_offset_multiline_jti")
        if raw:
            jti_rows.append(
                {
                    "angle": summary["angle"],
                    "tau_center_ps": "raw_offsets",
                    "line_half_window_ps": raw["line_half_window_ps"],
                    "n_pairs": raw["n_pairs"],
                    "diag_main_fraction": raw["diagnostics"]["diag_main_fraction"],
                    "diag_pm1_fraction": raw["diagnostics"]["diag_pm1_fraction"],
                    "counts_csv": raw["outputs"]["counts_csv"],
                    "meta": raw["outputs"]["meta"],
                }
            )
        publication = summary.get("publication_jti")
        if publication:
            jti_rows.append(
                {
                    "angle": summary["angle"],
                    "tau_center_ps": "publication",
                    "line_half_window_ps": publication["sideband_half_window_ps"],
                    "n_pairs": publication["n_pairs"],
                    "diag_main_fraction": publication["diagnostics"]["diag_main_fraction"],
                    "diag_pm1_fraction": publication["diagnostics"]["diag_pm1_fraction"],
                    "counts_csv": publication["outputs"]["counts_csv"],
                    "meta": publication["outputs"]["meta"],
                }
            )
        centered = summary.get("centered_publication_jti")
        if centered:
            jti_rows.append(
                {
                    "angle": summary["angle"],
                    "tau_center_ps": "centered_publication",
                    "line_half_window_ps": centered["sideband_half_window_ps"],
                    "n_pairs": centered["n_pairs"],
                    "diag_main_fraction": centered["diagnostics"]["diag_main_fraction"],
                    "diag_pm1_fraction": centered["diagnostics"]["diag_pm1_fraction"],
                    "counts_csv": centered["outputs"]["counts_csv"],
                    "meta": centered["outputs"]["meta"],
                }
            )
    _write_csv(
        out_root / "all_detected_peaks.csv",
        [
            "angle",
            "rank_by_count",
            "delay_ps",
            "counts",
            "smoothed_counts",
            "relative_to_main",
            "bin_index",
            "spacing_from_previous_ps",
            "spacing_to_next_ps",
        ],
        peak_rows,
    )
    _write_csv(
        out_root / "jti_line_summary.csv",
        ["angle", "tau_center_ps", "line_half_window_ps", "n_pairs", "diag_main_fraction", "diag_pm1_fraction", "counts_csv", "meta"],
        jti_rows,
    )
    root_summary = {
        "output_dir": str(out_root),
        "parameters": vars(args),
        "datasets": summaries,
        "outputs": {
            "all_detected_peaks_csv": str(out_root / "all_detected_peaks.csv"),
            "jti_line_summary_csv": str(out_root / "jti_line_summary.csv"),
            "pminus_angle_comparison_png": str(out_root / "pminus_angle_comparison.png"),
            "publication_jti_dirs": [
                str(Path(s["output_dir"]) / "publication_jti")
                for s in summaries
                if s.get("publication_jti") is not None
            ],
            "centered_publication_jti_dirs": [
                str(Path(s["output_dir"]) / "centered_publication_jti")
                for s in summaries
                if s.get("centered_publication_jti") is not None
            ],
        },
    }
    (out_root / "summary.json").write_text(json.dumps(root_summary, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    print(json.dumps(root_summary["outputs"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
