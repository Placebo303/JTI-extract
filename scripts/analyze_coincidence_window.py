#!/usr/bin/env python3
"""Analyze coincidence distribution in random time windows."""

from __future__ import annotations

import argparse
import csv
import json
import random
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


def load_ttbin_events(input_path: Path, output_dir: Path, channels: tuple[int, int], max_events: int | None = None) -> Tags:
    return load_tags(input_path, output_dir / "_tag_cache", int(channels[0]), int(channels[1]), max_events)


def compute_all_pairs(t_a: np.ndarray, t_b: np.ndarray, window_ps: int) -> tuple[np.ndarray, np.ndarray]:
    """Compute all pairs within coincidence window."""
    t_a = np.asarray(t_a, dtype=np.int64)
    t_b = np.asarray(t_b, dtype=np.int64)
    w = int(window_ps)
    
    all_a = []
    all_b = []
    
    for i in range(t_a.size):
        left = np.searchsorted(t_b, t_a[i] - w, side="left")
        right = np.searchsorted(t_b, t_a[i] + w, side="right")
        if left < right:
            all_a.extend([t_a[i]] * (right - left))
            all_b.extend(t_b[left:right])
    
    return np.array(all_a, dtype=np.int64), np.array(all_b, dtype=np.int64)


def analyze_window(
    midpoints: np.ndarray,
    window_ps: int,
    binwidth_ps: int,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, float, float]:
    """Analyze coincidence distribution in a random window."""
    random.seed(seed)
    
    min_time = float(np.min(midpoints))
    max_time = float(np.max(midpoints))
    
    max_start = max_time - window_ps
    start_ps = random.uniform(min_time, max_start)
    end_ps = start_ps + window_ps
    
    mask = (midpoints >= start_ps) & (midpoints < end_ps)
    window_midpoints = midpoints[mask]
    
    n_bins = int(window_ps / binwidth_ps)
    bins = np.linspace(start_ps, end_ps, n_bins + 1)
    counts, edges = np.histogram(window_midpoints, bins=bins)
    
    return counts, edges, start_ps, end_ps


def save_csv(path: Path, counts: np.ndarray, edges: np.ndarray, start_ps: float) -> None:
    """Save CSV with relative time."""
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["relative_time_ns", "counts"])
        for i in range(counts.size):
            time_center = (edges[i] + edges[i + 1]) / 2
            relative_time_ns = (time_center - start_ps) / 1000  # ps -> ns
            writer.writerow([f"{relative_time_ns:.1f}", int(counts[i])])


def plot_png(path: Path, counts: np.ndarray, edges: np.ndarray, window_us: int, start_ps: float) -> None:
    """Plot coincidence distribution."""
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        raise RuntimeError(f"matplotlib is required: {exc}") from exc
    
    relative_time_ns = ((edges[:-1] + edges[1:]) / 2 - start_ps) / 1000
    
    fig, ax = plt.subplots(figsize=(10, 5), dpi=150)
    ax.bar(relative_time_ns, counts, width=20, alpha=0.7, color='steelblue', edgecolor='navy', linewidth=0.5)
    ax.set_xlabel('Relative time (ns)')
    ax.set_ylabel('Coincidence counts')
    ax.set_title(f'Coincidence distribution in {window_us}µs window (binwidth=20ns)')
    ax.grid(True, alpha=0.3, linewidth=0.5)
    
    mean_counts = np.mean(counts)
    std_counts = np.std(counts)
    ax.axhline(y=mean_counts, color='r', linestyle='--', alpha=0.7, label=f'Mean={mean_counts:.1f}')
    ax.axhline(y=mean_counts + std_counts, color='orange', linestyle=':', alpha=0.5, label=f'Std={std_counts:.1f}')
    ax.axhline(y=mean_counts - std_counts, color='orange', linestyle=':', alpha=0.5)
    ax.legend()
    
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze coincidence distribution in random time windows.")
    parser.add_argument("--input", required=True, help="Input .ttbin file.")
    parser.add_argument("--channels", nargs=2, type=int, required=True, metavar=("A", "B"), help="Hardware channels.")
    parser.add_argument("--output-dir", required=True, help="Output directory.")
    parser.add_argument("--coinc-window-ps", type=int, default=200, help="Coincidence window in ps.")
    parser.add_argument("--binwidth-ps", type=int, default=20000, help="Histogram bin width in ps (default: 20ns).")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for window selection.")
    args = parser.parse_args(argv)
    
    window_lengths_us = [3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 35, 40]
    
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Loading data from {input_path}...")
    tags = load_ttbin_events(input_path, output_dir, (int(args.channels[0]), int(args.channels[1])))
    print(f"  CH{args.channels[0]}: {tags.t_a.size} events")
    print(f"  CH{args.channels[1]}: {tags.t_b.size} events")
    
    print(f"\nComputing all pairs (window={args.coinc_window_ps}ps)...")
    pairs_a, pairs_b = compute_all_pairs(tags.t_a, tags.t_b, int(args.coinc_window_ps))
    midpoints = (pairs_a.astype(np.float64) + pairs_b.astype(np.float64)) / 2
    print(f"  Total pairs: {pairs_a.size}")
    print(f"  Midpoint range: {np.min(midpoints):.0f} - {np.max(midpoints):.0f} ps")
    
    results = []
    print(f"\nAnalyzing windows (binwidth={args.binwidth_ps}ps, seed={args.seed}):")
    
    for window_us in window_lengths_us:
        window_ps = window_us * 1_000_000
        
        counts, edges, start_ps, end_ps = analyze_window(
            midpoints, window_ps, int(args.binwidth_ps), int(args.seed)
        )
        
        csv_path = output_dir / f"coincidence_window_{window_us}us.csv"
        png_path = output_dir / f"coincidence_window_{window_us}us.png"
        
        save_csv(csv_path, counts, edges, start_ps)
        plot_png(png_path, counts, edges, window_us, start_ps)
        
        mean_counts = float(np.mean(counts))
        std_counts = float(np.std(counts))
        poisson_std = np.sqrt(mean_counts) if mean_counts > 0 else 0
        
        result = {
            "window_us": window_us,
            "window_ps": window_ps,
            "n_bins": int(counts.size),
            "total_counts": int(np.sum(counts)),
            "mean_counts": mean_counts,
            "std_counts": std_counts,
            "poisson_std": float(poisson_std),
            "std_over_poisson": float(std_counts / poisson_std) if poisson_std > 0 else float('nan'),
            "min_counts": int(np.min(counts)),
            "max_counts": int(np.max(counts)),
            "start_ps": start_ps,
            "end_ps": end_ps,
            "csv_path": str(csv_path),
            "png_path": str(png_path),
        }
        results.append(result)
        
        print(f"  {window_us:2d}us: {counts.size:5d} bins, {int(np.sum(counts)):7d} counts, "
              f"mean={mean_counts:.1f}, std={std_counts:.1f}, std/poisson={result['std_over_poisson']:.3f}")
    
    summary = {
        "input": str(input_path),
        "channels": [int(args.channels[0]), int(args.channels[1])],
        "coincidence_window_ps": int(args.coinc_window_ps),
        "binwidth_ps": int(args.binwidth_ps),
        "seed": int(args.seed),
        "total_pairs": int(pairs_a.size),
        "windows": results,
    }
    
    summary_path = output_dir / "coincidence_window_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    
    print(f"\nResults saved to: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
