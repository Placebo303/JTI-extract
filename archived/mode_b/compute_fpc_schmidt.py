#!/usr/bin/env python3
"""FPC comb-tooth Schmidt-like effective mode number analysis.

Peak-aware greedy-unique pairing with true-coordinate, unwrapped,
edge-guarded, non-cyclic JTI construction.

Three JTI types (each with independent greedy-unique):
  H_full_window  – full selected comb delay range, greedy-unique
  H_comb         – tooth ROI union, greedy-unique
  H_tooth_m      – per-tooth ROI, greedy-unique

All coordinates unified:
  t_b_corr = t_b - tau_align_ps
  residual_tau = t_b_corr - t_a

Schmidt-like computation:
  P = H / sum(H), A = sqrt(P), SVD(A)
  lambda_n = s_n^2 / sum(s_n^2), K = 1 / sum(lambda_n^2)
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jti_extract.cli.tdc_layer_scan import Tags, load_tags


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CandidatePair:
    a_idx: int
    b_idx: int
    tau_raw: int
    residual_tau: int
    score: float
    peak_id: str


@dataclass
class SchmidtResult:
    K: float
    purity: float
    n_singular_values: int
    total_counts: int
    singular_values: list[float]
    lambda_weights: list[float]


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


def infer_tau_align(peaks_csv: Path, args_tau_align: float | None, args_tau0: float | None) -> tuple[float, str]:
    """Resolve tau_align_ps with priority: explicit > peaks_csv max-count > tau0 fallback."""
    if args_tau_align is not None:
        return float(args_tau_align), "explicit"

    peaks = load_peaks(peaks_csv)
    if peaks:
        max_peak = max(peaks, key=lambda p: float(p.get("counts", 0)))
        delay = float(max_peak.get("delay_ps", 0))
        if delay != 0:
            return delay, "peaks_csv_max_count_peak"

    if args_tau0 is not None:
        return float(args_tau0), "tau0_fallback"

    raise SystemExit("Must provide --tau-align-ps, or --tau0-ps, or peaks_csv with valid peaks")


def filter_peaks(
    peaks: list[dict[str, Any]],
    tau_align_ps: float,
    prominence_fraction: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not peaks:
        return [], []
    max_count = max(float(p.get("counts", 0)) for p in peaks)
    threshold = prominence_fraction * max_count
    selected: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for p in peaks:
        counts = float(p.get("counts", 0))
        tau_raw = float(p.get("delay_ps", 0))
        p["tau_residual_ps"] = tau_raw - tau_align_ps
        p["peak_id"] = f"p{len(selected)}"
        if counts >= threshold:
            selected.append(p)
        else:
            excluded.append(p)
    selected.sort(key=lambda r: float(r.get("tau_residual_ps", 0)))
    return selected, excluded


# ---------------------------------------------------------------------------
# FWHM estimation
# ---------------------------------------------------------------------------

def estimate_fwhm_from_histogram(delay_csv: Path, tau_center_ps: float, bw: int) -> float:
    delays: list[float] = []
    counts: list[float] = []
    with delay_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            delays.append(float(row["delay_ps"]))
            counts.append(float(row["counts"]))
    delays_arr = np.array(delays)
    counts_arr = np.array(counts)
    idx = int(np.argmin(np.abs(delays_arr - tau_center_ps)))
    peak_val = counts_arr[idx]
    if peak_val <= 0:
        return float(bw) * 3
    half_max = peak_val / 2.0
    left_idx = idx
    while left_idx > 0 and counts_arr[left_idx] >= half_max:
        left_idx -= 1
    right_idx = idx
    while right_idx < len(counts_arr) - 1 and counts_arr[right_idx] >= half_max:
        right_idx += 1
    fwhm_ps = float(abs(delays_arr[right_idx] - delays_arr[left_idx]))
    if fwhm_ps < bw:
        fwhm_ps = float(bw) * 2
    return fwhm_ps


def compute_roi_half_widths(peaks: list[dict[str, Any]], bw: int) -> None:
    if len(peaks) < 2:
        for p in peaks:
            fwhm = float(p.get("fwhm_ps", bw * 3))
            p["roi_half_ps"] = min(
                int(np.floor(0.4 * bw * 128)),
                max(3 * bw, int(np.ceil(1.5 * fwhm / 2))),
            )
        return
    delays = sorted(float(p["tau_residual_ps"]) for p in peaks)
    spacings = np.diff(delays)
    tooth_spacing_ps = float(np.median(spacings))
    for p in peaks:
        fwhm = float(p.get("fwhm_ps", bw * 3))
        p["roi_half_ps"] = min(
            int(np.floor(0.4 * tooth_spacing_ps)),
            max(3 * bw, int(np.ceil(1.5 * fwhm / 2))),
        )


# ---------------------------------------------------------------------------
# Candidate generation
# ---------------------------------------------------------------------------

def generate_candidates(
    t_a: np.ndarray,
    t_b: np.ndarray,
    peaks: list[dict[str, Any]],
    tau_align_ps: float,
    *,
    mode: str,
) -> list[CandidatePair]:
    """Generate candidate pairs.

    mode='comb': only pairs falling within any tooth ROI
    mode='full': pairs within full min/max residual tau range
    """
    tau_align = np.int64(int(tau_align_ps))
    t_b_corr = t_b - tau_align
    candidates: list[CandidatePair] = []
    CHUNK = 50_000

    if mode == 'comb':
        for peak in peaks:
            tau_raw_center = np.int64(int(float(peak.get("delay_ps", 0))))
            tau_res_center = float(peak["tau_residual_ps"])
            roi_half = np.int64(int(peak["roi_half_ps"]))
            peak_id = str(peak.get("peak_id", ""))

            for start in range(0, t_a.size, CHUNK):
                a_chunk = t_a[start:start + CHUNK]
                a_indices = np.arange(start, min(start + CHUNK, t_a.size))

                left = np.searchsorted(t_b, a_chunk + tau_raw_center - roi_half, side="left")
                right = np.searchsorted(t_b, a_chunk + tau_raw_center + roi_half, side="right")

                for k_idx in range(a_chunk.size):
                    lo, hi = int(left[k_idx]), int(right[k_idx])
                    if lo >= hi:
                        continue
                    a_val = int(a_chunk[k_idx])
                    a_idx = int(a_indices[k_idx])
                    for b_idx in range(lo, hi):
                        b_val = int(t_b[b_idx])
                        tau_raw = b_val - a_val
                        residual_tau = int(t_b_corr[b_idx]) - a_val
                        score = abs(residual_tau - tau_res_center)
                        candidates.append(CandidatePair(
                            a_idx=a_idx, b_idx=b_idx,
                            tau_raw=tau_raw, residual_tau=residual_tau,
                            score=float(score), peak_id=peak_id,
                        ))

    elif mode == 'full':
        full_min = min(float(p["tau_residual_ps"]) - int(p["roi_half_ps"]) for p in peaks)
        full_max = max(float(p["tau_residual_ps"]) + int(p["roi_half_ps"]) for p in peaks)
        tau_res_centers = {str(p.get("peak_id", "")): float(p["tau_residual_ps"]) for p in peaks}

        for start in range(0, t_a.size, CHUNK):
            a_chunk = t_a[start:start + CHUNK]
            a_indices = np.arange(start, min(start + CHUNK, t_a.size))

            # Search in raw tau space: full_min to full_max around t_a
            raw_min = np.int64(int(math.floor(full_min)))
            raw_max = np.int64(int(math.ceil(full_max)))
            left = np.searchsorted(t_b, a_chunk + raw_min, side="left")
            right = np.searchsorted(t_b, a_chunk + raw_max, side="right")

            for k_idx in range(a_chunk.size):
                lo, hi = int(left[k_idx]), int(right[k_idx])
                if lo >= hi:
                    continue
                a_val = int(a_chunk[k_idx])
                a_idx = int(a_indices[k_idx])
                for b_idx in range(lo, hi):
                    b_val = int(t_b[b_idx])
                    residual_tau = int(t_b_corr[b_idx]) - a_val
                    # Find nearest peak for assignment
                    best_peak_id = ""
                    best_score = float("inf")
                    for pid, tau_res in tau_res_centers.items():
                        s = abs(residual_tau - tau_res)
                        if s < best_score:
                            best_score = s
                            best_peak_id = pid
                    # Include ALL pairs in the full range (no ROI filtering)
                    tau_raw = b_val - a_val
                    candidates.append(CandidatePair(
                        a_idx=a_idx, b_idx=b_idx,
                        tau_raw=tau_raw, residual_tau=residual_tau,
                        score=best_score, peak_id=best_peak_id,
                    ))

    return candidates


# ---------------------------------------------------------------------------
# Global greedy unique
# ---------------------------------------------------------------------------

def global_greedy_unique(
    candidates: list[CandidatePair],
    used_a: set[int] | None = None,
    used_b: set[int] | None = None,
) -> tuple[list[CandidatePair], dict[str, Any]]:
    """Deterministic greedy unique: sort by (score, peak_id, a_idx, b_idx).

    If used_a/used_b are provided, those events are already consumed and
    cannot be used by new pairs (for comb+gap extension).
    """
    candidates.sort(key=lambda c: (c.score, c.peak_id, c.a_idx, c.b_idx))

    if used_a is None:
        used_a = set()
    else:
        used_a = set(used_a)  # copy to avoid mutating caller's set
    if used_b is None:
        used_b = set()
    else:
        used_b = set(used_b)

    accepted: list[CandidatePair] = []
    rejected_a = 0
    rejected_b = 0
    per_peak: dict[str, int] = {}

    for c in candidates:
        if c.a_idx in used_a:
            rejected_a += 1
            continue
        if c.b_idx in used_b:
            rejected_b += 1
            continue
        used_a.add(c.a_idx)
        used_b.add(c.b_idx)
        accepted.append(c)
        per_peak[c.peak_id] = per_peak.get(c.peak_id, 0) + 1

    return accepted, {
        "candidate_count_total": len(candidates),
        "accepted_pair_count_total": len(accepted),
        "rejected_due_to_a_reuse": rejected_a,
        "rejected_due_to_b_reuse": rejected_b,
        "accepted_pairs_per_peak": per_peak,
    }


# ---------------------------------------------------------------------------
# JTI construction
# ---------------------------------------------------------------------------

def build_jti(
    accepted: list[CandidatePair],
    t_a: np.ndarray,
    t_b: np.ndarray,
    tau_align_ps: float,
    *,
    bw: int,
    dim: int,
    origin_ps: int,
    guard_bins: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    """True-coordinate unwrapped edge-guarded JTI from accepted pairs."""
    origin = np.int64(origin_ps)
    tau_align = np.int64(int(tau_align_ps))
    bw_i = np.int64(bw)
    frame_period = np.int64(dim) * bw_i
    guard_ps = np.int64(guard_bins) * bw_i

    H = np.zeros((dim, dim), dtype=np.float64)
    invalid_count = 0
    cross_frame_count = 0
    edge_rejected_count = 0

    for p in accepted:
        a_val = np.int64(t_a[p.a_idx])
        b_val = np.int64(t_b[p.b_idx])

        ua = a_val - origin
        ub = (b_val - tau_align) - origin

        frame_a = ua // frame_period
        frame_b = ub // frame_period

        if frame_a != frame_b:
            cross_frame_count += 1
            continue

        xa = ua - frame_a * frame_period
        xb = ub - frame_a * frame_period

        if xa < guard_ps or xa >= frame_period - guard_ps:
            edge_rejected_count += 1
            continue
        if xb < guard_ps or xb >= frame_period - guard_ps:
            edge_rejected_count += 1
            continue

        i = int(xa // bw_i)
        j = int(xb // bw_i)

        if not (0 <= i < dim and 0 <= j < dim):
            invalid_count += 1
            continue

        H[i, j] += 1.0

    total_accepted = len(accepted)
    retained = int(np.sum(H))
    return H, {
        "accepted_pairs_input": total_accepted,
        "cross_frame_rejected": cross_frame_count,
        "edge_rejected": edge_rejected_count,
        "invalid_bin": invalid_count,
        "retained_in_jti": retained,
        "retained_fraction": retained / total_accepted if total_accepted > 0 else 0.0,
    }


# ---------------------------------------------------------------------------
# Schmidt computation
# ---------------------------------------------------------------------------

def compute_schmidt(H: np.ndarray) -> SchmidtResult:
    """Compute Schmidt-like K from JTI matrix.

    P = H / sum(H), A = sqrt(P), SVD(A)
    lambda_n = s_n^2 / sum(s_n^2), K = 1 / sum(lambda_n^2)
    """
    total = float(np.sum(H))
    if total <= 0 or not np.isfinite(total):
        return SchmidtResult(K=float("nan"), purity=float("nan"), n_singular_values=0,
                             total_counts=0, singular_values=[], lambda_weights=[])
    P = H / total
    A = np.sqrt(P)
    s = np.linalg.svd(A, compute_uv=False)
    s = s[s > 1e-12]
    if s.size == 0:
        return SchmidtResult(K=float("nan"), purity=float("nan"), n_singular_values=0,
                             total_counts=int(total), singular_values=[], lambda_weights=[])
    weights = s ** 2
    weights = weights / np.sum(weights)
    purity = float(np.sum(weights ** 2))
    K = float(1.0 / purity)
    return SchmidtResult(
        K=K, purity=purity, n_singular_values=int(s.size), total_counts=int(total),
        singular_values=s.tolist(), lambda_weights=weights.tolist(),
    )


def compute_residual_diagnostics(H: np.ndarray, bw: int) -> dict[str, Any]:
    dim = H.shape[0]
    i_idx, j_idx = np.meshgrid(np.arange(dim), np.arange(dim), indexing='ij')
    delta = j_idx - i_idx
    total = float(np.sum(H))
    if total <= 0:
        return {"weighted_mean_residual_tau_ps": 0.0, "weighted_std_residual_tau_ps": 0.0,
                "offset_min_ps": 0, "offset_max_ps": 0}
    mean_offset = float(np.sum(H * delta) / total)
    std_offset = float(np.sqrt(np.sum(H * (delta - mean_offset) ** 2) / total))
    nonzero = H > 0
    return {
        "weighted_mean_residual_tau_ps": round(mean_offset * bw, 2),
        "weighted_std_residual_tau_ps": round(std_offset * bw, 2),
        "offset_min_ps": int(delta[nonzero].min()) * bw if np.any(nonzero) else 0,
        "offset_max_ps": int(delta[nonzero].max()) * bw if np.any(nonzero) else 0,
    }


def compute_comb_weight(counts_dict: dict[str, int]) -> float:
    counts = np.array(list(counts_dict.values()), dtype=np.float64)
    total = float(np.sum(counts))
    if total <= 0:
        return float("nan")
    p_m = counts / total
    return float(1.0 / np.sum(p_m ** 2))


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def run_analysis(args: argparse.Namespace) -> dict[str, Any]:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    bw = int(args.binwidth_ps)
    dim = int(args.dimensions)
    guard_bins = int(args.guard_bins)
    origin_ps = int(args.frame_origin_ps)

    # 1. Load timetags
    ttbin = Path(args.ttbin)
    cache_dir = out_dir / "_tag_cache"
    tags = load_tags(ttbin, cache_dir, int(args.raw_ch_a_id), int(args.raw_ch_b_id), args.max_events)
    if tags.t_a.size == 0 or tags.t_b.size == 0:
        raise RuntimeError(f"No events found in {ttbin}")
    print(f"Loaded {tags.t_a.size:,} A events, {tags.t_b.size:,} B events from {ttbin.name}")

    # 2. Resolve tau_align_ps
    peaks_csv = Path(args.peaks_csv)
    delay_csv = Path(args.delay_csv)
    tau_align_ps, tau_align_source = infer_tau_align(peaks_csv, args.tau_align_ps, args.tau0_ps)
    print(f"tau_align_ps = {tau_align_ps:.0f} (source: {tau_align_source})")

    # 3. Load and filter peaks
    peaks_raw = load_peaks(peaks_csv)
    print(f"Loaded {len(peaks_raw)} peaks from {peaks_csv.name}")

    prominence_fractions = [float(x) for x in str(args.prominence_fractions).split(",")]
    primary_prom = float(args.primary_prominence)
    results_by_prom: dict[str, dict[str, Any]] = {}

    for prom in prominence_fractions:
        prom_key = f"{prom:.2f}"
        print(f"\n--- prominence_fraction = {prom} ---")

        selected, excluded = filter_peaks(peaks_raw, tau_align_ps, prom)
        print(f"  Selected {len(selected)} peaks, excluded {len(excluded)}")

        if not selected:
            results_by_prom[prom_key] = {
                "K_full_window_greedy_unique_raw": float("nan"),
                "K_global_comb_raw": float("nan"),
                "K_comb_weight": float("nan"),
                "K_tooth_raw": [],
                "selected_tooth_count": 0,
                "excluded_peaks": [
                    {"peak_id": str(p.get("peak_id", "")), "reason": "below_prominence_threshold",
                     "counts": float(p.get("counts", 0))} for p in excluded
                ],
            }
            continue

        # FWHM + ROI widths
        for p in selected:
            tau_raw = float(p.get("delay_ps", 0))
            p["fwhm_ps"] = estimate_fwhm_from_histogram(delay_csv, tau_raw, bw)
        compute_roi_half_widths(selected, bw)

        for p in selected:
            print(f"  {p['peak_id']}: tau_raw={float(p.get('delay_ps', 0)):+.0f}ps "
                  f"tau_res={p['tau_residual_ps']:+.0f}ps "
                  f"roi_half={p['roi_half_ps']}ps fwhm={p['fwhm_ps']:.0f}ps")

        # 4. Generate candidates: comb mode
        print("  Generating comb candidates...")
        candidate_comb = generate_candidates(tags.t_a, tags.t_b, selected, tau_align_ps, mode='comb')
        print(f"    comb candidates: {len(candidate_comb):,}")

        # 5. Generate candidates: full mode
        print("  Generating full-window candidates...")
        candidate_full = generate_candidates(tags.t_a, tags.t_b, selected, tau_align_ps, mode='full')
        print(f"    full candidates: {len(candidate_full):,}")

        # 6. Global greedy unique: comb
        print("  Running greedy-unique (comb)...")
        accepted_comb, greedy_meta_comb = global_greedy_unique(candidate_comb)
        print(f"    accepted: {greedy_meta_comb['accepted_pair_count_total']:,}")

        # 7. Comb+gap extension for H_full_window
        # Gap candidates = full candidates not in comb candidate set
        print("  Running greedy-unique (comb+gap extension for full window)...")
        comb_pair_set = {(c.a_idx, c.b_idx) for c in candidate_comb}
        gap_candidates = [c for c in candidate_full if (c.a_idx, c.b_idx) not in comb_pair_set]
        print(f"    gap candidates: {len(gap_candidates):,}")

        # Greedy on gap, inheriting used_a/used_b from accepted_comb
        used_a_comb = {p.a_idx for p in accepted_comb}
        used_b_comb = {p.b_idx for p in accepted_comb}
        accepted_gap, greedy_meta_gap = global_greedy_unique(gap_candidates, used_a_comb, used_b_comb)
        print(f"    gap accepted: {greedy_meta_gap['accepted_pair_count_total']:,}")

        # Combine: accepted_full = accepted_comb + accepted_gap
        accepted_full = accepted_comb + accepted_gap
        print(f"    total accepted_full: {len(accepted_full):,}")

        # Assertions (candidate_full may be < candidate_comb due to comb having
        # duplicate pairs across overlapping peak ROIs; the meaningful assertion
        # is on accepted_full and on H sums after JTI construction)
        assert len(accepted_full) >= len(accepted_comb), \
            f"accepted_full ({len(accepted_full)}) < accepted_comb ({len(accepted_comb)})"

        # 8. Build JTIs
        print("  Building H_comb...")
        H_comb, comb_jti_meta = build_jti(
            accepted_comb, tags.t_a, tags.t_b, tau_align_ps,
            bw=bw, dim=dim, origin_ps=origin_ps, guard_bins=guard_bins,
        )
        print(f"    retained: {comb_jti_meta['retained_in_jti']:,}")

        print("  Building H_full_window...")
        H_full, full_jti_meta = build_jti(
            accepted_full, tags.t_a, tags.t_b, tau_align_ps,
            bw=bw, dim=dim, origin_ps=origin_ps, guard_bins=guard_bins,
        )
        print(f"    retained: {full_jti_meta['retained_in_jti']:,}")

        # Assert H_full_window >= H_comb
        sum_comb = int(np.sum(H_comb))
        sum_full = int(np.sum(H_full))
        assert sum_full >= sum_comb, \
            f"sum(H_full_window)={sum_full} < sum(H_comb)={sum_comb}"
        print(f"    assertion OK: sum(H_full)={sum_full} >= sum(H_comb)={sum_comb}")

        # 9. Build per-tooth JTIs
        print("  Building per-tooth JTIs...")
        H_tooth: dict[str, np.ndarray] = {}
        tooth_jti_meta: dict[str, dict] = {}
        tooth_groups: dict[str, list[CandidatePair]] = {}
        for p in accepted_comb:
            if p.peak_id not in tooth_groups:
                tooth_groups[p.peak_id] = []
            tooth_groups[p.peak_id].append(p)

        for peak_id, pairs in tooth_groups.items():
            H_m, meta_m = build_jti(
                pairs, tags.t_a, tags.t_b, tau_align_ps,
                bw=bw, dim=dim, origin_ps=origin_ps, guard_bins=guard_bins,
            )
            H_tooth[peak_id] = H_m
            tooth_jti_meta[peak_id] = meta_m

        # 10. Schmidt computations
        K_comb = compute_schmidt(H_comb)
        K_full = compute_schmidt(H_full)
        K_tooth_results: dict[str, SchmidtResult] = {}
        for pid, H_m in H_tooth.items():
            K_tooth_results[pid] = compute_schmidt(H_m)

        # 11. Residual diagnostics
        diag_comb = compute_residual_diagnostics(H_comb, bw)
        diag_full = compute_residual_diagnostics(H_full, bw)
        diag_tooth: dict[str, dict] = {}
        for pid, H_m in H_tooth.items():
            diag_tooth[pid] = compute_residual_diagnostics(H_m, bw)

        # 12. K_comb_weight (using retained counts from H_tooth)
        counts_per_tooth = {pid: int(np.sum(H_m)) for pid, H_m in H_tooth.items()}
        K_comb_weight = compute_comb_weight(counts_per_tooth)

        # 13. Statistics
        min_counts_included = int(args.min_counts_included)
        min_counts_warning = int(args.min_counts_warning)

        tooth_results_list: list[dict[str, Any]] = []
        for peak in selected:
            pid = str(peak.get("peak_id", ""))
            K_m = K_tooth_results.get(pid)
            counts_m = counts_per_tooth.get(pid, 0)
            low_count = counts_m < min_counts_warning
            tooth_results_list.append({
                "peak_id": pid,
                "tau_raw_ps": float(peak.get("delay_ps", 0)),
                "tau_residual_ps": float(peak["tau_residual_ps"]),
                "roi_half_ps": int(peak["roi_half_ps"]),
                "fwhm_ps": float(peak["fwhm_ps"]),
                "counts_in_roi": counts_m,
                "K_tooth": K_m.K if K_m else float("nan"),
                "purity": K_m.purity if K_m else float("nan"),
                "n_singular_values": K_m.n_singular_values if K_m else 0,
                "low_count_warning": low_count,
            })

        valid_K = [r["K_tooth"] for r in tooth_results_list
                   if not r["low_count_warning"] and np.isfinite(r["K_tooth"])
                   and r["counts_in_roi"] >= min_counts_included]
        all_K = [r["K_tooth"] for r in tooth_results_list if np.isfinite(r["K_tooth"])]

        def _mean_safe(vals):
            return float(np.mean(vals)) if vals else float("nan")

        def _median_safe(vals):
            return float(np.median(vals)) if vals else float("nan")

        def _std_safe(vals):
            return float(np.std(vals)) if vals else float("nan")

        result = {
            "K_full_window_greedy_unique_raw": K_full.K,
            "K_full_window_interpretation": "operational one-to-one K over the full selected comb delay range; not all-pairs background-inclusive K",
            "K_global_comb_raw": K_comb.K,
            "K_comb_weight": K_comb_weight,

            "K_tooth_raw": [r["K_tooth"] for r in tooth_results_list],
            "mean_K_tooth_included": _mean_safe(valid_K),
            "median_K_tooth_included": _median_safe(valid_K),
            "std_K_tooth_included": _std_safe(valid_K),
            "mean_K_tooth_all": _mean_safe(all_K),
            "median_K_tooth_all": _median_safe(all_K),
            "std_K_tooth_all": _std_safe(all_K),

            "selected_tooth_count": len(selected),
            "included_tooth_count": len(valid_K),
            "excluded_tooth_count_low_count": sum(1 for r in tooth_results_list if r["low_count_warning"]),

            "excluded_peaks": [
                {"peak_id": str(p.get("peak_id", "")), "reason": "below_prominence_threshold",
                 "counts": float(p.get("counts", 0))} for p in excluded
            ],

            "tooth_details": tooth_results_list,

            "pairing_diagnostics": {
                "comb": greedy_meta_comb,
                "gap": greedy_meta_gap,
                "full_summary": {
                    "candidate_count_comb": len(candidate_comb),
                    "candidate_count_full": len(candidate_full),
                    "candidate_count_gap": len(gap_candidates),
                    "accepted_pair_count_comb": greedy_meta_comb["accepted_pair_count_total"],
                    "accepted_pair_count_gap": greedy_meta_gap["accepted_pair_count_total"],
                    "accepted_pair_count_full": len(accepted_full),
                },
            },
            "per_peak_unwrap_diagnostics": tooth_jti_meta,
            "comb_jti_meta": comb_jti_meta,
            "full_jti_meta": full_jti_meta,

            "residual_tau_diagnostics": {
                "H_comb": diag_comb,
                "H_full_window": diag_full,
                "per_tooth": diag_tooth,
            },
        }

        results_by_prom[prom_key] = result

        # Save CSVs for primary prominence
        if abs(prom - primary_prom) < 1e-6:
            for pid, H_m in H_tooth.items():
                _write_csv_matrix(out_dir / f"per_tooth_svd_input_{pid}.csv", H_m)
            _write_csv_matrix(out_dir / "H_full_window.csv", H_full)
            _write_csv_matrix(out_dir / "H_comb.csv", H_comb)

            # Singular values CSVs
            _write_csv_rows(out_dir / "singular_values_H_comb.csv",
                            ["index", "singular_value", "lambda"],
                            [{"index": i, "singular_value": sv, "lambda": lam}
                             for i, (sv, lam) in enumerate(zip(K_comb.singular_values, K_comb.lambda_weights))])
            _write_csv_rows(out_dir / "singular_values_H_full_window.csv",
                            ["index", "singular_value", "lambda"],
                            [{"index": i, "singular_value": sv, "lambda": lam}
                             for i, (sv, lam) in enumerate(zip(K_full.singular_values, K_full.lambda_weights))])

            # tooth_details.csv
            _write_csv_rows(
                out_dir / "tooth_details.csv",
                ["peak_id", "tau_raw_ps", "tau_residual_ps", "roi_half_ps", "fwhm_ps",
                 "counts_in_roi", "K_tooth", "purity", "n_singular_values", "low_count_warning"],
                tooth_results_list,
            )

            # Standalone pairing_diagnostics.json
            pairing_diag_path = out_dir / "pairing_diagnostics.json"
            pairing_diag_path.write_text(json.dumps(
                result["pairing_diagnostics"], ensure_ascii=False, indent=2, default=_json_default),
                encoding="utf-8")

            # summary.csv
            _valid_tooth = [(r["K_tooth"], r["counts_in_roi"]) for r in tooth_results_list
                            if np.isfinite(r["K_tooth"]) and r["counts_in_roi"] > 0]
            K_tw_mean = float("nan")
            if _valid_tooth:
                _total_c = sum(c for _, c in _valid_tooth)
                if _total_c > 0:
                    K_tw_mean = sum(k * c for k, c in _valid_tooth) / _total_c
            summary_row = {
                "analysis_mode": "bfc_multiline_jti",
                "binwidth_ps": bw, "dim": dim, "guard_bins": guard_bins,
                "tau_align_ps": tau_align_ps,
                "K_global_comb_raw": K_comb.K,
                "K_comb_weight": K_comb_weight,
                "K_full_window_greedy_unique_raw": K_full.K,
                "K_tooth_mean": result.get("mean_K_tooth_included", float("nan")),
                "K_tooth_median": result.get("median_K_tooth_included", float("nan")),
                "K_tooth_weighted_mean": K_tw_mean,
                "selected_tooth_count": len(selected),
                "included_tooth_count": len(valid_K),
                "sum_H_comb": int(np.sum(H_comb)),
                "sum_H_full_window": int(np.sum(H_full)),
                "candidate_count_comb": len(candidate_comb),
                "candidate_count_full": len(candidate_full),
                "accepted_pair_count_comb": greedy_meta_comb["accepted_pair_count_total"],
                "accepted_pair_count_full": len(accepted_full),
            }
            _write_csv_rows(out_dir / "summary.csv", list(summary_row.keys()), [summary_row])

    # Final output
    primary = results_by_prom.get(f"{primary_prom:.2f}", {})

    # Compute K_tooth_weighted_mean for final output
    _K_tooth_raw = primary.get("K_tooth_raw", [])
    _tooth_details = primary.get("tooth_details", [])
    _K_tw = float("nan")
    if _K_tooth_raw and _tooth_details:
        _counts = [r.get("counts_in_roi", 0) for r in _tooth_details]
        # Skip nan K values in weighted mean
        _valid_pairs = [(k, c) for k, c in zip(_K_tooth_raw, _counts)
                        if np.isfinite(k) and c > 0]
        _total_c = sum(c for _, c in _valid_pairs)
        if _total_c > 0 and _valid_pairs:
            _K_tw = sum(k * c for k, c in _valid_pairs) / _total_c

    output = {
        "analysis_mode": "bfc_multiline_jti",
        "result_type": "background-unsubtracted intensity-based Schmidt-like effective mode number",
        "strict_schmidt_number": False,
        "uses_complex_phase": False,
        "background_subtracted": False,
        "amplitude_proxy": "sqrt(normalized_intensity)",
        "analysis_stage": "JTI_stage_temporal_domain_BFC_characterization",
        "future_stage": "JSI_frequency_domain_BFC_characterization",

        "pairing_mode": "peak_aware_greedy_unique",
        "peak_tau_coordinate": "raw",
        "tau_align_ps_resolved": tau_align_ps,
        "tau_align_source": tau_align_source,
        "tau_coordinate_for_roi": "residual_tau = (t_B - tau_align_ps) - t_A",

        "K_full_window_greedy_unique_raw": primary.get("K_full_window_greedy_unique_raw", float("nan")),
        "H_full_window_interpretation": "operational one-to-one K over the full selected comb delay range; not all-pairs background-inclusive K",
        "K_global_comb_raw": primary.get("K_global_comb_raw", float("nan")),
        "K_comb_weight": primary.get("K_comb_weight", float("nan")),
        "K_tooth_raw": _K_tooth_raw,
        "K_tooth_weighted_mean": _K_tw,
        "mean_K_tooth_included": primary.get("mean_K_tooth_included", float("nan")),
        "median_K_tooth_included": primary.get("median_K_tooth_included", float("nan")),
        "std_K_tooth_included": primary.get("std_K_tooth_included", float("nan")),
        "mean_K_tooth_all": primary.get("mean_K_tooth_all", float("nan")),
        "median_K_tooth_all": primary.get("median_K_tooth_all", float("nan")),
        "std_K_tooth_all": primary.get("std_K_tooth_all", float("nan")),

        "selected_tooth_count": primary.get("selected_tooth_count", 0),
        "included_tooth_count": primary.get("included_tooth_count", 0),
        "excluded_tooth_count_low_count": primary.get("excluded_tooth_count_low_count", 0),

        "excluded_peaks": primary.get("excluded_peaks", []),
        "tooth_details": primary.get("tooth_details", []),

        "H_full_window_pairing_mode": "peak_aware_greedy_unique_comb_plus_gap_extension",
        "H_comb_pairing_mode": "peak_aware_greedy_unique_tooth_roi_union",
        "unique_constraint_scope": "within_each_matrix",

        "global_comb_construction": "greedy_unique_pairs_in_tooth_roi_union",
        "full_window_construction": "accepted_comb plus greedy-unique gap candidates in full residual delay range",
        "double_count_policy": "one_A_and_one_B_used_at_most_once_globally",
        "p_m_source": "accepted_peak_aware_greedy_unique_pairs_retained_after_edge_guard",

        "pairing_diagnostics": primary.get("pairing_diagnostics", {}),
        "per_peak_unwrap_diagnostics": primary.get("per_peak_unwrap_diagnostics", {}),
        "comb_jti_meta": primary.get("comb_jti_meta", {}),
        "full_jti_meta": primary.get("full_jti_meta", {}),
        "residual_tau_diagnostics": primary.get("residual_tau_diagnostics", {}),

        "sensitivity_analysis": results_by_prom,

        "interpretation": {
            "K_global_comb_raw": "global JTI-based temporal Schmidt-like effective mode number over selected comb-support ROI",
            "K_comb_weight": "effective number of retained comb/delay components",
            "K_tooth": "per-tooth local temporal Schmidt-like indicator",
            "K_full_window_greedy_unique_raw": "operational one-to-one effective mode number over the full selected comb delay range",
        },
        "not_final_BFC_total_schmidt_number": True,

        "guard_bins": guard_bins,
        "binwidth_ps": bw,
        "dimension": dim,
    }

    json_path = out_dir / "schmidt_results.json"
    json_path.write_text(json.dumps(output, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    print(f"\nSaved: {json_path}")

    return output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="FPC comb-tooth Schmidt-like effective mode number analysis.")
    ap.add_argument("--ttbin", required=True, help="Path to .1.ttbin file.")
    ap.add_argument("--raw-ch-a-id", type=int, default=2, help="TimeTagger channel A.")
    ap.add_argument("--raw-ch-b-id", type=int, default=3, help="TimeTagger channel B.")
    ap.add_argument("--peaks-csv", required=True, help="Path to pminus_peaks.csv.")
    ap.add_argument("--delay-csv", required=True, help="Path to pminus_delay_histogram.csv.")
    ap.add_argument("--tau0-ps", type=float, default=None, help="Backward-compatible shortcut for tau-align.")
    ap.add_argument("--tau-align-ps", type=float, default=None, help="B channel alignment correction (ps).")
    ap.add_argument("--frame-origin-ps", type=float, default=0.0, help="Frame origin (ps).")
    ap.add_argument("--binwidth-ps", type=int, default=20, help="Bin width (ps).")
    ap.add_argument("--dimensions", type=int, default=128, help="JTI dimension.")
    ap.add_argument("--guard-bins", type=int, default=2, help="Edge guard bins.")
    ap.add_argument("--min-counts-included", type=int, default=500, help="Min counts for included summary.")
    ap.add_argument("--min-counts-warning", type=int, default=10, help="Min counts for low_count_warning.")
    ap.add_argument("--prominence-fractions", default="0.02,0.04,0.08", help="Comma-separated prominence thresholds.")
    ap.add_argument("--primary-prominence", type=float, default=0.04, help="Primary prominence fraction.")
    ap.add_argument("--max-events", type=int, default=None, help="Max events to read.")
    ap.add_argument("--out", required=True, help="Output directory.")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_analysis(args)

    print("\n=== Schmidt Analysis Results ===")
    print(f"  K_full_window_greedy_unique_raw: {result['K_full_window_greedy_unique_raw']:.4f}")
    print(f"  K_global_comb_raw:               {result['K_global_comb_raw']:.4f}")
    print(f"  K_comb_weight:                   {result['K_comb_weight']:.4f}")
    print(f"  K_tooth_raw:                     {result['K_tooth_raw']}")
    print(f"  mean_K_tooth_included:           {result['mean_K_tooth_included']:.4f}")
    print(f"  selected_teeth:                  {result['selected_tooth_count']}")
    print(f"  included_teeth:                  {result['included_tooth_count']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
