#!/usr/bin/env python3
"""Run pseudo-CV for all 6 combinations (3 angles × 2 binwidths)."""

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
DV_DIM = 128
RAW_CH_A = 2
RAW_CH_B = 3
GUARD = 2


def build_cmds() -> list[tuple[str, list[str], Path]]:
    cmds = []
    for angle, folder in ANGLES.items():
        ttbin = DATA_ROOT / f"{folder}.1.ttbin"
        peaks_csv = DATA_ROOT / "jti_extracted_bw20" / f"{angle}deg" / "pminus_peaks.csv"
        delay_csv = DATA_ROOT / "jti_extracted_bw20" / f"{angle}deg" / "pminus_delay_histogram.csv"
        for bw in BINWIDTHS:
            out_dir = DATA_ROOT / f"pseudo_cv_{angle}_bw{bw}"
            cmd = [
                sys.executable, str(ROOT / "scripts" / "pseudo_cv_from_modeb.py"),
                "--ttbin", str(ttbin),
                "--peaks-csv", str(peaks_csv),
                "--delay-csv", str(delay_csv),
                "--raw-ch-a-id", str(RAW_CH_A),
                "--raw-ch-b-id", str(RAW_CH_B),
                "--dv-dim", str(DV_DIM),
                "--dv-bw-ps", str(bw),
                "--guard-bins", str(GUARD),
                "--out", str(out_dir),
            ]
            cmds.append((f"pseudo-CV {angle}° bw={bw}ps", cmd, out_dir))
    return cmds


def main() -> int:
    cmds = build_cmds()
    print(f"Total: {len(cmds)} runs")
    t_start = time.time()
    results = []

    for label, cmd, out_dir in cmds:
        print(f"\n{'='*60}")
        print(f"[START] {label}")
        t0 = time.time()
        try:
            r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=1800)
            elapsed = time.time() - t0
            if r.returncode == 0:
                print(f"[DONE]  {label} ({elapsed:.1f}s)")
                for line in r.stdout.strip().splitlines()[-3:]:
                    print(f"  | {line}")
                results.append((label, True, f"OK ({elapsed:.1f}s)"))
            else:
                print(f"[FAIL]  {label}")
                for line in r.stderr.strip().splitlines()[-5:]:
                    print(f"  ! {line}")
                results.append((label, False, f"exit={r.returncode}"))
        except Exception as exc:
            results.append((label, False, repr(exc)))

    total = time.time() - t_start
    ok = sum(1 for _, v, _ in results if v)
    print(f"\n{'='*60}")
    print(f"DONE ({total:.1f}s) — {ok}/{len(results)} passed")
    for label, v, msg in results:
        print(f"  [{'OK' if v else 'FAIL'}] {label}: {msg}")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
