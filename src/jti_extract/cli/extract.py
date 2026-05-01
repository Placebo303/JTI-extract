#!/usr/bin/env python3
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


@dataclass(frozen=True)
class _RawTimetags:
    # Channel mapping convention: Ch is float array with 0/1 for valid events and NaN otherwise.
    Ch: np.ndarray
    TimeTag: np.ndarray
    overflow_types: np.ndarray | None
    missed_events: np.ndarray | None
    acquisition_duration_s: float | None
    acquisition_duration_source: str | None


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
    """Accept either a WSL/Linux path or a Windows drive path."""
    s = str(raw).strip()

    is_windows_abs = len(s) >= 3 and s[1] == ":" and (s[2] == "\\" or s[2] == "/")
    if not is_windows_abs:
        return Path(s)

    if os.name == "nt":
        return Path(s)

    # WSL/Linux: convert Windows drive paths to Linux paths.
    try:
        out = subprocess.check_output(["wslpath", "-a", s], text=True).strip()
        if out:
            return Path(out)
    except Exception:
        drive = s[0].lower()
        rest = s[2:].replace("\\", "/").lstrip("/")
        return Path(f"/mnt/{drive}/{rest}")

    return Path(s)


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
            acquisition_duration_s = float(span) * 1e-12  # project convention: timetag in ps
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


def _read_ttbin_timetags(
    ttbin_path: Path,
    *,
    max_events: int | None,
    raw_ch_a_id: int,
    raw_ch_b_id: int,
    logical_ch_a: int,
    logical_ch_b: int,
) -> _RawTimetags:
    """Read a TimeTagger *.ttbin stream into arrays (requires `Swabian.TimeTagger` Python package)."""
    try:
        from Swabian import TimeTagger as _TT
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "JTI extraction requires the Swabian Instruments `Swabian.TimeTagger` Python API to parse *.ttbin.\n"
            f"Python={sys.executable} cannot import `from Swabian import TimeTagger`: {exc}\n"
            "\n"
            "Notes:\n"
            "- The PyPI packages named `TimeTagger` / `timetagger` are NOT the required library.\n"
            "- Fix by installing Swabian's Time Tagger software + Python bindings for your Python version,\n"
            "  then re-run with the same Python environment.\n"
            "- Alternative: generate `parsed_timebin_data.npz` under --data (or its known subfolders) so this\n"
            "  script can run without `TimeTagger` (and do not pass --ttbin / --prefer-ttbin)."
        ) from exc

    channels: list[int] = []
    timestamps: list[int] = []
    event_types: list[int] = []
    missed: list[int] = []

    reader = _TT.FileReader(str(ttbin_path))
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

    # Map valid TimeTag events (eventType==0): raw channel ids -> 0/1.
    Ch = np.full(channel.shape, np.nan, dtype=float)
    valid = overflow_types == 0
    Ch[np.logical_and(valid, channel == int(raw_ch_a_id))] = float(int(logical_ch_a))
    Ch[np.logical_and(valid, channel == int(raw_ch_b_id))] = float(int(logical_ch_b))

    acquisition_duration_s = None
    acquisition_source = None
    try:
        if TimeTag.size > 0:
            span = int(max(0, int(np.max(TimeTag)) - int(np.min(TimeTag))))
            acquisition_duration_s = float(span) * 1e-12  # project convention: ps -> s
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


def _load_timetags(
    *,
    data_dir: Path,
    ttbin: Path | None,
    prefer_ttbin: bool,
    max_events: int | None,
    raw_ch_a_id: int,
    raw_ch_b_id: int,
    logical_ch_a: int,
    logical_ch_b: int,
) -> tuple[_RawTimetags, Path | None, str]:
    npz_candidates = [
        data_dir / "parsed_timebin_data.npz",
        data_dir / "01_raw_parsing" / "parsed_timebin_data.npz",
        data_dir / "results" / "01_raw_parsing" / "parsed_timebin_data.npz",
    ]
    npz_path = next((p for p in npz_candidates if p.exists()), None)

    use_ttbin = prefer_ttbin or (ttbin is not None) or (npz_path is None)
    if use_ttbin:
        if ttbin is None:
            ttbin_files = sorted(data_dir.glob("*.ttbin"))
            if not ttbin_files:
                raise RuntimeError(
                    f"No *.ttbin found under: {data_dir}. "
                    "Provide --ttbin or generate parsed_timebin_data.npz first."
                )
            ttbin = ttbin_files[0]
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

    if npz_path is None:
        raise RuntimeError(
            f"No parsed_timebin_data.npz found under: {data_dir}. "
            "Generate it first or provide --ttbin."
        )
    return _read_npz_timebins(npz_path), None, "parsed_timebin_data.npz"


def _unique_frames_single_hit(frames: np.ndarray, data: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Given sorted `frames`, keep only frames that appear exactly once, returning (frames, data) for those hits."""
    if frames.size == 0:
        return frames, data
    if frames.size == 1:
        return frames, data

    change_idx = np.flatnonzero(frames[1:] != frames[:-1]) + 1
    starts = np.concatenate(([0], change_idx))
    ends = np.concatenate((change_idx, [frames.size]))
    counts = ends - starts
    keep = counts == 1
    kept_starts = starts[keep]
    return frames[kept_starts], data[kept_starts]


def _time_tags_to_bins(times_ps: np.ndarray, *, bin_width_ps: int, frame_origin_ps: float) -> np.ndarray:
    shifted = times_ps.astype(np.float64, copy=False) - float(frame_origin_ps)
    bins = np.floor(shifted / float(bin_width_ps))
    return bins.astype(np.int64, copy=False)


def _pairs_from_timetags(
    timetags: _RawTimetags,
    *,
    bin_width_ps: int,
    frame_bins: int,
    frame_origin_ps: float,
    logical_ch_a: int,
    logical_ch_b: int,
) -> tuple[np.ndarray, dict]:
    """Return (dA,dB) pairs (frame-local bin index) using strict single-hit-per-frame matching."""
    if bin_width_ps <= 0:
        raise ValueError("bin_width_ps must be positive")
    if frame_bins <= 0:
        raise ValueError("frame_bins must be positive")

    Ch = timetags.Ch
    TimeTag = timetags.TimeTag
    if Ch.shape != TimeTag.shape:
        raise ValueError(f"Ch and TimeTag shape mismatch: {Ch.shape} vs {TimeTag.shape}")

    ch_a = float(int(logical_ch_a))
    ch_b = float(int(logical_ch_b))
    t0 = TimeTag[Ch == ch_a]
    t1 = TimeTag[Ch == ch_b]

    b0 = _time_tags_to_bins(t0, bin_width_ps=int(bin_width_ps), frame_origin_ps=float(frame_origin_ps))
    b1 = _time_tags_to_bins(t1, bin_width_ps=int(bin_width_ps), frame_origin_ps=float(frame_origin_ps))
    b0.sort()
    b1.sort()

    N = np.int64(int(frame_bins))
    f0 = np.floor_divide(b0, N)
    d0 = np.mod(b0, N).astype(np.int64, copy=False)
    f1 = np.floor_divide(b1, N)
    d1 = np.mod(b1, N).astype(np.int64, copy=False)

    f0u, d0u = _unique_frames_single_hit(f0, d0)
    f1u, d1u = _unique_frames_single_hit(f1, d1)

    common, i0, i1 = np.intersect1d(f0u, f1u, assume_unique=True, return_indices=True)
    pairs = np.column_stack((d0u[i0], d1u[i1])).astype(np.int64, copy=False)
    meta = {
        "n_events_total": int(TimeTag.size),
        "n_events_ch0": int(t0.size),
        "n_events_ch1": int(t1.size),
        "n_frames_common": int(common.size),
        "n_pairs": int(pairs.shape[0]),
        "frame_origin_ps": float(frame_origin_ps),
    }
    return pairs, meta


def _jti_from_pairs(pairs: np.ndarray, *, n_bins: int) -> np.ndarray:
    jti = np.zeros((int(n_bins), int(n_bins)), dtype=np.float64)
    if pairs.size == 0:
        return jti
    a = pairs[:, 0].astype(np.int64, copy=False)
    b = pairs[:, 1].astype(np.int64, copy=False)
    valid = (a >= 0) & (a < int(n_bins)) & (b >= 0) & (b < int(n_bins))
    if not np.any(valid):
        return jti
    np.add.at(jti, (a[valid], b[valid]), 1.0)
    return jti


def compute_jti_diagnostics(counts: np.ndarray) -> dict[str, float]:
    total_sum = float(np.sum(counts))
    diag_main_sum = float(np.trace(counts))
    diag_pm1_sum = float(np.trace(counts, offset=1) + np.trace(counts, offset=-1))

    if total_sum <= 0.0:
        diag_main_fraction = 0.0
        diag_pm1_fraction = 0.0
        diag_contrast = 0.0
    else:
        diag_main_fraction = diag_main_sum / total_sum
        diag_pm1_fraction = diag_pm1_sum / total_sum
        diag_contrast = diag_main_fraction - diag_pm1_fraction

    return {
        "diag_main_sum": diag_main_sum,
        "diag_pm1_sum": diag_pm1_sum,
        "total_sum": total_sum,
        "diag_main_fraction": diag_main_fraction,
        "diag_pm1_fraction": diag_pm1_fraction,
        "diag_contrast": diag_contrast,
    }


def _accidentals_subtract(counts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    total = float(np.sum(counts))
    if not _finite(total) or total <= 0:
        return counts.copy(), np.zeros_like(counts, dtype=np.float64)
    r = np.sum(counts, axis=1)
    c = np.sum(counts, axis=0)
    acc = np.outer(r, c) / total
    corr = counts - acc
    corr = np.maximum(corr, 0.0)
    return corr, acc


def _shift_zero_pad(mat: np.ndarray, shift: tuple[int, int]) -> np.ndarray:
    dy, dx = int(shift[0]), int(shift[1])
    out = np.zeros_like(mat)

    if mat.size == 0:
        return out

    h, w = int(mat.shape[0]), int(mat.shape[1])

    # Destination ranges.
    y0 = max(0, dy)
    y1 = min(h, h + dy)
    x0 = max(0, dx)
    x1 = min(w, w + dx)

    # Corresponding source ranges.
    sy0 = max(0, -dy)
    sy1 = sy0 + (y1 - y0)
    sx0 = max(0, -dx)
    sx1 = sx0 + (x1 - x0)

    if y1 <= y0 or x1 <= x0:
        return out

    out[y0:y1, x0:x1] = mat[sy0:sy1, sx0:sx1]
    return out


def _shift_center_tile_window(mat: np.ndarray, peak: tuple[int, int], center: tuple[int, int]) -> np.ndarray:
    """
    Align by taking an NxN window from a 3x3 tiled version of `mat`.

    This avoids corner wrap artifacts while preserving all data (no zero-padding loss),
    which is often preferable for modulo/frame-based JTI visualizations.
    """
    h, w = int(mat.shape[0]), int(mat.shape[1])
    tiled = np.tile(mat, (3, 3))

    peak_y = int(peak[0]) + h
    peak_x = int(peak[1]) + w

    y0 = peak_y - int(center[0])
    x0 = peak_x - int(center[1])
    return tiled[y0 : y0 + h, x0 : x0 + w]


def _peak_align_to_center(
    mat: np.ndarray,
    *,
    mode: str = "roll",
) -> tuple[np.ndarray, tuple[int, int] | None, tuple[int, int]]:
    if mat.size == 0 or not np.any(mat):
        return mat.copy(), None, (0, 0)
    peak = np.unravel_index(int(np.argmax(mat)), mat.shape)
    center = (mat.shape[0] // 2, mat.shape[1] // 2)
    shift = (int(center[0] - peak[0]), int(center[1] - peak[1]))

    m = str(mode).strip().lower()
    if m in {"roll", "wrap"}:
        out = np.roll(np.roll(mat, shift[0], axis=0), shift[1], axis=1)
    elif m in {"pad", "zero", "zeropad", "zero_pad"}:
        out = _shift_zero_pad(mat, shift)
    elif m in {"tile", "window", "tilewindow", "tile_window"}:
        out = _shift_center_tile_window(mat, peak, center)
    else:
        raise ValueError(f"unknown align mode: {mode} (expected roll/pad/tile)")
    return out, (int(peak[0]), int(peak[1])), shift


def _normalize(mat: np.ndarray, mode: str) -> np.ndarray:
    mode = str(mode).strip().lower()
    if mode in {"none", ""}:
        return mat.copy()
    if mode == "sum":
        s = float(np.sum(mat))
        return (mat / s) if s > 0 else mat.copy()
    if mode == "max":
        m = float(np.max(mat)) if mat.size else 0.0
        return (mat / m) if m > 0 else mat.copy()
    if mode in {"diagmax", "diag_max", "diagonalmax", "diagonal_max"}:
        # Normalize so the maximum value on the main diagonal becomes 1.
        if mat.size == 0:
            return mat.copy()
        d = np.diag(mat)
        m = float(np.max(d)) if d.size else 0.0
        return (mat / m) if m > 0 else mat.copy()
    raise ValueError(f"unknown normalize mode: {mode} (expected none/sum/max/diagmax)")


def _save_csv_matrix(path: Path, mat: np.ndarray) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([""] + list(range(int(mat.shape[1]))))
        for i in range(int(mat.shape[0])):
            w.writerow([i] + [float(x) for x in mat[i, :].tolist()])


def _save_frame_origin_scan_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "frame_origin_ps",
        "dimension",
        "bin_width_ps",
        "n_pairs",
        "total_sum",
        "diag_main_sum",
        "diag_pm1_sum",
        "diag_main_fraction",
        "diag_pm1_fraction",
        "diag_contrast",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row[k] for k in fieldnames})


def _plot_png(path: Path, mat: np.ndarray, *, title: str) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
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
    fig.colorbar(im, ax=ax, label="Counts")
    fig.tight_layout()
    fig.savefig(str(path))
    plt.close(fig)


def _iter_frame_origins(start_ps: float, stop_ps: float, step_ps: float) -> list[float]:
    if step_ps <= 0:
        raise ValueError("frame_origin_step_ps must be positive")
    if stop_ps < start_ps:
        raise ValueError("frame_origin_stop_ps must be >= frame_origin_start_ps")

    values: list[float] = []
    current = float(start_ps)
    tolerance = abs(step_ps) * 1e-9 + 1e-12
    while current <= stop_ps + tolerance:
        values.append(float(round(current, 12)))
        current += step_ps
    return values


def _select_best_frame_origin(rows: list[dict]) -> dict:
    if not rows:
        raise ValueError("frame-origin scan rows must not be empty")

    def _key(row: dict) -> tuple[float, float, float, float]:
        return (
            float(row["diag_main_fraction"]),
            -float(row["diag_pm1_fraction"]),
            float(row["diag_contrast"]),
            -float(row["frame_origin_ps"]),
        )

    best = max(rows, key=_key)
    return {
        "best_frame_origin_ps": float(best["frame_origin_ps"]),
        "selection_rule": (
            "maximize diag_main_fraction; then minimize diag_pm1_fraction; "
            "then maximize diag_contrast; then choose the smallest frame_origin_ps"
        ),
        "dimension": int(best["dimension"]),
        "bin_width_ps": int(best["bin_width_ps"]),
        "best_diag_main_fraction": float(best["diag_main_fraction"]),
        "best_diag_pm1_fraction": float(best["diag_pm1_fraction"]),
        "best_diag_contrast": float(best["diag_contrast"]),
    }


def _counts_for_frame_origin(
    timetags: _RawTimetags,
    *,
    bin_width_ps: int,
    frame_bins: int,
    frame_origin_ps: float,
    logical_ch_a: int,
    logical_ch_b: int,
) -> tuple[np.ndarray, dict, dict[str, float]]:
    pairs, pairs_meta = _pairs_from_timetags(
        timetags,
        bin_width_ps=int(bin_width_ps),
        frame_bins=int(frame_bins),
        frame_origin_ps=float(frame_origin_ps),
        logical_ch_a=logical_ch_a,
        logical_ch_b=logical_ch_b,
    )
    counts = _jti_from_pairs(pairs, n_bins=int(frame_bins))
    diagnostics = compute_jti_diagnostics(counts)
    return counts, pairs_meta, diagnostics


def _optional_analysis_outputs(
    counts: np.ndarray,
    *,
    background_subtract: bool,
    peak_align: bool,
    align_mode: str,
    normalize: str,
) -> tuple[dict, dict]:
    analysis_options = {
        "background_subtract": bool(background_subtract),
        "peak_align": bool(peak_align),
        "align_mode": str(align_mode),
        "normalize": str(normalize),
    }
    if not background_subtract and not peak_align and str(normalize).lower() in {"none", ""}:
        return analysis_options, {}

    accidentals = np.zeros_like(counts)
    corrected = counts.copy()
    if background_subtract:
        corrected, accidentals = _accidentals_subtract(counts)

    peak = None
    shift = (0, 0)
    aligned = corrected
    if peak_align:
        aligned, peak, shift = _peak_align_to_center(corrected, mode=align_mode)

    normalized = _normalize(aligned, normalize)
    return analysis_options, {
        "jti_accidentals": accidentals.astype(np.float64),
        "jti_corrected": corrected.astype(np.float64),
        "jti_aligned": aligned.astype(np.float64),
        "jti_normalized": normalized.astype(np.float64),
        "peak_index_before_align": peak,
        "shift_bins": {"signal": int(shift[0]), "idler": int(shift[1])},
    }


def run_extract(
    *,
    data_dir: Path,
    ttbin: Path | None,
    binwidth_ps: Iterable[int],
    dimensions: Iterable[int],
    frame_origin_ps: float,
    scan_frame_origin: bool,
    frame_origin_start_ps: float,
    frame_origin_stop_ps: float | None,
    frame_origin_step_ps: float,
    out_dir: Path,
    quiet: bool,
    max_events: int | None,
    raw_ch_a_id: int,
    raw_ch_b_id: int,
    logical_ch_a: int,
    logical_ch_b: int,
    prefer_ttbin: bool,
    background_subtract: bool,
    peak_align: bool,
    align_mode: str,
    normalize: str,
    save_csv: bool,
    save_npz: bool,
    plot: bool,
    prefix: str,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)

    timetags, resolved_ttbin, input_source = _load_timetags(
        data_dir=data_dir,
        ttbin=ttbin,
        prefer_ttbin=prefer_ttbin,
        max_events=max_events,
        raw_ch_a_id=raw_ch_a_id,
        raw_ch_b_id=raw_ch_b_id,
        logical_ch_a=logical_ch_a,
        logical_ch_b=logical_ch_b,
    )

    binwidth_values = [int(x) for x in binwidth_ps]
    dimension_values = [int(x) for x in dimensions]
    if scan_frame_origin and (len(binwidth_values) != 1 or len(dimension_values) != 1):
        raise SystemExit(
            "--scan-frame-origin only supports a single --binwidth-ps value and a single --dimensions value."
        )
    if scan_frame_origin and frame_origin_step_ps <= 0:
        raise SystemExit("--frame-origin-step-ps must be positive when --scan-frame-origin is enabled.")

    outputs: list[dict] = []
    for bw in binwidth_values:
        for dim in dimension_values:
            frame_bins = int(dim)
            stem = f"{prefix}jti_dim{int(dim)}_bw{int(bw)}ps"
            scan_csv_path = None
            scan_best_path = None
            best_frame_origin_payload = None
            best_counts_csv_path = None

            if scan_frame_origin:
                stop_ps = float(frame_origin_stop_ps if frame_origin_stop_ps is not None else bw)
                scan_rows: list[dict] = []
                for t0 in _iter_frame_origins(float(frame_origin_start_ps), stop_ps, float(frame_origin_step_ps)):
                    scan_counts, scan_pairs_meta, scan_diag = _counts_for_frame_origin(
                        timetags,
                        bin_width_ps=int(bw),
                        frame_bins=frame_bins,
                        frame_origin_ps=float(t0),
                        logical_ch_a=logical_ch_a,
                        logical_ch_b=logical_ch_b,
                    )
                    scan_rows.append(
                        {
                            "frame_origin_ps": float(t0),
                            "dimension": int(dim),
                            "bin_width_ps": int(bw),
                            "n_pairs": int(scan_pairs_meta["n_pairs"]),
                            **scan_diag,
                        }
                    )

                scan_csv_path = out_dir / f"{stem}.frame_origin_scan.csv"
                _save_frame_origin_scan_csv(scan_csv_path, scan_rows)
                best_frame_origin_payload = _select_best_frame_origin(scan_rows)
                scan_best_path = out_dir / f"{stem}.frame_origin_scan_best.json"
                scan_best_path.write_text(
                    json.dumps(best_frame_origin_payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

            counts, pairs_meta, diagnostics = _counts_for_frame_origin(
                timetags,
                bin_width_ps=int(bw),
                frame_bins=frame_bins,
                frame_origin_ps=float(frame_origin_ps),
                logical_ch_a=logical_ch_a,
                logical_ch_b=logical_ch_b,
            )
            analysis_options, analysis_arrays = _optional_analysis_outputs(
                counts,
                background_subtract=background_subtract,
                peak_align=peak_align,
                align_mode=align_mode,
                normalize=normalize,
            )

            meta_path = out_dir / f"{stem}.meta.json"
            npz_path = None
            if save_npz:
                npz_payload: dict[str, object] = {
                    "jti_counts": counts.astype(np.float64),
                    "dimension": np.int64(int(dim)),
                    "bin_width_ps": np.int64(int(bw)),
                    "frame_origin_ps": np.float64(float(frame_origin_ps)),
                }
                for key, value in analysis_arrays.items():
                    if isinstance(value, np.ndarray):
                        npz_payload[key] = value
                npz_path = out_dir / f"{stem}.npz"
                np.savez_compressed(str(npz_path), **npz_payload)

            meta = {
                "dimension": int(dim),
                "bin_width_ps": int(bw),
                "frame_duration_ps": float(int(dim) * int(bw)),
                "frame_origin_ps": float(frame_origin_ps),
                "n_pairs": int(pairs_meta["n_pairs"]),
                "single_hit_policy": "strict_single_hit_per_frame",
                "raw_ch_a_id": int(raw_ch_a_id),
                "raw_ch_b_id": int(raw_ch_b_id),
                "logical_ch_a": int(logical_ch_a),
                "logical_ch_b": int(logical_ch_b),
                "input_source": str(input_source),
                "resolved_ttbin": str(resolved_ttbin) if resolved_ttbin is not None else None,
                "scan_frame_origin_enabled": bool(scan_frame_origin),
                "diagnostics": diagnostics,
                "pairs_meta": pairs_meta,
                "timetags": {
                    "acquisition_duration_s": timetags.acquisition_duration_s,
                    "acquisition_duration_source": timetags.acquisition_duration_source,
                },
            }
            if scan_csv_path is not None and scan_best_path is not None:
                meta["frame_origin_scan_csv"] = str(scan_csv_path)
                meta["frame_origin_scan_best_json"] = str(scan_best_path)
            if best_frame_origin_payload is not None:
                best_counts, best_pairs_meta, best_diagnostics = _counts_for_frame_origin(
                    timetags,
                    bin_width_ps=int(bw),
                    frame_bins=frame_bins,
                    frame_origin_ps=float(best_frame_origin_payload["best_frame_origin_ps"]),
                    logical_ch_a=logical_ch_a,
                    logical_ch_b=logical_ch_b,
                )
                best_counts_csv_path = out_dir / f"{stem}.best_frame_origin.counts.csv"
                if save_csv:
                    _save_csv_matrix(best_counts_csv_path, best_counts)
                meta["best_frame_origin_result"] = {
                    "frame_origin_ps": float(best_frame_origin_payload["best_frame_origin_ps"]),
                    "counts_csv": str(best_counts_csv_path) if save_csv else None,
                    "n_pairs": int(best_pairs_meta["n_pairs"]),
                    "diagnostics": best_diagnostics,
                }
            if analysis_options["background_subtract"] or analysis_options["peak_align"] or analysis_options["normalize"].lower() != "none":
                optional_postprocess = dict(analysis_options)
                if "peak_index_before_align" in analysis_arrays:
                    optional_postprocess["peak_index_before_align"] = analysis_arrays["peak_index_before_align"]
                if "shift_bins" in analysis_arrays:
                    optional_postprocess["shift_bins"] = analysis_arrays["shift_bins"]
                meta["optional_postprocess"] = optional_postprocess
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

            if save_csv:
                _save_csv_matrix(out_dir / f"{stem}.counts.csv", counts)
            if plot:
                _plot_png(
                    out_dir / f"{stem}.png",
                    counts,
                    title=f"Discrete Joint Time-Bin Counts (dim={dim}, bw={bw}ps, t0={frame_origin_ps}ps)",
                )

            outputs.append(
                {
                    "dimension": int(dim),
                    "bin_width_ps": int(bw),
                    "frame_origin_ps": float(frame_origin_ps),
                    "counts_csv": str(out_dir / f"{stem}.counts.csv") if save_csv else None,
                    "best_frame_origin_counts_csv": str(best_counts_csv_path) if best_counts_csv_path is not None and save_csv else None,
                    "meta": str(meta_path),
                    "npz": str(npz_path) if npz_path is not None else None,
                    "frame_origin_scan_csv": str(scan_csv_path) if scan_csv_path is not None else None,
                    "frame_origin_scan_best_json": str(scan_best_path) if scan_best_path is not None else None,
                }
            )
            if not quiet:
                if save_csv:
                    print(str(out_dir / f"{stem}.counts.csv"))
                    if best_counts_csv_path is not None:
                        print(str(best_counts_csv_path))
                print(str(meta_path))
                if npz_path is not None:
                    print(str(npz_path))
                if scan_csv_path is not None:
                    print(str(scan_csv_path))
                if scan_best_path is not None:
                    print(str(scan_best_path))

    summary = {
        "data_dir": str(data_dir),
        "out_dir": str(out_dir),
        "input_source": str(input_source),
        "resolved_ttbin": str(resolved_ttbin) if resolved_ttbin is not None else None,
        "binwidth_ps": binwidth_values,
        "dimensions": dimension_values,
        "frame_origin_ps": float(frame_origin_ps),
        "scan_frame_origin_enabled": bool(scan_frame_origin),
        "outputs": outputs,
    }
    summary_path = out_dir / f"{prefix}jti_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if not quiet:
        print(str(summary_path))
    return summary


def _self_test_counts_and_diagnostics() -> None:
    counts = _jti_from_pairs(np.asarray([(0, 0), (1, 1), (2, 2)], dtype=np.int64), n_bins=4)
    assert float(np.trace(counts)) == 3.0, "main diagonal sum should be 3"

    counts_pm1 = _jti_from_pairs(np.asarray([(0, 1), (1, 2), (2, 3)], dtype=np.int64), n_bins=4)
    diag = compute_jti_diagnostics(counts_pm1)
    assert diag["diag_pm1_sum"] == 3.0, "pm1 diagonal sum should be 3"


def _self_test_frame_origin_scan() -> None:
    timetags = _RawTimetags(
        Ch=np.asarray([0.0, 1.0, 0.0, 1.0], dtype=float),
        TimeTag=np.asarray([10, 20, 110, 120], dtype=np.int64),
        overflow_types=None,
        missed_events=None,
        acquisition_duration_s=None,
        acquisition_duration_source=None,
    )
    out_dir = Path(__file__).resolve().parent / ".selftest_tmp"
    out_dir.mkdir(exist_ok=True)
    try:
        rows: list[dict] = []
        for t0 in _iter_frame_origins(0.0, 50.0, 25.0):
            pairs, pairs_meta = _pairs_from_timetags(
                timetags,
                bin_width_ps=50,
                frame_bins=4,
                frame_origin_ps=t0,
                logical_ch_a=0,
                logical_ch_b=1,
            )
            rows.append(
                {
                    "frame_origin_ps": t0,
                    "dimension": 4,
                    "bin_width_ps": 50,
                    "n_pairs": int(pairs_meta["n_pairs"]),
                    **compute_jti_diagnostics(_jti_from_pairs(pairs, n_bins=4)),
                }
            )

        csv_path = out_dir / "toy_jti_dim4_bw50ps.frame_origin_scan.csv"
        best_path = out_dir / "toy_jti_dim4_bw50ps.frame_origin_scan_best.json"
        _save_frame_origin_scan_csv(csv_path, rows)
        best_path.write_text(json.dumps(_select_best_frame_origin(rows), ensure_ascii=False, indent=2), encoding="utf-8")
        assert csv_path.exists(), "scan CSV should be created"
        assert best_path.exists(), "scan best JSON should be created"
        assert "frame_origin_ps" in csv_path.read_text(encoding="utf-8")
        assert "best_frame_origin_ps" in json.loads(best_path.read_text(encoding="utf-8"))
    finally:
        for path in [out_dir / "toy_jti_dim4_bw50ps.frame_origin_scan.csv", out_dir / "toy_jti_dim4_bw50ps.frame_origin_scan_best.json"]:
            if path.exists():
                path.unlink()
        if out_dir.exists():
            out_dir.rmdir()


def _run_self_tests() -> None:
    _self_test_counts_and_diagnostics()
    _self_test_frame_origin_scan()
    print("self-test passed")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Extract a discrete joint time-bin coincidence matrix in the arrival-time basis "
            "from pre-aligned timetag data."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  python extract_jti.py --data \"<path/to/dataset>\" --binwidth-ps 200 "
            "--dimensions 32 --frame-origin-ps 0 --out results/jti_out\n"
        ),
    )
    ap.add_argument("--data", required=False, help="Dataset directory (also used to search parsed_timebin_data.npz).")
    ap.add_argument("--ttbin", default=None, help="Optional: explicit *.ttbin file path (Windows or WSL).")
    ap.add_argument("--prefer-ttbin", action="store_true", help="Prefer reading *.ttbin even if parsed_timebin_data.npz exists.")
    ap.add_argument("--max-events", type=int, default=None, help="Optional: stop reading after this many events (debug/perf).")
    ap.add_argument("--raw-ch-a-id", type=int, default=1, help="TimeTagger raw channel id for signal/A channel (default: 1).")
    ap.add_argument("--raw-ch-b-id", type=int, default=2, help="TimeTagger raw channel id for idler/B channel (default: 2).")
    ap.add_argument("--ch-a", type=int, default=0, help="Logical channel value for signal/A in parsed data (default: 0).")
    ap.add_argument("--ch-b", type=int, default=1, help="Logical channel value for idler/B in parsed data (default: 1).")
    ap.add_argument("--binwidth-ps", default="100", help="Comma-separated bin widths in ps.")
    ap.add_argument("--dimensions", default="16", help="Comma-separated dimensions (also used as frame bins per axis).")
    ap.add_argument("--frame-origin-ps", type=float, default=0.0, help="Common time origin t0 in ps for discrete time-bin mapping.")
    ap.add_argument("--scan-frame-origin", action="store_true", help="Scan frame-origin candidates and export diagonal diagnostics.")
    ap.add_argument("--frame-origin-start-ps", type=float, default=0.0, help="Start value for frame-origin scan in ps.")
    ap.add_argument("--frame-origin-stop-ps", type=float, default=None, help="Stop value for frame-origin scan in ps. Defaults to the selected bin width.")
    ap.add_argument("--frame-origin-step-ps", type=float, default=5.0, help="Step size for frame-origin scan in ps.")
    ap.add_argument("--out", default=None, help="Output directory (default: the ttbin folder if available; otherwise --data).")
    ap.add_argument("--no-csv", action="store_true", help="Disable CSV export (CSV counts are the default output format).")
    ap.add_argument("--npz", action="store_true", help="Also save NPZ with jti_counts and optional analysis arrays.")
    ap.add_argument("--plot", action="store_true", help="Also save a heatmap PNG derived from raw counts.")
    ap.add_argument("--background-subtract", action="store_true", help="Optional analysis mode for NPZ/meta only. Does not change counts.csv.")
    ap.add_argument("--peak-align", action="store_true", help="Optional analysis mode for NPZ/meta only. Does not change counts.csv.")
    ap.add_argument("--no-bg", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--no-align", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--align-mode", default="roll", choices=["roll", "pad", "tile"], help="Optional analysis mode used with --peak-align.")
    ap.add_argument("--normalize", default="none", choices=["none", "sum", "max", "diagmax"], help="Optional analysis normalization for NPZ/meta only.")
    ap.add_argument("--prefix", default="", help="Prefix for output filenames, e.g. 'run1_'.")
    ap.add_argument("--quiet", action="store_true", help="Suppress console output.")
    ap.add_argument("--self-test", action="store_true", help="Run built-in toy validation and exit.")
    args = ap.parse_args()

    if np is None:  # pragma: no cover
        raise SystemExit(
            f"numpy is missing in this Python environment ({sys.executable}). "
            "Run with a Python that has numpy installed."
        )
    if args.self_test:
        _run_self_tests()
        return 0
    if not args.data:
        raise SystemExit("--data is required unless --self-test is used.")

    data_dir = _normalize_path(args.data)
    if not data_dir.exists():
        raise SystemExit(f"data dir not found: {data_dir}")

    ttbin = _normalize_path(args.ttbin) if args.ttbin else None
    out_dir = Path(args.out) if args.out else None
    if out_dir is None:
        out_dir = (ttbin.parent if ttbin is not None else data_dir)

    if (ttbin is not None or bool(args.prefer_ttbin)) and (int(args.ch_a) not in (0, 1) or int(args.ch_b) not in (0, 1)):
        print(
            "Warning: when reading *.ttbin, use --raw-ch-a-id/--raw-ch-b-id to select hardware channels; "
            "--ch-a/--ch-b are logical labels after mapping (usually 0 and 1).",
            file=sys.stderr,
        )

    background_subtract = bool(args.background_subtract) and not bool(args.no_bg)
    peak_align = bool(args.peak_align) and not bool(args.no_align)

    run_extract(
        data_dir=data_dir,
        ttbin=ttbin,
        binwidth_ps=_parse_int_list(args.binwidth_ps),
        dimensions=_parse_int_list(args.dimensions),
        frame_origin_ps=float(args.frame_origin_ps),
        scan_frame_origin=bool(args.scan_frame_origin),
        frame_origin_start_ps=float(args.frame_origin_start_ps),
        frame_origin_stop_ps=args.frame_origin_stop_ps,
        frame_origin_step_ps=float(args.frame_origin_step_ps),
        out_dir=out_dir,
        quiet=bool(args.quiet),
        max_events=args.max_events,
        raw_ch_a_id=int(args.raw_ch_a_id),
        raw_ch_b_id=int(args.raw_ch_b_id),
        logical_ch_a=int(args.ch_a),
        logical_ch_b=int(args.ch_b),
        prefer_ttbin=bool(args.prefer_ttbin),
        background_subtract=background_subtract,
        peak_align=peak_align,
        align_mode=str(args.align_mode),
        normalize=str(args.normalize),
        save_csv=not bool(args.no_csv),
        save_npz=bool(args.npz),
        plot=bool(args.plot),
        prefix=str(args.prefix or ""),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
