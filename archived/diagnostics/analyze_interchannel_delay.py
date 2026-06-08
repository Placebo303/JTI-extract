#!/usr/bin/env python3
"""Analyze inter-channel delay distribution P-(τ) for TimeTagger .ttbin files."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jti_extract.cli.tdc_layer_scan import Tags, load_tags


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


def normalize_path(text: str) -> Path:
    return Path(str(text).strip().strip('"'))


def load_ttbin_events(input_path: Path, output_dir: Path, channels: tuple[int, int], max_events: int | None = None) -> Tags:
    return load_tags(input_path, output_dir / "_tag_cache", int(channels[0]), int(channels[1]), max_events)


def compute_interchannel_delay(
    t_a: np.ndarray,
    t_b: np.ndarray,
    *,
    window_ps: int = 10000,
) -> np.ndarray:
    """Compute inter-channel delay τ = t_b - t_a for all pairs within window."""
    t_a = np.asarray(t_a, dtype=np.int64)
    t_b = np.asarray(t_b, dtype=np.int64)
    
    delays = []
    for i in range(t_a.size):
        # Find all t_b within window of t_a[i]
        left = np.searchsorted(t_b, t_a[i] - window_ps, side="left")
        right = np.searchsorted(t_b, t_a[i] + window_ps, side="right")
        if left < right:
            delays.extend(t_b[left:right] - t_a[i])
    
    return np.array(delays, dtype=np.int64) if delays else np.array([], dtype=np.int64)


def compute_interchannel_delay_fast(
    t_a: np.ndarray,
    t_b: np.ndarray,
    *,
    window_ps: int = 10000,
    chunk_size: int = 100000,
) -> np.ndarray:
    """Fast chunked computation of inter-channel delay τ = t_b - t_a."""
    t_a = np.asarray(t_a, dtype=np.int64)
    t_b = np.asarray(t_b, dtype=np.int64)
    
    all_delays = []
    for start in range(0, t_a.size, chunk_size):
        end = min(start + chunk_size, t_a.size)
        chunk_a = t_a[start:end]
        
        for i in range(chunk_a.size):
            left = np.searchsorted(t_b, chunk_a[i] - window_ps, side="left")
            right = np.searchsorted(t_b, chunk_a[i] + window_ps, side="right")
            if left < right:
                all_delays.extend(t_b[left:right] - chunk_a[i])
    
    return np.array(all_delays, dtype=np.int64) if all_delays else np.array([], dtype=np.int64)


def compute_delay_histogram(
    delays_ps: np.ndarray,
    *,
    bin_width_ps: int = 10,
    range_ps: tuple[int, int] = (-10000, 10000),
) -> tuple[np.ndarray, np.ndarray]:
    """Compute histogram of inter-channel delays."""
    edges = np.arange(range_ps[0], range_ps[1] + bin_width_ps, bin_width_ps, dtype=np.float64)
    counts, _ = np.histogram(delays_ps.astype(np.float64), bins=edges)
    return counts.astype(np.int64), edges


def find_peak_region(
    counts: np.ndarray,
    edges: np.ndarray,
    *,
    threshold_fraction: float = 0.1,
) -> dict[str, Any]:
    """Find the peak region and compute FWHM and central width metrics."""
    if counts.size == 0:
        return {"fwhm_ps": 0, "central_90_percent_ps": 0, "central_95_percent_ps": 0}
    
    max_count = int(np.max(counts))
    if max_count == 0:
        return {"fwhm_ps": 0, "central_90_percent_ps": 0, "central_95_percent_ps": 0}
    
    # Find peak position
    peak_idx = int(np.argmax(counts))
    peak_center = float((edges[peak_idx] + edges[peak_idx + 1]) * 0.5)
    
    # FWHM
    half_max = max_count * 0.5
    above_half = counts >= half_max
    if np.any(above_half):
        indices = np.where(above_half)[0]
        fwhm_ps = float(edges[indices[-1] + 1] - edges[indices[0]])
    else:
        fwhm_ps = 0.0
    
    # Central 90% and 95% width
    total_counts = int(np.sum(counts))
    sorted_indices = np.argsort(-counts)
    cumulative = np.cumsum(counts[sorted_indices])
    
    central_90_idx = np.searchsorted(cumulative, total_counts * 0.9)
    central_95_idx = np.searchsorted(cumulative, total_counts * 0.95)
    
    central_90_indices = sorted_indices[:central_90_idx + 1]
    central_95_indices = sorted_indices[:central_95_idx + 1]
    
    central_90_ps = float(edges[central_90_indices.max() + 1] - edges[central_90_indices.min()]) if central_90_indices.size > 0 else 0.0
    central_95_ps = float(edges[central_95_indices.max() + 1] - edges[central_95_indices.min()]) if central_95_indices.size > 0 else 0.0
    
    return {
        "peak_center_ps": peak_center,
        "fwhm_ps": fwhm_ps,
        "central_90_percent_ps": central_90_ps,
        "central_95_percent_ps": central_95_ps,
        "max_count": max_count,
        "total_counts": total_counts,
    }


def save_delay_histogram_csv(path: Path, counts: np.ndarray, edges: np.ndarray) -> None:
    """Save delay histogram to CSV."""
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["delay_ps", "counts"])
        for i in range(counts.size):
            delay_center = (edges[i] + edges[i + 1]) * 0.5
            writer.writerow([int(delay_center), int(counts[i])])


def plot_delay_histogram(path: Path, counts: np.ndarray, edges: np.ndarray, *, title: str) -> None:
    """Plot delay histogram."""
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        raise RuntimeError(f"matplotlib is required for plotting: {exc}") from exc
    
    centers = (edges[:-1] + edges[1:]) * 0.5
    fig, ax = plt.subplots(figsize=(10, 5), dpi=160)
    ax.plot(centers * 1e-3, counts, linewidth=0.8)  # Convert to ns for readability
    ax.set_xlabel("Inter-channel delay τ = t_B - t_A (ns)")
    ax.set_ylabel("Counts")
    ax.set_title(title)
    ax.grid(True, linewidth=0.4, alpha=0.35)
    ax.axvline(x=0, color='r', linestyle='--', alpha=0.5, label='τ = 0')
    ax.legend()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    input_path = normalize_path(args.input)
    output_dir = normalize_path(args.output_dir)
    channels = (int(args.channels[0]), int(args.channels[1]))
    
    tags = load_ttbin_events(input_path, output_dir, channels, args.max_events)
    if tags.t_a.size == 0 or tags.t_b.size == 0:
        raise RuntimeError("selected channels contain no events")
    
    print(f"Loaded {tags.t_a.size} events in channel A, {tags.t_b.size} events in channel B")
    
    # Compute delays
    window_ps = int(args.window_ps)
    print(f"Computing inter-channel delays with window = {window_ps} ps...")
    
    delays = compute_interchannel_delay_fast(tags.t_a, tags.t_b, window_ps=window_ps)
    print(f"Found {delays.size} pairs within window")
    
    # Compute histogram
    bin_width_ps = int(args.bin_width_ps)
    range_ps = (-window_ps, window_ps)
    counts, edges = compute_delay_histogram(delays, bin_width_ps=bin_width_ps, range_ps=range_ps)
    
    # Find peak region
    peak_info = find_peak_region(counts, edges)
    
    # Save outputs
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"interchannel_delay_ch{channels[0]}_ch{channels[1]}"
    
    csv_path = output_dir / f"{stem}.csv"
    png_path = output_dir / f"{stem}.png"
    json_path = output_dir / f"{stem}_summary.json"
    
    save_delay_histogram_csv(csv_path, counts, edges)
    
    title = (
        f"{input_path.name} | ch {channels[0]}-{channels[1]} | "
        f"window {window_ps} ps | bin {bin_width_ps} ps"
    )
    plot_delay_histogram(png_path, counts, edges, title=title)
    
    # Compute statistics
    duration_s = float(tags.meta.get("acquisition_duration_s", 0))
    summary = {
        "input": {"path": str(input_path), "channels": [channels[0], channels[1]]},
        "acquisition": {"duration_s": duration_s},
        "events": {"channel_a": int(tags.t_a.size), "channel_b": int(tags.t_b.size)},
        "delay_analysis": {
            "window_ps": window_ps,
            "bin_width_ps": bin_width_ps,
            "total_pairs": int(delays.size),
            "mean_delay_ps": float(np.mean(delays)) if delays.size > 0 else 0.0,
            "std_delay_ps": float(np.std(delays)) if delays.size > 0 else 0.0,
            **peak_info,
        },
        "outputs": {
            "csv": str(csv_path),
            "png": str(png_path),
            "summary": str(json_path),
        },
    }
    
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    
    print(f"\nResults:")
    print(f"  Total pairs: {delays.size}")
    print(f"  Peak center: {peak_info.get('peak_center_ps', 0):.1f} ps")
    print(f"  FWHM: {peak_info.get('fwhm_ps', 0):.1f} ps")
    print(f"  Central 90% width: {peak_info.get('central_90_percent_ps', 0):.1f} ps")
    print(f"  Central 95% width: {peak_info.get('central_95_percent_ps', 0):.1f} ps")
    print(f"\nOutputs saved to:")
    print(f"  CSV: {csv_path}")
    print(f"  PNG: {png_path}")
    print(f"  Summary: {json_path}")
    
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze inter-channel delay distribution P-(τ) for TimeTagger .ttbin files.")
    parser.add_argument("--input", required=True, help="Input .ttbin file.")
    parser.add_argument("--channels", nargs=2, type=int, required=True, metavar=("A", "B"), help="Hardware channels to pair.")
    parser.add_argument("--window-ps", type=int, default=10000, help="Search window in ps (default: 10000 = ±10 ns).")
    parser.add_argument("--bin-width-ps", type=int, default=10, help="Histogram bin width in ps (default: 10).")
    parser.add_argument("--output-dir", required=True, help="Output directory.")
    parser.add_argument("--max-events", type=int, default=None, help="Optional maximum raw events to read.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    summary = analyze(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
