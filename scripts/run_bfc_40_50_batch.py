#!/usr/bin/env python3
"""Batch run modeB (FPC Schmidt) + CV 5ps heatmap for 2026.04.13BFC data.

Runs 12 commands total:
  6x compute_fpc_schmidt.py (3 angles x 2 binwidths: 40ps, 50ps)
  6x extract.py CV 5ps (3 angles x 2 binwidths: 40ps, 50ps)
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = Path(r"D:\Data\Raw Data\2026.04.13BFC\Time Tags")

ANGLES = {
    "90":  "Type II FPC 90° Single Filter_2026-04-13_165855",
    "135": "Type II FPC 135° Single Filter_2026-04-13_171823",
    "180": "Type II FPC 180° Single Filter_2026-04-13_170734",
}

BINWIDTHS = [40, 50]
TAU_ALIGN = 830
DIM = 128
GUARD = 2
RAW_CH_A = 2
RAW_CH_B = 3


def build_modeb_cmds() -> list[tuple[str, list[str], Path]]:
    """Build compute_fpc_schmidt.py commands."""
    cmds = []
    for angle, folder in ANGLES.items():
        ttbin = DATA_ROOT / f"{folder}.1.ttbin"
        peaks_csv = DATA_ROOT / "jti_extracted_bw20" / f"{angle}deg" / "pminus_peaks.csv"
        delay_csv = DATA_ROOT / "jti_extracted_bw20" / f"{angle}deg" / "pminus_delay_histogram.csv"
        for bw in BINWIDTHS:
            out_dir = DATA_ROOT / f"schmidt_{angle}_bw{bw}"
            cmd = [
                sys.executable, str(ROOT / "compute_fpc_schmidt.py"),
                "--ttbin", str(ttbin),
                "--peaks-csv", str(peaks_csv),
                "--delay-csv", str(delay_csv),
                "--raw-ch-a-id", str(RAW_CH_A),
                "--raw-ch-b-id", str(RAW_CH_B),
                "--tau-align-ps", str(TAU_ALIGN),
                "--binwidth-ps", str(bw),
                "--dimensions", str(DIM),
                "--guard-bins", str(GUARD),
                "--out", str(out_dir),
            ]
            cmds.append((f"modeB {angle}° bw={bw}ps", cmd, out_dir))
    return cmds


def build_cv_cmds() -> list[tuple[str, list[str], Path]]:
    """Build extract.py CV 5ps commands."""
    cmds = []
    for angle, folder in ANGLES.items():
        ttbin = DATA_ROOT / f"{folder}.1.ttbin"
        for bw in BINWIDTHS:
            out_dir = DATA_ROOT / f"cv5ps_{angle}_bw{bw}"
            cmd = [
                sys.executable, "-m", "jti_extract.cli.extract",
                "--ttbin", str(ttbin),
                "--raw-ch-a-id", str(RAW_CH_A),
                "--raw-ch-b-id", str(RAW_CH_B),
                "--binwidth-ps", str(bw),
                "--dimensions", str(DIM),
                "--fine-bins", "5",
                "--k-values", "1",
                "--tau0-ps", str(TAU_ALIGN),
                "--scan-frame-origin",
                "--svd-unwrapped",
                "--guard-bins", str(GUARD),
                "--out", str(out_dir),
            ]
            cmds.append((f"CV5ps {angle}° bw={bw}ps", cmd, out_dir))
    return cmds


def run_command(label: str, cmd: list[str], out_dir: Path) -> tuple[str, bool, str]:
    """Run one command, return (label, success, message)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n{'='*60}")
    print(f"[START] {label}")
    print(f"  output: {out_dir}")
    print(f"{'='*60}")
    t0 = time.time()
    try:
        result = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=1800,
        )
        elapsed = time.time() - t0
        if result.returncode == 0:
            print(f"[DONE]  {label} ({elapsed:.1f}s)")
            if result.stdout.strip():
                for line in result.stdout.strip().splitlines()[-5:]:
                    print(f"  | {line}")
            return label, True, f"OK ({elapsed:.1f}s)"
        else:
            print(f"[FAIL]  {label} ({elapsed:.1f}s)")
            stderr = result.stderr.strip()
            if stderr:
                for line in stderr.splitlines()[-10:]:
                    print(f"  ! {line}")
            return label, False, f"exit={result.returncode}: {stderr[-200:]}"
    except subprocess.TimeoutExpired:
        return label, False, "timeout (1800s)"
    except Exception as exc:
        return label, False, repr(exc)


def main() -> int:
    modeb_cmds = build_modeb_cmds()
    cv_cmds = build_cv_cmds()
    all_cmds = modeb_cmds + cv_cmds

    print(f"Total commands: {len(all_cmds)}")
    print(f"  ModeB: {len(modeb_cmds)}")
    print(f"  CV 5ps: {len(cv_cmds)}")
    print(f"Project root: {ROOT}")
    print(f"Data root: {DATA_ROOT}")

    results: list[tuple[str, bool, str]] = []
    t_start = time.time()

    for label, cmd, out_dir in all_cmds:
        label_r, ok, msg = run_command(label, cmd, out_dir)
        results.append((label_r, ok, msg))

    total_elapsed = time.time() - t_start

    print(f"\n{'='*60}")
    print(f"BATCH COMPLETE ({total_elapsed:.1f}s)")
    print(f"{'='*60}")
    ok_count = sum(1 for _, ok, _ in results if ok)
    fail_count = len(results) - ok_count
    print(f"  Passed: {ok_count}/{len(results)}")
    if fail_count:
        print(f"  Failed: {fail_count}/{len(results)}")
    print()
    for label, ok, msg in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {label}: {msg}")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
