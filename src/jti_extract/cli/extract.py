#!/usr/bin/env python3
"""
JTI extraction with CV/DV/SVD unwrapped output.

CV (continuous variable): fine-bin 2D histogram showing modulo-time distribution.
DV (divided variable): discrete JTI matrix for physical analysis.
SVD (unwrapped edge-guarded): non-cyclic finite-window JTI for Schmidt/SVD analysis.

Key features:
- Window bound to binwidth: window_ps = k * binwidth_ps
- No single-hit-per-frame filter (all_pairs_window mode)
- Explicit accidentals evaluation via B-channel delay
- Revised frame_origin scoring: score = diag_band_fraction - accidental_fraction
- Integer arithmetic throughout to avoid float64 precision loss on large timestamps
- Unwrapped edge-guarded JTI for SVD/Schmidt analysis (no wrap-around)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover
    np = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _RawTimetags:
    Ch: np.ndarray
    TimeTag: np.ndarray
    overflow_types: np.ndarray | None
    missed_events: np.ndarray | None
    acquisition_duration_s: float | None
    acquisition_duration_source: str | None


@dataclass(frozen=True)
class _CoincidenceResult:
    """Result of coincidence pairing."""
    t_a_paired: np.ndarray  # ps timestamps of A events in pairs
    t_b_paired: np.ndarray  # ps timestamps of B events in pairs
    n_events_a: int
    n_events_b: int
    window_ps: int
    pairing_mode: str
    allows_event_reuse: bool


@dataclass(frozen=True)
class _ScanResult:
    """Result of frame_origin scan for one k value."""
    k: int
    window_ps: int
    best_frame_origin_ps: float
    total_pairs: int
    diag_main_fraction: float
    diag_pm1_fraction: float
    offdiag_fraction: float
    diag_contrast: float
    accidental_fraction: float
    score: float
    scan_rows: list[dict]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _finite(x) -> bool:
    try:
        v = float(x)
    except Exception:
        return False
    return v == v and abs(v) != float("inf")


def _parse_int_list(text: str) -> list[int]:
    parts = [p.strip() for p in str(text).split(",") if p.strip()]
    out: list[int] = []
    for p in parts:
        out.append(int(p))
    if not out:
        raise ValueError("empty list")
    return out


def _normalize_path(raw: str) -> Path:
    s = str(raw).strip()
    is_windows_abs = len(s) >= 3 and s[1] == ":" and (s[2] == "\\" or s[2] == "/")
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


# ---------------------------------------------------------------------------
# IO: read ttbin / npz
# ---------------------------------------------------------------------------

def _read_ttbin_timetags(
    ttbin_path: Path,
    *,
    max_events: int | None,
    raw_ch_a_id: int,
    raw_ch_b_id: int,
    logical_ch_a: int,
    logical_ch_b: int,
) -> _RawTimetags:
    try:
        from TimeTagger import FileReader as TTFileReader  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "JTI extraction requires the Swabian Instruments `TimeTagger` Python API to parse *.ttbin.\n"
            f"Python={sys.executable} cannot import `TimeTagger`: {exc}\n"
        ) from exc

    channels: list[int] = []
    timestamps: list[int] = []
    event_types: list[int] = []
    missed: list[int] = []

    reader = TTFileReader(str(ttbin_path))
    while reader.hasData():
        data = reader.getData(1_000_000)
        ch = data.getChannels()
        ts = data.getTimestamps()
        et = data.getEventTypes()
        me = data.getMissedEvents()

        channels.extend(ch.tolist() if hasattr(ch, "tolist") else list(ch))
        timestamps.extend(ts.tolist() if hasattr(ts, "tolist") else list(ts))
        event_types.extend(et.tolist() if hasattr(et, "tolist") else list(et))
        if hasattr(me, "tolist"):
            me_list = me.tolist()
            missed.extend(me_list if isinstance(me_list, list) else [me_list])
        else:
            try:
                missed.extend(list(me))
            except Exception:
                missed.append(int(me))

        if max_events is not None and len(timestamps) >= int(max_events):
            break

    channel = np.asarray(channels, dtype=np.int64)
    overflow_types = np.asarray(event_types, dtype=np.int64)
    TimeTag = np.asarray(timestamps, dtype=np.int64)
    missed_events = np.asarray(missed)

    Ch = np.full(channel.shape, np.nan, dtype=float)
    valid = overflow_types == 0
    Ch[np.logical_and(valid, channel == int(raw_ch_a_id))] = float(int(logical_ch_a))
    Ch[np.logical_and(valid, channel == int(raw_ch_b_id))] = float(int(logical_ch_b))

    acquisition_duration_s = None
    acquisition_source = None
    try:
        if TimeTag.size > 0:
            span = int(max(0, int(np.max(TimeTag)) - int(np.min(TimeTag))))
            acquisition_duration_s = float(span) * 1e-12
            acquisition_source = f"derived_from_ttbin_span_ps:{ttbin_path}"
    except Exception:
        acquisition_duration_s = None

    return _RawTimetags(
        Ch=Ch,
        TimeTag=TimeTag,
        overflow_types=overflow_types,
        missed_events=missed_events,
        acquisition_duration_s=acquisition_duration_s,
        acquisition_duration_source=acquisition_source,
    )


def _read_npz_timebins(npz_path: Path) -> _RawTimetags:
    with np.load(str(npz_path), allow_pickle=False) as z:
        Ch = z["Ch"]
        TimeTag = z["TimeTag"]
        overflow_types = z["overflow_types"] if "overflow_types" in z else None
        missed_events = z["missed_events"] if "missed_events" in z else None

    Ch = np.asarray(Ch)
    TimeTag = np.asarray(TimeTag)

    acquisition_duration_s = None
    acquisition_source = None
    try:
        if TimeTag.size > 0:
            span = int(max(0, int(np.max(TimeTag)) - int(np.min(TimeTag))))
            acquisition_duration_s = float(span) * 1e-12
            acquisition_source = f"derived_from_npz_span_ps:{npz_path}"
    except Exception:
        acquisition_duration_s = None

    return _RawTimetags(
        Ch=Ch,
        TimeTag=TimeTag,
        overflow_types=np.asarray(overflow_types) if overflow_types is not None else None,
        missed_events=np.asarray(missed_events) if missed_events is not None else None,
        acquisition_duration_s=acquisition_duration_s,
        acquisition_duration_source=acquisition_source,
    )


def _load_timetags(
    *,
    ttbin: Path | None,
    max_events: int | None,
    raw_ch_a_id: int,
    raw_ch_b_id: int,
    logical_ch_a: int,
    logical_ch_b: int,
) -> tuple[_RawTimetags, Path | None, str]:
    if ttbin is not None and ttbin.exists():
        return (
            _read_ttbin_timetags(
                ttbin,
                max_events=max_events,
                raw_ch_a_id=raw_ch_a_id,
                raw_ch_b_id=raw_ch_b_id,
                logical_ch_a=logical_ch_a,
                logical_ch_b=logical_ch_b,
            ),
            ttbin,
            "ttbin",
        )

    # Try npz fallback
    npz_candidates = [
        ttbin.parent / "parsed_timebin_data.npz" if ttbin is not None else None,
        Path("parsed_timebin_data.npz"),
    ]
    npz_path = next((p for p in npz_candidates if p is not None and p.exists()), None)
    if npz_path is not None:
        return _read_npz_timebins(npz_path), None, "parsed_timebin_data.npz"

    raise RuntimeError(
        f"No valid input found. Provide --ttbin pointing to a .ttbin file."
    )


# ---------------------------------------------------------------------------
# Coincidence pairing: all_pairs_window
# ---------------------------------------------------------------------------

def _find_coincidence_pairs(
    timetags: _RawTimetags,
    *,
    window_ps: int,
    logical_ch_a: int,
    logical_ch_b: int,
    pair_center_ps: int = 0,
) -> _CoincidenceResult:
    """Find all coincidence pairs within window. Events can be reused.

    pair_center_ps shifts the pairing window center:
        searches for B events where |t_B - t_A - pair_center_ps| <= window_ps
    """
    Ch = timetags.Ch
    TimeTag = timetags.TimeTag
    if Ch.shape != TimeTag.shape:
        raise ValueError(f"Ch and TimeTag shape mismatch: {Ch.shape} vs {TimeTag.shape}")

    t_a = np.sort(TimeTag[Ch == float(int(logical_ch_a))].astype(np.int64, copy=False))
    t_b = np.sort(TimeTag[Ch == float(int(logical_ch_b))].astype(np.int64, copy=False))

    if t_a.size == 0 or t_b.size == 0:
        return _CoincidenceResult(
            t_a_paired=np.array([], dtype=np.int64),
            t_b_paired=np.array([], dtype=np.int64),
            n_events_a=int(t_a.size),
            n_events_b=int(t_b.size),
            window_ps=int(window_ps),
            pairing_mode="all_pairs_window",
            allows_event_reuse=True,
        )

    w = int(window_ps)
    center = int(pair_center_ps)
    # Find all B events within window centered at pair_center_ps
    left = np.searchsorted(t_b, t_a + center - w, side="left")
    right = np.searchsorted(t_b, t_a + center + w, side="right")
    pair_counts = right - left
    total_pairs = int(np.sum(pair_counts))

    if total_pairs <= 0:
        return _CoincidenceResult(
            t_a_paired=np.array([], dtype=np.int64),
            t_b_paired=np.array([], dtype=np.int64),
            n_events_a=int(t_a.size),
            n_events_b=int(t_b.size),
            window_ps=int(window_ps),
            pairing_mode="all_pairs_window",
            allows_event_reuse=True,
        )

    # Build paired arrays
    a_rep = np.repeat(t_a, pair_counts)
    b_vals = np.empty(total_pairs, dtype=np.int64)
    pos = 0
    for lo, hi in zip(left, right):
        n = int(hi - lo)
        if n:
            b_vals[pos:pos + n] = t_b[lo:hi]
            pos += n

    return _CoincidenceResult(
        t_a_paired=a_rep,
        t_b_paired=b_vals,
        n_events_a=int(t_a.size),
        n_events_b=int(t_b.size),
        window_ps=int(window_ps),
        pairing_mode="all_pairs_window",
        allows_event_reuse=True,
    )


def _find_coincidence_pairs_with_delay(
    timetags: _RawTimetags,
    *,
    window_ps: int,
    logical_ch_a: int,
    logical_ch_b: int,
    delay_ps: int,
    pair_center_ps: int = 0,
) -> _CoincidenceResult:
    """Find coincidence pairs with B channel delayed by delay_ps (for accidentals estimation).

    pair_center_ps shifts the pairing window center (same as _find_coincidence_pairs).
    """
    Ch = timetags.Ch
    TimeTag = timetags.TimeTag
    if Ch.shape != TimeTag.shape:
        raise ValueError(f"Ch and TimeTag shape mismatch: {Ch.shape} vs {TimeTag.shape}")

    t_a = np.sort(TimeTag[Ch == float(int(logical_ch_a))].astype(np.int64, copy=False))
    t_b = np.sort(TimeTag[Ch == float(int(logical_ch_b))].astype(np.int64, copy=False)) + np.int64(delay_ps)

    if t_a.size == 0 or t_b.size == 0:
        return _CoincidenceResult(
            t_a_paired=np.array([], dtype=np.int64),
            t_b_paired=np.array([], dtype=np.int64),
            n_events_a=int(t_a.size),
            n_events_b=int(t_b.size),
            window_ps=int(window_ps),
            pairing_mode="all_pairs_window_delayed",
            allows_event_reuse=True,
        )

    w = int(window_ps)
    center = int(pair_center_ps)
    left = np.searchsorted(t_b, t_a + center - w, side="left")
    right = np.searchsorted(t_b, t_a + center + w, side="right")
    pair_counts = right - left
    total_pairs = int(np.sum(pair_counts))

    if total_pairs <= 0:
        return _CoincidenceResult(
            t_a_paired=np.array([], dtype=np.int64),
            t_b_paired=np.array([], dtype=np.int64),
            n_events_a=int(t_a.size),
            n_events_b=int(t_b.size),
            window_ps=int(window_ps),
            pairing_mode="all_pairs_window_delayed",
            allows_event_reuse=True,
        )

    a_rep = np.repeat(t_a, pair_counts)
    b_vals = np.empty(total_pairs, dtype=np.int64)
    pos = 0
    for lo, hi in zip(left, right):
        n = int(hi - lo)
        if n:
            b_vals[pos:pos + n] = t_b[lo:hi]
            pos += n

    return _CoincidenceResult(
        t_a_paired=a_rep,
        t_b_paired=b_vals,
        n_events_a=int(t_a.size),
        n_events_b=int(t_b.size),
        window_ps=int(window_ps),
        pairing_mode="all_pairs_window_delayed",
        allows_event_reuse=True,
    )


# ---------------------------------------------------------------------------
# Binning: CV, DV, and SVD unwrapped
# ---------------------------------------------------------------------------

def _time_tags_to_bins(times_ps: np.ndarray, *, bin_width_ps: int, frame_origin_ps: float) -> np.ndarray:
    """Convert timestamps to bin indices using integer arithmetic to avoid float64 precision loss."""
    origin_int = np.int64(int(round(frame_origin_ps)))
    shifted = times_ps - origin_int
    bins = shifted // np.int64(bin_width_ps)
    return bins.astype(np.int64, copy=False)


def _frame_local_bins(times_ps: np.ndarray, *, bin_width_ps: int, frame_bins: int, frame_origin_ps: float) -> np.ndarray:
    """Convert timestamps to frame-local bin indices (modulo frame_bins)."""
    global_bins = _time_tags_to_bins(times_ps, bin_width_ps=int(bin_width_ps), frame_origin_ps=float(frame_origin_ps))
    return np.mod(global_bins, int(frame_bins)).astype(np.int64, copy=False)


def _compute_cv_histogram(
    t_a_paired: np.ndarray,
    t_b_paired: np.ndarray,
    *,
    frame_period_ps: int,
    fine_bin_ps: int,
    frame_origin_ps: float,
) -> np.ndarray:
    """Compute CV 2D histogram with fine bins. Uses integer arithmetic to avoid float64 precision loss."""
    n_bins = int(frame_period_ps // fine_bin_ps)
    if t_a_paired.size == 0:
        return np.zeros((n_bins, n_bins), dtype=np.float64)

    # All arithmetic in int64 to avoid float64 precision loss on large timestamps
    origin_int = np.int64(int(round(frame_origin_ps)))
    period = np.int64(frame_period_ps)
    fine = np.int64(fine_bin_ps)

    t_a_shifted = t_a_paired - origin_int
    t_b_shifted = t_b_paired - origin_int

    a_mod = np.mod(t_a_shifted, period)
    b_mod = np.mod(t_b_shifted, period)

    a_bin = (a_mod // fine).astype(np.int64)
    b_bin = (b_mod // fine).astype(np.int64)

    # Bounds check: reject out-of-range bins instead of clipping
    valid = (a_bin >= 0) & (a_bin < n_bins) & (b_bin >= 0) & (b_bin < n_bins)
    if not np.all(valid):
        n_invalid = int(np.sum(~valid))
        a_bin = a_bin[valid]
        b_bin = b_bin[valid]

    cv = np.zeros((n_bins, n_bins), dtype=np.float64)
    np.add.at(cv, (a_bin, b_bin), 1.0)
    return cv


def _compute_dv_matrix(
    t_a_paired: np.ndarray,
    t_b_paired: np.ndarray,
    *,
    dimension: int,
    binwidth_ps: int,
    frame_origin_ps: float,
) -> np.ndarray:
    """Compute DV JTI matrix with discrete bins. Uses integer arithmetic to avoid float64 precision loss."""
    if t_a_paired.size == 0:
        return np.zeros((dimension, dimension), dtype=np.float64)

    # All arithmetic in int64 to avoid float64 precision loss on large timestamps
    origin_int = np.int64(int(round(frame_origin_ps)))
    bw = np.int64(binwidth_ps)
    dim = np.int64(dimension)

    t_a_shifted = t_a_paired - origin_int
    t_b_shifted = t_b_paired - origin_int

    a_bin = t_a_shifted // bw
    b_bin = t_b_shifted // bw

    # Frame-local bins
    a_local = np.mod(a_bin, dim).astype(np.int64)
    b_local = np.mod(b_bin, dim).astype(np.int64)

    # Bounds check: reject out-of-range bins instead of clipping
    valid = (a_local >= 0) & (a_local < dimension) & (b_local >= 0) & (b_local < dimension)
    if not np.all(valid):
        a_local = a_local[valid]
        b_local = b_local[valid]

    dv = np.zeros((dimension, dimension), dtype=np.float64)
    np.add.at(dv, (a_local, b_local), 1.0)
    return dv


def _compute_unwrapped_edge_guarded_jti(
    t_a_paired: np.ndarray,
    t_b_paired: np.ndarray,
    *,
    binwidth_ps: int,
    dim: int,
    origin_ps: int,
    tau0_ps: int = 0,
    guard_bins: int = 2,
) -> tuple[np.ndarray, dict]:
    """Compute unwrapped, edge-guarded, non-cyclic JTI for SVD/Schmidt analysis.

    Rejects cross-frame pairs and applies edge guard to ensure finite-support kernel.
    All arithmetic in int64 to avoid float64 precision loss on large timestamps.
    """
    if t_a_paired.size == 0:
        return np.zeros((dim, dim), dtype=np.float64), {
            "raw_pairs_before_unwrap": 0,
            "rejected_cross_frame_pairs": 0,
            "rejected_edge_pairs": 0,
            "kept_pairs": 0,
            "kept_fraction_of_raw_pairs": 0.0,
            "cross_frame_fraction": 0.0,
            "edge_rejected_fraction": 0.0,
        }

    # All arithmetic in int64
    origin = np.int64(origin_ps)
    tau0 = np.int64(tau0_ps)
    bw = np.int64(binwidth_ps)
    frame_period = np.int64(dim) * bw
    guard_ps = np.int64(guard_bins) * bw

    raw_pairs = t_a_paired.size

    # Shift by origin
    ua = t_a_paired.astype(np.int64) - origin
    ub = (t_b_paired.astype(np.int64) - tau0) - origin

    # Compute frame indices
    frame_a = ua // frame_period
    frame_b = ub // frame_period

    # Reject cross-frame pairs
    same_frame = frame_a == frame_b
    n_cross_frame = int(np.sum(~same_frame))
    ua = ua[same_frame]
    ub = ub[same_frame]
    frame_a = frame_a[same_frame]

    if ua.size == 0:
        return np.zeros((dim, dim), dtype=np.float64), {
            "raw_pairs_before_unwrap": raw_pairs,
            "rejected_cross_frame_pairs": n_cross_frame,
            "rejected_edge_pairs": 0,
            "kept_pairs": 0,
            "kept_fraction_of_raw_pairs": 0.0,
            "cross_frame_fraction": n_cross_frame / raw_pairs if raw_pairs > 0 else 0.0,
            "edge_rejected_fraction": 0.0,
        }

    # Compute frame-local coordinates
    xa = ua - frame_a * frame_period
    xb = ub - frame_a * frame_period  # same frame_a since same_frame

    # Edge guard: reject events near frame boundaries
    in_guard = (
        (xa >= guard_ps) & (xa < frame_period - guard_ps) &
        (xb >= guard_ps) & (xb < frame_period - guard_ps)
    )
    n_edge_rejected = int(ua.size - np.sum(in_guard))
    xa = xa[in_guard]
    xb = xb[in_guard]

    if xa.size == 0:
        return np.zeros((dim, dim), dtype=np.float64), {
            "raw_pairs_before_unwrap": raw_pairs,
            "rejected_cross_frame_pairs": n_cross_frame,
            "rejected_edge_pairs": n_edge_rejected,
            "kept_pairs": 0,
            "kept_fraction_of_raw_pairs": 0.0,
            "cross_frame_fraction": n_cross_frame / raw_pairs if raw_pairs > 0 else 0.0,
            "edge_rejected_fraction": n_edge_rejected / raw_pairs if raw_pairs > 0 else 0.0,
        }

    # Bin into matrix
    i = xa // bw
    j = xb // bw

    # Bounds check: reject out-of-range bins instead of clipping
    valid = (i >= 0) & (i < dim) & (j >= 0) & (j < dim)
    n_invalid = int(np.sum(~valid))
    if n_invalid > 0:
        i = i[valid]
        j = j[valid]

    H = np.zeros((dim, dim), dtype=np.float64)
    np.add.at(H, (i, j), 1.0)

    kept = int(xa.size)
    meta = {
        "raw_pairs_before_unwrap": raw_pairs,
        "rejected_cross_frame_pairs": n_cross_frame,
        "rejected_edge_pairs": n_edge_rejected,
        "invalid_bin_pairs": n_invalid,
        "kept_pairs": kept,
        "kept_fraction_of_raw_pairs": kept / raw_pairs if raw_pairs > 0 else 0.0,
        "cross_frame_fraction": n_cross_frame / raw_pairs if raw_pairs > 0 else 0.0,
        "edge_rejected_fraction": n_edge_rejected / raw_pairs if raw_pairs > 0 else 0.0,
        "invalid_bin_fraction": n_invalid / raw_pairs if raw_pairs > 0 else 0.0,
    }
    return H, meta


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

def compute_jti_diagnostics(counts: np.ndarray, *, band_bins: int = 1) -> dict[str, float]:
    """Compute JTI diagnostics including diag_band_fraction and diag_contrast."""
    total_sum = float(np.sum(counts))
    diag_main_sum = float(np.trace(counts))
    diag_pm1_sum = float(np.trace(counts, offset=1) + np.trace(counts, offset=-1))

    if total_sum <= 0.0:
        return {
            "total_sum": 0.0,
            "diag_main_sum": 0.0,
            "diag_pm1_sum": 0.0,
            "diag_band_sum": 0.0,
            "offdiag_sum": 0.0,
            "diag_main_fraction": 0.0,
            "diag_pm1_fraction": 0.0,
            "diag_band_fraction": 0.0,
            "offdiag_fraction": 0.0,
            "diag_contrast": 0.0,
        }

    # diag_band_sum: sum over |row-col| <= band_bins
    n = int(counts.shape[0])
    band = int(band_bins)
    diag_band_sum = diag_main_sum
    for offset in range(1, band + 1):
        diag_band_sum += float(np.trace(counts, offset=offset) + np.trace(counts, offset=-offset))

    offdiag_sum = total_sum - diag_band_sum

    return {
        "total_sum": total_sum,
        "diag_main_sum": diag_main_sum,
        "diag_pm1_sum": diag_pm1_sum,
        "diag_band_sum": diag_band_sum,
        "offdiag_sum": offdiag_sum,
        "diag_main_fraction": diag_main_sum / total_sum,
        "diag_pm1_fraction": diag_pm1_sum / total_sum,
        "diag_band_fraction": diag_band_sum / total_sum,
        "offdiag_fraction": offdiag_sum / total_sum,
        "diag_contrast": diag_pm1_sum / offdiag_sum if offdiag_sum > 0 else 0.0,
    }


def _compute_score(diag_band_fraction: float, accidental_fraction: float) -> float:
    """Compute frame_origin selection score: diag_band_fraction - accidental_fraction."""
    return float(diag_band_fraction) - float(accidental_fraction)


def _plot_png(path: Path, mat: np.ndarray, *, title: str) -> None:
    """Plot JTI heatmap and save as PNG."""
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        raise RuntimeError(f"matplotlib is required for --plot: {exc}") from exc

    n = int(mat.shape[0])
    fig, ax = plt.subplots(figsize=(6.0, 5.0), dpi=160)
    im = ax.imshow(
        mat,
        origin="lower",
        cmap="viridis",
        extent=[-0.5, n - 0.5, -0.5, n - 0.5],
        aspect="equal",
    )
    ax.set_title(title)
    ax.set_xlabel("Signal time-bin index")
    ax.set_ylabel("Idler time-bin index")
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    plt.colorbar(im, ax=ax, label="Counts")
    fig.tight_layout()
    fig.savefig(str(path))
    plt.close(fig)


def diagonal_coincidence_profile(counts: np.ndarray, *, band_bins: int = 1) -> np.ndarray:
    """Sum counts along the main diagonal direction over |col-row| <= band_bins."""
    mat = np.asarray(counts, dtype=np.float64)
    if mat.ndim != 2 or mat.shape[0] != mat.shape[1]:
        raise ValueError(f"counts must be a square matrix, got shape {mat.shape}")
    n = int(mat.shape[0])
    band = int(band_bins)
    if band < 0:
        raise ValueError("band_bins must be non-negative")
    out = np.zeros(n, dtype=np.float64)
    out += np.diag(mat)
    for offset in range(1, band + 1):
        upper = np.diag(mat, k=offset)
        lower = np.diag(mat, k=-offset)
        out[: n - offset] += upper
        out[offset:] += lower
    return out


# ---------------------------------------------------------------------------
# Chunked pair finding with center offset
# ---------------------------------------------------------------------------

def iter_pair_chunks_centered(
    t_a: np.ndarray,
    t_b: np.ndarray,
    *,
    center_ps: int,
    half_window_ps: int,
    chunk_events: int = 100_000,
) -> Iterable[tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Find coincidence pairs within a centered window, yielded in chunks.

    For each A event, finds B events in [a + center - half, a + center + half].
    Yields (a_rep, b_vals, delta) tuples where delta = b - a.
    All arithmetic in int64 to avoid float64 precision loss on large timestamps.
    """
    t_b = np.asarray(t_b, dtype=np.int64)
    center = int(center_ps)
    half = int(half_window_ps)
    for start in range(0, int(t_a.size), int(chunk_events)):
        a = np.asarray(t_a[start : start + int(chunk_events)], dtype=np.int64)
        left = np.searchsorted(t_b, a + center - half, side="left")
        right = np.searchsorted(t_b, a + center + half, side="right")
        pair_counts = right - left
        total = int(np.sum(pair_counts))
        if total <= 0:
            continue
        a_rep = np.repeat(a, pair_counts)
        b_vals = np.empty(total, dtype=np.int64)
        pos = 0
        for lo, hi in zip(left, right):
            n = int(hi - lo)
            if n:
                b_vals[pos : pos + n] = t_b[lo:hi]
                pos += n
        b_vals = b_vals[:pos]
        yield a_rep[:pos], b_vals, b_vals - a_rep[:pos]


# ---------------------------------------------------------------------------
# Centered line JTI computation
# ---------------------------------------------------------------------------

def compute_centered_line_jti(
    t_a: np.ndarray,
    t_b: np.ndarray,
    *,
    tau_center_ps: int,
    half_window_ps: int,
    dim: int,
    bin_width_ps: int,
    frame_origin_ps: float,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Compute JTI for a single tau-centered line.

    Shifts B timestamps by tau_center_ps so the selected line folds near the main diagonal.
    All binning uses integer arithmetic to avoid float64 precision loss on large timestamps.
    """
    import math

    counts = np.zeros((int(dim), int(dim)), dtype=np.float64)
    total_pairs = 0
    a_with_pairs = 0
    max_b_per_a = 0
    delta_sum = 0.0
    delta_sq_sum = 0.0
    for a_rep, b_vals, deltas in iter_pair_chunks_centered(
        t_a, t_b,
        center_ps=int(tau_center_ps),
        half_window_ps=int(half_window_ps),
    ):
        if a_rep.size == 0:
            continue
        # Keep int64 arithmetic to avoid float64 precision loss on large timestamps
        b_shifted = b_vals - np.int64(int(tau_center_ps))
        x = _frame_local_bins(a_rep, bin_width_ps=int(bin_width_ps), frame_bins=int(dim), frame_origin_ps=float(frame_origin_ps))
        y = _frame_local_bins(b_shifted, bin_width_ps=int(bin_width_ps), frame_bins=int(dim), frame_origin_ps=float(frame_origin_ps))
        np.add.at(counts, (x, y), 1.0)
        total_pairs += int(a_rep.size)
        unique_a = np.unique(a_rep)
        a_with_pairs += int(unique_a.size)
        if unique_a.size:
            _, per_a = np.unique(a_rep, return_counts=True)
            max_b_per_a = max(max_b_per_a, int(np.max(per_a)))
        centered_delta = deltas.astype(np.float64, copy=False) - float(tau_center_ps)
        delta_sum += float(np.sum(centered_delta))
        delta_sq_sum += float(np.sum(centered_delta * centered_delta))
    mean_delta = delta_sum / float(total_pairs) if total_pairs else math.nan
    var_delta = delta_sq_sum / float(total_pairs) - mean_delta * mean_delta if total_pairs else math.nan
    meta = {
        "n_pairs": int(total_pairs),
        "n_a_with_window_pairs": int(a_with_pairs),
        "max_b_per_a_in_window": int(max_b_per_a),
        "tau_center_ps": int(tau_center_ps),
        "line_half_window_ps": int(half_window_ps),
        "centered_delta_mean_ps": float(mean_delta) if np.isfinite(mean_delta) else math.nan,
        "centered_delta_std_ps": float(math.sqrt(max(0.0, var_delta))) if np.isfinite(var_delta) else math.nan,
    }
    return counts, meta


# ---------------------------------------------------------------------------
# Multiline JTI with raw offsets
# ---------------------------------------------------------------------------

def compute_multiline_raw_offset_jti(
    t_a: np.ndarray,
    t_b: np.ndarray,
    *,
    tau_centers_ps: list[int],
    tau_reference_ps: int,
    half_window_ps: int,
    dim: int,
    bin_width_ps: int,
    frame_origin_ps: float,
    require_same_frame: bool = False,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Compute multiline JTI with raw offset display.

    B channel is shifted only by tau_reference_ps, so FPC lines remain as parallel
    diagonal offsets relative to that reference.
    All binning uses integer arithmetic to avoid float64 precision loss on large timestamps.
    """
    counts = np.zeros((int(dim), int(dim)), dtype=np.float64)
    total_pairs = 0
    per_line_pairs: dict[str, int] = {}
    used_centers: list[int] = []
    for tau in tau_centers_ps:
        line_pairs = 0
        for a_rep, b_vals, _ in iter_pair_chunks_centered(
            t_a, t_b,
            center_ps=int(tau),
            half_window_ps=int(half_window_ps),
        ):
            if a_rep.size == 0:
                continue
            if require_same_frame:
                # Keep int64 arithmetic for same-frame filtering
                shifted_b = b_vals - np.int64(int(tau_reference_ps))
                gx = _time_tags_to_bins(a_rep, bin_width_ps=int(bin_width_ps), frame_origin_ps=float(frame_origin_ps))
                gy = _time_tags_to_bins(shifted_b, bin_width_ps=int(bin_width_ps), frame_origin_ps=float(frame_origin_ps))
                fx = np.floor_divide(gx, int(dim))
                fy = np.floor_divide(gy, int(dim))
                keep = fx == fy
                if not np.any(keep):
                    continue
                x = np.mod(gx[keep], int(dim)).astype(np.int64, copy=False)
                y = np.mod(gy[keep], int(dim)).astype(np.int64, copy=False)
                line_pairs += int(np.count_nonzero(keep))
            else:
                x = _frame_local_bins(
                    a_rep,
                    bin_width_ps=int(bin_width_ps),
                    frame_bins=int(dim),
                    frame_origin_ps=float(frame_origin_ps),
                )
                # Keep int64 arithmetic for B shift
                shifted_b = b_vals - np.int64(int(tau_reference_ps))
                y = _frame_local_bins(
                    shifted_b,
                    bin_width_ps=int(bin_width_ps),
                    frame_bins=int(dim),
                    frame_origin_ps=float(frame_origin_ps),
                )
                line_pairs += int(a_rep.size)
            np.add.at(counts, (x, y), 1.0)
        per_line_pairs[str(int(tau))] = int(line_pairs)
        total_pairs += int(line_pairs)
        used_centers.append(int(tau))
    return counts, {
        "n_pairs": int(total_pairs),
        "tau_centers_ps": used_centers,
        "tau_reference_ps": int(tau_reference_ps),
        "line_half_window_ps": int(half_window_ps),
        "require_same_frame": bool(require_same_frame),
        "per_line_pairs": per_line_pairs,
    }


# ---------------------------------------------------------------------------
# Display JTI with alignment-centered diagonal overlay
# ---------------------------------------------------------------------------

def compute_alignment_centered_display_jti(
    t_a: np.ndarray,
    t_b: np.ndarray,
    *,
    selected_offsets: list[dict[str, Any]],
    tau0_ps: float,
    center_offset_bin: int,
    half_window_ps: int,
    dim: int,
    bin_width_ps: int,
    frame_origin_ps: float,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """Compute display JTI where the brightest delay peak is forced onto the main diagonal.

    Each peak is placed on its own diagonal offset. Only A events with pairs in the
    peak's window are counted.
    All binning uses integer arithmetic to avoid float64 precision loss on large timestamps.
    """
    counts = np.zeros((int(dim), int(dim)), dtype=np.uint64)
    peak_meta: list[dict[str, Any]] = []
    for idx, row in enumerate(selected_offsets):
        tau_rel = float(row.get("tau_rel_ps", 0.0))
        tau_center = float(tau0_ps) + tau_rel
        diagonal_offset = int(row.get("diagonal_offset_bin", round(tau_rel / float(bin_width_ps))))
        display_offset = int(center_offset_bin) + diagonal_offset
        n_pairs = 0
        for a_rep, _b_vals, _dt_vals in iter_pair_chunks_centered(
            t_a, t_b,
            center_ps=int(round(tau_center)),
            half_window_ps=int(half_window_ps),
        ):
            x = _frame_local_bins(a_rep, bin_width_ps=int(bin_width_ps), frame_bins=int(dim), frame_origin_ps=float(frame_origin_ps))
            y = x + int(display_offset)
            keep = (y >= 0) & (y < int(dim))
            if np.any(keep):
                np.add.at(counts, (x[keep], y[keep]), 1)
                n_pairs += int(np.count_nonzero(keep))
        peak_meta.append(
            {
                "peak_id": row.get("peak_id", f"p{idx}"),
                "tau_ps": float(tau_center),
                "tau_rel_ps": tau_rel,
                "chosen_bw_ps": float(bin_width_ps),
                "diagnostic_diagonal_offset_bin": int(diagonal_offset),
                "display_offset_bin": int(display_offset),
                "center_offset_bin": int(center_offset_bin),
                "alignment_error_ps": float(row.get("alignment_error_ps", 0.0) or 0.0),
                "norm_height": float(row.get("norm_height", 0.0) or 0.0),
                "fwhm_ps": float(row.get("fwhm_ps", float("nan")) or float("nan")),
                "fwhm_bins": float(row.get("fwhm_bins", float("nan")) or float("nan")),
                "n_pairs_plotted": int(n_pairs),
            }
        )
    return counts, peak_meta


# ---------------------------------------------------------------------------
# Frame origin scan
# ---------------------------------------------------------------------------

def _scan_frame_origin(
    timetags: _RawTimetags,
    *,
    k: int,
    binwidth_ps: int,
    dimension: int,
    band_bins: int,
    logical_ch_a: int,
    logical_ch_b: int,
    accidental_delay_mult: int,
    origin_start_ps: float,
    origin_stop_ps: float | None,
    origin_step_ps: float,
    quiet: bool,
    pair_center_ps: int = 0,
) -> _ScanResult:
    """Scan frame_origin for a given k value."""
    window_ps = k * binwidth_ps
    frame_period_ps = dimension * binwidth_ps
    stop_ps = float(origin_stop_ps if origin_stop_ps is not None else binwidth_ps)

    # Pre-find coincidence pairs (independent of frame_origin)
    result = _find_coincidence_pairs(
        timetags,
        window_ps=window_ps,
        logical_ch_a=logical_ch_a,
        logical_ch_b=logical_ch_b,
        pair_center_ps=pair_center_ps,
    )

    # Pre-find accidentals pairs (B delayed by several frame periods)
    delay_ps = frame_period_ps * accidental_delay_mult
    acc_result = _find_coincidence_pairs_with_delay(
        timetags,
        window_ps=window_ps,
        logical_ch_a=logical_ch_a,
        logical_ch_b=logical_ch_b,
        delay_ps=delay_ps,
        pair_center_ps=pair_center_ps,
    )

    if not quiet:
        print(f"  k={k}, window_ps={window_ps}, pairs={result.t_a_paired.size}, acc_pairs={acc_result.t_a_paired.size}")

    scan_rows: list[dict] = []
    best_score = -float("inf")
    best_origin = 0.0

    # Scan frame origins
    current = float(origin_start_ps)
    tolerance = abs(origin_step_ps) * 1e-9 + 1e-12
    while current <= stop_ps + tolerance:
        origin = float(round(current, 12))

        # Compute DV matrix for this origin
        dv = _compute_dv_matrix(
            result.t_a_paired,
            result.t_b_paired,
            dimension=dimension,
            binwidth_ps=binwidth_ps,
            frame_origin_ps=origin,
        )

        # Compute accidentals DV matrix
        dv_acc = _compute_dv_matrix(
            acc_result.t_a_paired,
            acc_result.t_b_paired,
            dimension=dimension,
            binwidth_ps=binwidth_ps,
            frame_origin_ps=origin,
        )

        diag = compute_jti_diagnostics(dv, band_bins=band_bins)
        diag_acc = compute_jti_diagnostics(dv_acc, band_bins=band_bins)

        total_pairs = int(diag["total_sum"])
        accidental_fraction = diag_acc["total_sum"] / total_pairs if total_pairs > 0 else 0.0
        score = _compute_score(diag["diag_band_fraction"], accidental_fraction)

        row = {
            "frame_origin_ps": origin,
            "total_pairs": total_pairs,
            "diag_main_fraction": diag["diag_main_fraction"],
            "diag_pm1_fraction": diag["diag_pm1_fraction"],
            "diag_band_fraction": diag["diag_band_fraction"],
            "offdiag_fraction": diag["offdiag_fraction"],
            "diag_contrast": diag["diag_contrast"],
            "accidental_fraction": accidental_fraction,
            "score": score,
        }
        scan_rows.append(row)

        if score > best_score:
            best_score = score
            best_origin = origin

        current += origin_step_ps

    if not quiet:
        print(f"    best_origin={best_origin:.1f}ps, score={best_score:.4f}")

    return _ScanResult(
        k=k,
        window_ps=window_ps,
        best_frame_origin_ps=best_origin,
        total_pairs=int(result.t_a_paired.size),
        diag_main_fraction=scan_rows[-1]["diag_main_fraction"] if scan_rows else 0.0,
        diag_pm1_fraction=scan_rows[-1]["diag_pm1_fraction"] if scan_rows else 0.0,
        offdiag_fraction=scan_rows[-1]["offdiag_fraction"] if scan_rows else 0.0,
        diag_contrast=scan_rows[-1]["diag_contrast"] if scan_rows else 0.0,
        accidental_fraction=scan_rows[-1]["accidental_fraction"] if scan_rows else 0.0,
        score=best_score,
        scan_rows=scan_rows,
    )


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _save_csv_matrix(path: Path, mat: np.ndarray) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([""] + list(range(int(mat.shape[1]))))
        for i in range(int(mat.shape[0])):
            w.writerow([i] + [float(x) for x in mat[i, :].tolist()])


def _save_cv_png(
    path: Path,
    cv: np.ndarray,
    *,
    k: int,
    fine_bin_ps: int,
    frame_period_ps: int,
    frame_origin_ps: float,
    total_pairs: int,
) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        raise RuntimeError(f"matplotlib required for PNG output: {exc}") from exc

    n_bins = cv.shape[0]
    extent = [0, frame_period_ps / 1000.0, 0, frame_period_ps / 1000.0]  # ns

    fig, ax = plt.subplots(figsize=(8, 7), dpi=150)
    im = ax.imshow(
        cv,
        origin="lower",
        aspect="equal",
        extent=extent,
        cmap="viridis",
        interpolation="nearest",
    )
    ax.set_xlabel("t_A mod frame (ns)")
    ax.set_ylabel("t_B mod frame (ns)")
    ax.set_title(
        f"CV JTI | k={k}, fine_bin={fine_bin_ps}ps, window={k * fine_bin_ps}ps\n"
        f"origin={frame_origin_ps:.1f}ps, pairs={total_pairs:,}"
    )
    plt.colorbar(im, ax=ax, label="Counts")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _save_dv_png(
    path: Path,
    dv: np.ndarray,
    *,
    k: int,
    binwidth_ps: int,
    dimension: int,
    frame_origin_ps: float,
    total_pairs: int,
) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        raise RuntimeError(f"matplotlib required for PNG output: {exc}") from exc

    extent = [0, dimension * binwidth_ps / 1000.0, 0, dimension * binwidth_ps / 1000.0]

    fig, ax = plt.subplots(figsize=(8, 7), dpi=150)
    im = ax.imshow(
        dv,
        origin="lower",
        aspect="equal",
        extent=extent,
        cmap="viridis",
        interpolation="nearest",
    )
    ax.set_xlabel("t_A bin index")
    ax.set_ylabel("t_B bin index")
    ax.set_title(
        f"DV JTI | k={k}, bw={binwidth_ps}ps, dim={dimension}\n"
        f"origin={frame_origin_ps:.1f}ps, pairs={total_pairs:,}"
    )
    plt.colorbar(im, ax=ax, label="Counts")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _save_scan_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def _save_summary_csv(path: Path, summaries: list[dict]) -> None:
    if not summaries:
        return
    fieldnames = list(summaries[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in summaries:
            w.writerow(row)


# ---------------------------------------------------------------------------
# Main extraction logic
# ---------------------------------------------------------------------------

def run_extract(
    *,
    ttbin: Path,
    raw_ch_a_id: int,
    raw_ch_b_id: int,
    binwidth_ps: int,
    dimension: int,
    fine_bins: list[int],
    k_values: list[int],
    window_ps_override: int | None = None,
    scan_frame_origin: bool,
    frame_origin_ps: float,
    frame_origin_start_ps: float,
    frame_origin_stop_ps: float | None,
    frame_origin_step_ps: float,
    band_bins: int,
    accidental_delay_mult: int,
    out_dir: Path,
    quiet: bool,
    max_events: int | None,
    save_csv: bool,
    save_png: bool,
    svd_unwrapped: bool = True,
    guard_bins: int = 2,
    tau0_ps: int = 0,
    pair_center_ps: int = 0,
    tau_align_ps: int = 0,
) -> dict:
    """Main JTI extraction entry point with CV/DV/SVD unwrapped output."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load timetags
    timetags, resolved_ttbin, input_source = _load_timetags(
        ttbin=ttbin,
        max_events=max_events,
        raw_ch_a_id=raw_ch_a_id,
        raw_ch_b_id=raw_ch_b_id,
        logical_ch_a=0,
        logical_ch_b=1,
    )

    if not quiet:
        print(f"Loaded {timetags.TimeTag.size} events from {resolved_ttbin}")
        print(f"binwidth_ps={binwidth_ps}, dimension={dimension}")
        print(f"k_values={k_values}, fine_bins={fine_bins}")

    frame_period_ps = dimension * binwidth_ps
    summary_rows: list[dict] = []

    for k in k_values:
        window_ps = window_ps_override if window_ps_override is not None else k * binwidth_ps
        if not quiet:
            print(f"\n--- k={k}, window_ps={window_ps} ---")

        if scan_frame_origin:
            scan_result = _scan_frame_origin(
                timetags,
                k=k,
                binwidth_ps=binwidth_ps,
                dimension=dimension,
                band_bins=band_bins,
                logical_ch_a=0,
                logical_ch_b=1,
                accidental_delay_mult=accidental_delay_mult,
                origin_start_ps=frame_origin_start_ps,
                origin_stop_ps=frame_origin_stop_ps,
                origin_step_ps=frame_origin_step_ps,
                quiet=quiet,
                pair_center_ps=int(pair_center_ps),
            )
            best_origin = scan_result.best_frame_origin_ps

            # Save scan CSV
            scan_csv_path = out_dir / f"frame_origin_scan_k{k}.csv"
            _save_scan_csv(scan_csv_path, scan_result.scan_rows)
            if not quiet:
                print(f"  Saved scan CSV: {scan_csv_path}")
        else:
            best_origin = frame_origin_ps
            scan_result = None

        # Find coincidence pairs
        result = _find_coincidence_pairs(
            timetags,
            window_ps=window_ps,
            logical_ch_a=0,
            logical_ch_b=1,
            pair_center_ps=int(pair_center_ps),
        )

        # Find accidentals pairs
        delay_ps = frame_period_ps * accidental_delay_mult
        acc_result = _find_coincidence_pairs_with_delay(
            timetags,
            window_ps=window_ps,
            logical_ch_a=0,
            logical_ch_b=1,
            delay_ps=delay_ps,
            pair_center_ps=int(pair_center_ps),
        )

        total_pairs = int(result.t_a_paired.size)
        acc_pairs = int(acc_result.t_a_paired.size)
        accidental_fraction = acc_pairs / total_pairs if total_pairs > 0 else 0.0

        if not quiet:
            print(f"  pairs={total_pairs:,}, acc_pairs={acc_pairs:,}, acc_fraction={accidental_fraction:.4f}")

        # Generate CV outputs for each fine_bin
        for fine_bin_ps in fine_bins:
            n_cv_bins = frame_period_ps // fine_bin_ps
            cv = _compute_cv_histogram(
                result.t_a_paired,
                result.t_b_paired,
                frame_period_ps=frame_period_ps,
                fine_bin_ps=fine_bin_ps,
                frame_origin_ps=best_origin,
            )

            cv_diag = compute_jti_diagnostics(cv, band_bins=band_bins)

            if save_csv:
                cv_csv_path = out_dir / f"cv_fine{fine_bin_ps}ps_k{k}.csv"
                _save_csv_matrix(cv_csv_path, cv)
                if not quiet:
                    print(f"  Saved CV CSV: {cv_csv_path}")

            if save_png:
                cv_png_path = out_dir / f"cv_fine{fine_bin_ps}ps_k{k}.png"
                _save_cv_png(
                    cv_png_path,
                    cv,
                    k=k,
                    fine_bin_ps=fine_bin_ps,
                    frame_period_ps=frame_period_ps,
                    frame_origin_ps=best_origin,
                    total_pairs=total_pairs,
                )
                if not quiet:
                    print(f"  Saved CV PNG: {cv_png_path}")

            # Save CV meta
            cv_meta = {
                "pairing_mode": "all_pairs_window",
                "allows_event_reuse": True,
                "purpose": "diagnostic_cv_dv_extraction",
                "k": k,
                "window_ps": window_ps,
                "fine_bin_ps": fine_bin_ps,
                "cv_bins": int(n_cv_bins),
                "frame_period_ps": frame_period_ps,
                "frame_origin_ps": best_origin,
                "total_pairs": total_pairs,
                "accidental_pairs": acc_pairs,
                "accidental_fraction": accidental_fraction,
                "accidental_delay_ps": delay_ps,
                "band_bins": band_bins,
                "diagnostics": cv_diag,
                "input_source": str(input_source),
                "resolved_ttbin": str(resolved_ttbin) if resolved_ttbin is not None else None,
            }
            cv_meta_path = out_dir / f"cv_fine{fine_bin_ps}ps_k{k}.meta.json"
            cv_meta_path.write_text(json.dumps(cv_meta, ensure_ascii=False, indent=2), encoding="utf-8")

        # Generate DV output
        dv = _compute_dv_matrix(
            result.t_a_paired,
            result.t_b_paired,
            dimension=dimension,
            binwidth_ps=binwidth_ps,
            frame_origin_ps=best_origin,
        )

        dv_diag = compute_jti_diagnostics(dv, band_bins=band_bins)

        if save_csv:
            dv_csv_path = out_dir / f"dv_k{k}_bw{binwidth_ps}ps_dim{dimension}.csv"
            _save_csv_matrix(dv_csv_path, dv)
            if not quiet:
                print(f"  Saved DV CSV: {dv_csv_path}")

        if save_png:
            dv_png_path = out_dir / f"dv_k{k}_bw{binwidth_ps}ps_dim{dimension}.png"
            _save_dv_png(
                dv_png_path,
                dv,
                k=k,
                binwidth_ps=binwidth_ps,
                dimension=dimension,
                frame_origin_ps=best_origin,
                total_pairs=total_pairs,
            )
            if not quiet:
                print(f"  Saved DV PNG: {dv_png_path}")

        # Save DV meta
        dv_meta = {
            "pairing_mode": "all_pairs_window",
            "allows_event_reuse": True,
            "purpose": "diagnostic_cv_dv_extraction",
            "k": k,
            "window_ps": window_ps,
            "binwidth_ps": binwidth_ps,
            "dimension": dimension,
            "frame_period_ps": frame_period_ps,
            "frame_origin_ps": best_origin,
            "total_pairs": total_pairs,
            "accidental_pairs": acc_pairs,
            "accidental_fraction": accidental_fraction,
            "accidental_delay_ps": delay_ps,
            "band_bins": band_bins,
            "diagnostics": dv_diag,
            "input_source": str(input_source),
            "resolved_ttbin": str(resolved_ttbin) if resolved_ttbin is not None else None,
        }
        dv_meta_path = out_dir / f"dv_k{k}_bw{binwidth_ps}ps_dim{dimension}.meta.json"
        dv_meta_path.write_text(json.dumps(dv_meta, ensure_ascii=False, indent=2), encoding="utf-8")

        # Generate SVD unwrapped edge-guarded output (if enabled)
        svd_kept_pairs = 0
        svd_kept_fraction = 0.0
        svd_cross_frame_fraction = 0.0
        svd_edge_rejected_fraction = 0.0

        if svd_unwrapped:
            svd_matrix, svd_meta = _compute_unwrapped_edge_guarded_jti(
                result.t_a_paired,
                result.t_b_paired,
                binwidth_ps=binwidth_ps,
                dim=dimension,
                origin_ps=int(round(best_origin)),
                tau0_ps=int(tau_align_ps),
                guard_bins=guard_bins,
            )

            svd_kept_pairs = svd_meta["kept_pairs"]
            svd_kept_fraction = svd_meta["kept_fraction_of_raw_pairs"]
            svd_cross_frame_fraction = svd_meta["cross_frame_fraction"]
            svd_edge_rejected_fraction = svd_meta["edge_rejected_fraction"]

            # Residual tau diagnostics
            _diag_dim = svd_matrix.shape[0]
            _diag_i, _diag_j = np.meshgrid(np.arange(_diag_dim), np.arange(_diag_dim), indexing='ij')
            _diag_delta = _diag_j - _diag_i
            _diag_total = float(np.sum(svd_matrix))
            if _diag_total > 0:
                _diag_mean = float(np.sum(svd_matrix * _diag_delta) / _diag_total)
                _diag_std = float(np.sqrt(np.sum(svd_matrix * (_diag_delta - _diag_mean) ** 2) / _diag_total))
                _diag_nz = svd_matrix > 0
                _diag_min = int(_diag_delta[_diag_nz].min()) * binwidth_ps if np.any(_diag_nz) else 0
                _diag_max = int(_diag_delta[_diag_nz].max()) * binwidth_ps if np.any(_diag_nz) else 0
            else:
                _diag_mean = 0.0
                _diag_std = 0.0
                _diag_min = 0
                _diag_max = 0
            residual_diagnostics = {
                "weighted_mean_residual_tau_ps": round(_diag_mean * binwidth_ps, 2),
                "weighted_std_residual_tau_ps": round(_diag_std * binwidth_ps, 2),
                "offset_min_ps": _diag_min,
                "offset_max_ps": _diag_max,
            }

            if save_csv:
                svd_csv_path = out_dir / f"svd_jti_unwrapped_guarded_k{k}_bw{binwidth_ps}ps_dim{dimension}.csv"
                _save_csv_matrix(svd_csv_path, svd_matrix)
                if not quiet:
                    print(f"  Saved SVD CSV: {svd_csv_path}")

            if save_png:
                svd_png_path = out_dir / f"svd_jti_unwrapped_guarded_k{k}_bw{binwidth_ps}ps_dim{dimension}.png"
                _save_dv_png(
                    svd_png_path,
                    svd_matrix,
                    k=k,
                    binwidth_ps=binwidth_ps,
                    dimension=dimension,
                    frame_origin_ps=best_origin,
                    total_pairs=svd_kept_pairs,
                )
                if not quiet:
                    print(f"  Saved SVD PNG: {svd_png_path}")

            # Save SVD meta
            svd_meta_full = {
                "mode": "unwrapped_edge_guarded_noncyclic",
                "analysis_mode": "single_line_jti",
                "pairing_mode": "all_pairs_window",
                "allows_event_reuse": True,
                "allows_wraparound": False,
                "intended_use": "Schmidt-like SVD / non-cyclic finite-window JTI",
                "k": k,
                "window_ps": window_ps,
                "binwidth_ps": binwidth_ps,
                "dim": dimension,
                "frame_period_ps": frame_period_ps,
                "origin_ps": int(round(best_origin)),
                "tau0_ps": int(tau0_ps),
                "pair_center_ps": int(pair_center_ps),
                "tau_align_ps": int(tau_align_ps),
                "tau0_ps_input": int(tau0_ps),
                "pair_center_source": "explicit",
                "tau_align_source": "explicit",
                "tau_coordinate_for_selection": "raw_tau = t_B - t_A",
                "tau_coordinate_after_alignment": "residual_tau = (t_B - tau_align_ps) - t_A",
                "guard_bins": guard_bins,
                "guard_ps": guard_bins * binwidth_ps,
                "residual_tau_diagnostics": residual_diagnostics,
                **svd_meta,
                "diagnostics": compute_jti_diagnostics(svd_matrix, band_bins=band_bins),
                "input_source": str(input_source),
                "resolved_ttbin": str(resolved_ttbin) if resolved_ttbin is not None else None,
            }
            svd_meta_path = out_dir / f"svd_jti_unwrapped_guarded_k{k}_bw{binwidth_ps}ps_dim{dimension}.meta.json"
            svd_meta_path.write_text(json.dumps(svd_meta_full, ensure_ascii=False, indent=2), encoding="utf-8")

            if not quiet:
                print(f"  SVD unwrapped: kept={svd_kept_pairs:,} ({svd_kept_fraction:.4f}), "
                      f"cross_frame={svd_cross_frame_fraction:.4f}, edge_rejected={svd_edge_rejected_fraction:.4f}")

        # Add to summary
        score = _compute_score(dv_diag["diag_band_fraction"], accidental_fraction)
        summary_rows.append({
            "k": k,
            "window_ps": window_ps,
            "best_frame_origin_ps": best_origin,
            "total_pairs": total_pairs,
            "accidental_pairs": acc_pairs,
            "accidental_fraction": accidental_fraction,
            "diag_main_fraction": dv_diag["diag_main_fraction"],
            "diag_pm1_fraction": dv_diag["diag_pm1_fraction"],
            "diag_band_fraction": dv_diag["diag_band_fraction"],
            "offdiag_fraction": dv_diag["offdiag_fraction"],
            "diag_contrast": dv_diag["diag_contrast"],
            "score": score,
            "svd_kept_pairs": svd_kept_pairs,
            "svd_kept_fraction": svd_kept_fraction,
            "svd_cross_frame_fraction": svd_cross_frame_fraction,
            "svd_edge_rejected_fraction": svd_edge_rejected_fraction,
            "svd_guard_bins": guard_bins if svd_unwrapped else None,
        })

    # Save summary CSV
    summary_csv_path = out_dir / "summary_k_scan.csv"
    _save_summary_csv(summary_csv_path, summary_rows)
    if not quiet:
        print(f"\nSaved summary: {summary_csv_path}")

    # Save overall summary JSON
    summary_json = {
        "ttbin": str(resolved_ttbin) if resolved_ttbin is not None else None,
        "input_source": str(input_source),
        "raw_ch_a_id": raw_ch_a_id,
        "raw_ch_b_id": raw_ch_b_id,
        "binwidth_ps": binwidth_ps,
        "dimension": dimension,
        "frame_period_ps": frame_period_ps,
        "fine_bins": fine_bins,
        "k_values": k_values,
        "band_bins": band_bins,
        "accidental_delay_mult": accidental_delay_mult,
        "scan_frame_origin": scan_frame_origin,
        "svd_unwrapped": svd_unwrapped,
        "guard_bins": guard_bins,
        "tau0_ps": tau0_ps,
        "summary": summary_rows,
    }
    summary_json_path = out_dir / "extraction_summary.json"
    summary_json_path.write_text(json.dumps(summary_json, ensure_ascii=False, indent=2), encoding="utf-8")

    return summary_json


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="JTI extraction with CV/DV/SVD unwrapped output.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  python -m jti_extract.cli.extract \\\n"
            "    --ttbin 'path/to/data.ttbin' \\\n"
            "    --raw-ch-a-id 1 --raw-ch-b-id 3 \\\n"
            "    --binwidth-ps 50 --dimensions 128 \\\n"
            "    --fine-bins 5 --k-values 1 \\\n"
            "    --scan-frame-origin --svd-unwrapped \\\n"
            "    --out 'path/to/output'\n"
        ),
    )
    ap.add_argument("--ttbin", required=True, help="Path to .ttbin file.")
    ap.add_argument("--raw-ch-a-id", type=int, default=1, help="TimeTagger raw channel id for A (default: 1).")
    ap.add_argument("--raw-ch-b-id", type=int, default=3, help="TimeTagger raw channel id for B (default: 3).")
    ap.add_argument("--binwidth-ps", type=int, default=10, help="Bin width in ps for DV output (default: 10).")
    ap.add_argument("--dimensions", type=int, default=128, help="Dimension for DV output (default: 128).")
    ap.add_argument("--fine-bins", default="5", help="Comma-separated fine bin widths in ps for CV output (default: 5).")
    ap.add_argument("--k-values", default="1", help="Comma-separated k values for window = k * binwidth (default: 1).")
    ap.add_argument("--window-ps", type=int, default=None,
                    help="Pairing window in ps directly (overrides k * binwidth_ps).")
    ap.add_argument("--scan-frame-origin", action="store_true", help="Scan frame_origin and select best.")
    ap.add_argument("--frame-origin-ps", type=float, default=0.0, help="Fixed frame_origin_ps (used when not scanning).")
    ap.add_argument("--frame-origin-start-ps", type=float, default=0.0, help="Start for frame_origin scan.")
    ap.add_argument("--frame-origin-stop-ps", type=float, default=None, help="Stop for frame_origin scan (default: binwidth_ps).")
    ap.add_argument("--frame-origin-step-ps", type=float, default=1.0, help="Step for frame_origin scan (default: 1ps).")
    ap.add_argument("--band-bins", type=int, default=1, help="Half-width for diag band fraction (default: 1).")
    ap.add_argument("--accidental-delay-mult", type=int, default=3, help="Frame periods for accidental delay (default: 3).")
    ap.add_argument("--max-events", type=int, default=None, help="Max events to read (debug).")
    ap.add_argument("--out", required=True, help="Output directory.")
    ap.add_argument("--no-csv", action="store_true", help="Disable CSV output.")
    ap.add_argument("--no-png", action="store_true", help="Disable PNG output.")
    ap.add_argument("--quiet", action="store_true", help="Suppress console output.")
    ap.add_argument("--svd-unwrapped", action="store_true", default=True, help="Enable unwrapped edge-guarded JTI output for SVD/Schmidt analysis (default: enabled).")
    ap.add_argument("--no-svd-unwrapped", dest="svd_unwrapped", action="store_false", help="Disable unwrapped edge-guarded JTI output.")
    ap.add_argument("--guard-bins", type=int, default=2, help="Edge guard bins for unwrapped JTI (default: 2).")
    ap.add_argument("--tau0-ps", type=int, default=0, help="Backward-compatible shortcut: sets both --pair-center-ps and --tau-align-ps (default: 0).")
    ap.add_argument("--pair-center-ps", type=int, default=None, help="Pairing window center offset in ps (default: from --tau0-ps).")
    ap.add_argument("--tau-align-ps", type=int, default=None, help="B channel alignment correction for unwrapped SVD output (default: from --tau0-ps).")

    args = ap.parse_args()

    if np is None:
        raise SystemExit(
            f"numpy is missing ({sys.executable}). Install numpy first."
        )

    ttbin = _normalize_path(args.ttbin)
    if not ttbin.exists():
        raise SystemExit(f"ttbin not found: {ttbin}")

    out_dir = _normalize_path(args.out)

    try:
        fine_bins = _parse_int_list(args.fine_bins)
    except Exception:
        raise SystemExit(f"Invalid --fine-bins: {args.fine_bins}")

    try:
        k_values = _parse_int_list(args.k_values)
    except Exception:
        raise SystemExit(f"Invalid --k-values: {args.k_values}")

    # Resolve pair_center_ps and tau_align_ps
    tau0 = args.tau0_ps
    pair_center = args.pair_center_ps if args.pair_center_ps is not None else tau0
    tau_align = args.tau_align_ps if args.tau_align_ps is not None else tau0

    if pair_center is None:
        raise SystemExit("Must provide --tau0-ps or --pair-center-ps")
    if tau_align is None:
        raise SystemExit("Must provide --tau0-ps or --tau-align-ps")

    run_extract(
        ttbin=ttbin,
        raw_ch_a_id=int(args.raw_ch_a_id),
        raw_ch_b_id=int(args.raw_ch_b_id),
        binwidth_ps=int(args.binwidth_ps),
        dimension=int(args.dimensions),
        fine_bins=fine_bins,
        k_values=k_values,
        window_ps_override=args.window_ps,
        scan_frame_origin=bool(args.scan_frame_origin),
        frame_origin_ps=float(args.frame_origin_ps),
        frame_origin_start_ps=float(args.frame_origin_start_ps),
        frame_origin_stop_ps=args.frame_origin_stop_ps,
        frame_origin_step_ps=float(args.frame_origin_step_ps),
        band_bins=int(args.band_bins),
        accidental_delay_mult=int(args.accidental_delay_mult),
        out_dir=out_dir,
        quiet=bool(args.quiet),
        max_events=args.max_events,
        save_csv=not bool(args.no_csv),
        save_png=not bool(args.no_png),
        svd_unwrapped=bool(args.svd_unwrapped),
        guard_bins=int(args.guard_bins),
        tau0_ps=int(tau0) if tau0 is not None else 0,
        pair_center_ps=int(pair_center),
        tau_align_ps=int(tau_align),
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
