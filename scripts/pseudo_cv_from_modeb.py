#!/usr/bin/env python3
"""Pseudo-CV heatmap from modeB peak-aware pairing.

Reuses modeB's adaptive per-peak ROI pairing + greedy-unique constraint,
then rebins accepted pairs into a fine-grained 2D histogram.

Axes are labeled in DV-bin units (0→dim-1) so the image directly
corresponds to the DV matrix, at finer resolution controlled by --fine-bin-ps.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from compute_fpc_schmidt import (
    CandidatePair,
    build_jti,
    compute_residual_diagnostics,
    compute_roi_half_widths,
    estimate_fwhm_from_histogram,
    filter_peaks,
    generate_candidates,
    global_greedy_unique,
    infer_tau_align,
    load_peaks,
)
from jti_extract.cli.tdc_layer_scan import load_tags


PROMINENCE = 0.04


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, Path):
        return str(obj)
    return str(obj)


def save_csv_matrix(path: Path, mat: np.ndarray, bw_ps: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = int(mat.shape[0])
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["bin_index", "time_ps"] + [f"col_{i}" for i in range(n)])
        for i in range(n):
            w.writerow([i, i * bw_ps] + [float(x) for x in mat[i, :].tolist()])


def save_png(
    path: Path,
    mat: np.ndarray,
    *,
    dv_dim: int,
    fine_dim: int,
    fine_bin_ps: int,
    frame_period_ps: int,
    title: str,
) -> None:
    import matplotlib.pyplot as plt

    n = int(mat.shape[0])
    # Axes in DV-bin units: 0 → dv_dim
    # Each DV bin = (dv_dim / fine_dim) * fine_bin_ps ... but dv_dim * dv_bw = frame = fine_dim * fine_bin_ps
    # So DV-bin index = fine_bin_index * (dv_dim / fine_dim)
    # Tick at fine_bin 0, 10, 20, ... → DV bin 0, 1, 2, ...
    dv_per_fine = dv_dim / fine_dim  # e.g. 128/1280 = 0.1

    fig, ax = plt.subplots(figsize=(8, 7), dpi=150)
    extent = [0, dv_dim, 0, dv_dim]
    im = ax.imshow(
        mat,
        origin="lower",
        aspect="equal",
        extent=extent,
        cmap="viridis",
        interpolation="nearest",
    )
    ax.set_xlabel("t_A DV-bin index")
    ax.set_ylabel("t_B DV-bin index")
    ax.set_title(title)
    ax.set_xticks(np.arange(0, dv_dim + 1, max(1, dv_dim // 8)))
    ax.set_yticks(np.arange(0, dv_dim + 1, max(1, dv_dim // 8)))
    plt.colorbar(im, ax=ax, label="Counts")
    fig.tight_layout()
    fig.savefig(str(path))
    plt.close(fig)


def run_one(
    ttbin: Path,
    peaks_csv: Path,
    delay_csv: Path,
    *,
    raw_ch_a: int,
    raw_ch_b: int,
    dv_dim: int,
    dv_bw_ps: int,
    fine_bin_ps: int,
    guard_bins: int,
    out_dir: Path,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)

    fine_dim = (dv_dim * dv_bw_ps) // fine_bin_ps
    frame_period_ps = dv_dim * dv_bw_ps

    print(f"  Loading tags...")
    cache_dir = out_dir / "_tag_cache"
    tags = load_tags(ttbin, cache_dir, raw_ch_a, raw_ch_b, None)
    print(f"    A={tags.t_a.size:,}, B={tags.t_b.size:,}")

    tau_align_ps, tau_source = infer_tau_align(peaks_csv, None, None)
    print(f"  tau_align_ps={tau_align_ps:.0f} (source: {tau_source})")

    peaks_raw = load_peaks(peaks_csv)
    selected, excluded = filter_peaks(peaks_raw, tau_align_ps, PROMINENCE)
    print(f"  Peaks: selected={len(selected)}, excluded={len(excluded)}")

    for p in selected:
        p["fwhm_ps"] = estimate_fwhm_from_histogram(delay_csv, float(p.get("delay_ps", 0)), dv_bw_ps)
    compute_roi_half_widths(selected, dv_bw_ps)

    # Override ROI with wider multiplier (0.6× vs default 0.4×) for better pseudo-CV contrast
    if len(selected) >= 2:
        delays = sorted(float(p["tau_residual_ps"]) for p in selected)
        tooth_spacing_ps = float(np.median(np.diff(delays)))
    else:
        tooth_spacing_ps = float(dv_dim) * float(dv_bw_ps)
    for p in selected:
        fwhm = float(p.get("fwhm_ps", dv_bw_ps * 3))
        p["roi_half_ps"] = min(
            int(np.floor(0.6 * tooth_spacing_ps)),
            max(3 * dv_bw_ps, int(np.ceil(1.5 * fwhm / 2))),
        )

    for p in selected:
        print(f"    {p['peak_id']}: tau_raw={float(p.get('delay_ps', 0)):+.0f}ps "
              f"roi_half={p['roi_half_ps']}ps fwhm={p['fwhm_ps']:.0f}ps")

    print(f"  Generating candidates (comb)...")
    candidates = generate_candidates(tags.t_a, tags.t_b, selected, tau_align_ps, mode='comb')
    print(f"    candidates: {len(candidates):,}")

    print(f"  Greedy-unique pairing...")
    accepted, greedy_meta = global_greedy_unique(candidates)
    print(f"    accepted: {greedy_meta['accepted_pair_count_total']:,}")

    print(f"  Building JTI at {fine_bin_ps}ps resolution (dim={fine_dim})...")
    H, jti_meta = build_jti(
        accepted, tags.t_a, tags.t_b, tau_align_ps,
        bw=fine_bin_ps, dim=fine_dim, origin_ps=0, guard_bins=guard_bins,
    )
    print(f"    retained: {jti_meta['retained_in_jti']:,}")

    diag = compute_residual_diagnostics(H, fine_bin_ps)

    csv_path = out_dir / f"pseudo_cv_{fine_bin_ps}ps.csv"
    save_csv_matrix(csv_path, H, fine_bin_ps)
    print(f"    Saved CSV: {csv_path}")

    png_path = out_dir / f"pseudo_cv_{fine_bin_ps}ps.png"
    save_png(
        png_path, H,
        dv_dim=dv_dim,
        fine_dim=fine_dim,
        fine_bin_ps=fine_bin_ps,
        frame_period_ps=frame_period_ps,
        title=(
            f"Pseudo-CV | dim={dv_dim} bw={dv_bw_ps}ps -> {fine_dim}x{fine_bin_ps}ps\n"
            f"peaks={len(selected)} accepted={len(accepted):,} retained={jti_meta['retained_in_jti']:,}"
        ),
    )
    print(f"    Saved PNG: {png_path}")

    meta = {
        "input_ttbin": str(ttbin),
        "input_peaks_csv": str(peaks_csv),
        "input_delay_csv": str(delay_csv),
        "tau_align_ps": tau_align_ps,
        "tau_align_source": tau_source,
        "prominence_fraction": PROMINENCE,
        "selected_peaks": len(selected),
        "excluded_peaks": len(excluded),
        "dv_dim": dv_dim,
        "dv_bw_ps": dv_bw_ps,
        "frame_period_ps": frame_period_ps,
        "fine_bin_ps": fine_bin_ps,
        "fine_dim": fine_dim,
        "guard_bins": guard_bins,
        "raw_ch_a": raw_ch_a,
        "raw_ch_b": raw_ch_b,
        "candidate_count": len(candidates),
        "greedy_accepted": greedy_meta["accepted_pair_count_total"],
        "greedy_meta": greedy_meta,
        "jti_meta": jti_meta,
        "residual_diagnostics": diag,
        "peaks": [
            {
                "peak_id": p.get("peak_id"),
                "tau_raw_ps": float(p.get("delay_ps", 0)),
                "tau_residual_ps": float(p["tau_residual_ps"]),
                "roi_half_ps": int(p["roi_half_ps"]),
                "fwhm_ps": float(p["fwhm_ps"]),
            }
            for p in selected
        ],
    }
    meta_path = out_dir / f"pseudo_cv_{fine_bin_ps}ps.meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")

    return meta


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Pseudo-CV heatmap from modeB peak-aware pairing.")
    ap.add_argument("--ttbin", required=True)
    ap.add_argument("--peaks-csv", required=True)
    ap.add_argument("--delay-csv", required=True)
    ap.add_argument("--raw-ch-a-id", type=int, default=2)
    ap.add_argument("--raw-ch-b-id", type=int, default=3)
    ap.add_argument("--dv-dim", type=int, required=True, help="DV dimension (e.g. 128)")
    ap.add_argument("--dv-bw-ps", type=int, required=True, help="DV binwidth in ps (e.g. 40 or 50)")
    ap.add_argument("--fine-bin-ps", type=int, default=20, help="Fine bin size in ps for pseudo-CV (default: 20)")
    ap.add_argument("--guard-bins", type=int, default=2)
    ap.add_argument("--out", required=True)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    ttbin = Path(args.ttbin)
    if not ttbin.exists():
        print(f"ERROR: ttbin not found: {ttbin}")
        return 1

    t0 = time.time()
    meta = run_one(
        ttbin=ttbin,
        peaks_csv=Path(args.peaks_csv),
        delay_csv=Path(args.delay_csv),
        raw_ch_a=int(args.raw_ch_a_id),
        raw_ch_b=int(args.raw_ch_b_id),
        dv_dim=int(args.dv_dim),
        dv_bw_ps=int(args.dv_bw_ps),
        fine_bin_ps=int(args.fine_bin_ps),
        guard_bins=int(args.guard_bins),
        out_dir=Path(args.out),
    )
    elapsed = time.time() - t0
    print(f"  Done in {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
