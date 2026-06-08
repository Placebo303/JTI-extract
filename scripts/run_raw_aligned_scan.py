#!/usr/bin/env python3
"""Batch parameter scan for raw-aligned FPC JTI.

Runs jti_extract.cli.raw_aligned with --compute-svd across multiple
binwidth/dimension/guard_bins combinations, then produces a combined
scan_summary.csv and terminal report.
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TTBIN = r"D:\Data\Raw Data\2026.04.13BFC\Time Tags\Type II FPC 90° Single Filter_2026-04-13_165855.1.ttbin"
PEAKS_CSV = r"D:\Code\JTI提取\results\fpc_multiline_analysis\90deg\pminus_peaks.csv"
OUT_BASE = r"D:\Data\Raw Data\2026.04.13BFC\Time Tags\raw_aligned_scan_90deg"

COMMON_ARGS = [
    "--raw-ch-a-id", "2",
    "--raw-ch-b-id", "3",
    "--tau-align-ps", "830",
    "--delay-min-ps", "-1500",
    "--delay-max-ps", "300",
    "--frame-origin-ps", "0",
    "--compute-svd",
]

# (label, binwidth_ps, dimensions, guard_bins)
SCANS = [
    # Main scan: frame_period ≈ 3200 ps
    ("bw20_dim160_gb5",  20, 160, 5),
    ("bw25_dim128_gb4",  25, 128, 4),
    ("bw40_dim80_gb2",   40,  80, 2),
    ("bw50_dim64_gb2",   50,  64, 2),
    ("bw80_dim40_gb1",   80,  40, 1),
    ("bw100_dim32_gb1", 100,  32, 1),
    # N sensitivity scan
    ("bw40_dim64_gb2",   40,  64, 2),
    ("bw40_dim96_gb2",   40,  96, 2),
    ("bw40_dim128_gb2",  40, 128, 2),
    ("bw50_dim48_gb2",   50,  48, 2),
    ("bw50_dim80_gb2",   50,  80, 2),
    ("bw50_dim96_gb2",   50,  96, 2),
]


def run_scan(label: str, bw: int, dim: int, gb: int) -> dict | None:
    out_dir = Path(OUT_BASE) / label
    cmd = [
        sys.executable, "-m", "jti_extract.cli.raw_aligned",
        "--ttbin", TTBIN,
        "--peaks-csv", PEAKS_CSV,
        "--binwidth-ps", str(bw),
        "--dimensions", str(dim),
        "--guard-bins", str(gb),
        "--out", str(out_dir),
    ] + COMMON_ARGS

    print(f"\n{'='*60}")
    print(f"  [{label}] bw={bw} ps, N={dim}, guard_bins={gb}")
    print(f"  frame_period = {dim * bw} ps, guard_ps = {gb * bw} ps")
    print(f"{'='*60}")

    result = subprocess.run(cmd, capture_output=False, timeout=600)
    if result.returncode != 0:
        print(f"  FAILED (exit code {result.returncode})")
        return None

    summary_path = out_dir / "summary.csv"
    if not summary_path.exists():
        print(f"  WARNING: summary.csv not found at {summary_path}")
        return None

    with summary_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        row = next(reader)
    return row


def main() -> int:
    out_base = Path(OUT_BASE)
    out_base.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    for label, bw, dim, gb in SCANS:
        row = run_scan(label, bw, dim, gb)
        if row is not None:
            row["label"] = label
            results.append(row)

    # Combined summary
    if not results:
        print("\nNo successful scans.")
        return 1

    fields = list(results[0].keys())
    combined_path = out_base / "scan_summary.csv"
    with combined_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in results:
            w.writerow({k: row.get(k, "") for k in fields})
    print(f"\nSaved combined summary: {combined_path}")

    # Terminal report
    print(f"\n{'='*80}")
    print("SCAN SUMMARY")
    print(f"{'='*80}")
    header = f"{'label':<22} {'bw':>4} {'N':>4} {'fp':>6} {'retained':>9} {'xf':>7} {'K':>8} {'purity':>10} {'n_sv':>5}"
    print(header)
    print("-" * len(header))
    for r in results:
        print(
            f"{r.get('label',''):<22} "
            f"{r.get('binwidth_ps',''):>4} "
            f"{r.get('dimension',''):>4} "
            f"{r.get('frame_period_ps',''):>6} "
            f"{r.get('retained_in_jti',''):>9} "
            f"{r.get('cross_frame_rejected',''):>7} "
            f"{r.get('K_raw_aligned',''):>8} "
            f"{r.get('purity',''):>10} "
            f"{r.get('n_singular_values',''):>5}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
