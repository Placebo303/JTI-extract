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


PROJECT_ROOT = Path(__file__).resolve().parent.parent


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
    """Accept either a WSL/Linux path or a Windows path like `E:\\Data\\...`."""
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
    """Read a TimeTagger *.ttbin stream into arrays (requires `TimeTagger` Python package)."""
    try:
        from TimeTagger import FileReader as TTFileReader  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "JTI extraction requires the Swabian Instruments `TimeTagger` Python API to parse *.ttbin.\n"
            f"Python={sys.executable} cannot import `TimeTagger`: {exc}\n"
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
) -> tuple[_RawTimetags, Path | None]:
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
        )

    if npz_path is None:
        raise RuntimeError(
            f"No parsed_timebin_data.npz found under: {data_dir}. "
            "Generate it first or provide --ttbin."
        )
    return _read_npz_timebins(npz_path), None


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


def _pairs_from_timetags(
    timetags: _RawTimetags,
    *,
    bin_width_ps: int,
    frame_bins: int,
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
    t0 = TimeTag[Ch == ch_a].astype(np.int64, copy=False)
    t1 = TimeTag[Ch == ch_b].astype(np.int64, copy=False)

    bw = np.int64(int(bin_width_ps))
    b0 = np.floor_divide(t0, bw)
    b1 = np.floor_divide(t1, bw)
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


def _plot_png(path: Path, mat: np.ndarray, *, bin_width_ps: int, title: str) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"matplotlib is required for --plot: {exc}") from exc

    n = int(mat.shape[0])
    dt_fs = float(bin_width_ps) * 1000.0
    centers_fs = (np.arange(n) - (n - 1) / 2.0) * dt_fs

    fig, ax = plt.subplots(figsize=(6.0, 5.0), dpi=160)
    im = ax.imshow(
        mat,
        origin="lower",
        cmap="viridis",
        extent=[centers_fs[0], centers_fs[-1], centers_fs[0], centers_fs[-1]],
        aspect="auto",
    )
    ax.set_title(title)
    ax.set_xlabel("Signal delay (fs)")
    ax.set_ylabel("Idler delay (fs)")
    fig.colorbar(im, ax=ax, label="Intensity (a.u.)" if np.max(mat) <= 1.0 else "Counts")
    fig.tight_layout()
    fig.savefig(str(path))
    plt.close(fig)


def run_extract(
    *,
    data_dir: Path,
    ttbin: Path | None,
    binwidth_ps: Iterable[int],
    dimensions: Iterable[int],
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

    timetags, resolved_ttbin = _load_timetags(
        data_dir=data_dir,
        ttbin=ttbin,
        prefer_ttbin=prefer_ttbin,
        max_events=max_events,
        raw_ch_a_id=raw_ch_a_id,
        raw_ch_b_id=raw_ch_b_id,
        logical_ch_a=logical_ch_a,
        logical_ch_b=logical_ch_b,
    )

    outputs: list[dict] = []
    for bw in binwidth_ps:
        for dim in dimensions:
            frame_bins = int(dim)
            pairs, pairs_meta = _pairs_from_timetags(
                timetags,
                bin_width_ps=int(bw),
                frame_bins=frame_bins,
                logical_ch_a=logical_ch_a,
                logical_ch_b=logical_ch_b,
            )
            counts = _jti_from_pairs(pairs, n_bins=frame_bins)

            acc = np.zeros_like(counts)
            counts_corr = counts.copy()
            if background_subtract:
                counts_corr, acc = _accidentals_subtract(counts)

            peak = None
            shift = (0, 0)
            aligned = counts_corr
            if peak_align:
                aligned, peak, shift = _peak_align_to_center(counts_corr, mode=align_mode)

            normalized = _normalize(aligned, normalize)

            stem = f"{prefix}jti_dim{int(dim)}_bw{int(bw)}ps"
            meta_path = out_dir / f"{stem}.meta.json"
            npz_path = None
            if save_npz:
                npz_path = out_dir / f"{stem}.npz"
                np.savez_compressed(
                    str(npz_path),
                    jti_counts=counts.astype(np.float64),
                    jti_accidentals=acc.astype(np.float64),
                    jti_corrected=counts_corr.astype(np.float64),
                    jti_aligned=aligned.astype(np.float64),
                    jti_normalized=normalized.astype(np.float64),
                    dimension=np.int64(int(dim)),
                    bin_width_ps=np.int64(int(bw)),
                )

            meta = {
                "dimension": int(dim),
                "bin_width_ps": int(bw),
                "frame_duration_ps": float(int(dim) * int(bw)),
                "normalize": normalize,
                "background_subtract": bool(background_subtract),
                "peak_align": bool(peak_align),
                "align_mode": str(align_mode),
                "peak_index_before_align": peak,
                "shift_bins": {"signal": int(shift[0]), "idler": int(shift[1])},
                "roll_shift_bins": {"signal": int(shift[0]), "idler": int(shift[1])},
                "n_pairs": int(pairs.shape[0]),
                "timetags": {
                    "acquisition_duration_s": timetags.acquisition_duration_s,
                    "acquisition_duration_source": timetags.acquisition_duration_source,
                    "raw_ch_a_id": int(raw_ch_a_id),
                    "raw_ch_b_id": int(raw_ch_b_id),
                    "logical_ch_a": int(logical_ch_a),
                    "logical_ch_b": int(logical_ch_b),
                    "ttbin": str(resolved_ttbin) if resolved_ttbin is not None else None,
                },
                "pairs_meta": pairs_meta,
            }
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

            if save_csv:
                _save_csv_matrix(out_dir / f"{stem}.counts.csv", counts)
                _save_csv_matrix(out_dir / f"{stem}.normalized.csv", normalized)

            if plot:
                _plot_png(out_dir / f"{stem}.png", normalized, bin_width_ps=int(bw), title=f"JTI (dim={dim}, bw={bw}ps)")

            outputs.append(
                {
                    "dimension": int(dim),
                    "bin_width_ps": int(bw),
                    "npz": str(npz_path) if npz_path is not None else None,
                    "meta": str(meta_path),
                }
            )
            if not quiet:
                if npz_path is not None:
                    print(str(npz_path))
                if save_csv:
                    print(str(out_dir / f"{stem}.counts.csv"))
                    print(str(out_dir / f"{stem}.normalized.csv"))

    summary = {
        "data_dir": str(data_dir),
        "out_dir": str(out_dir),
        "resolved_ttbin": str(resolved_ttbin) if resolved_ttbin is not None else None,
        "binwidth_ps": list(int(x) for x in binwidth_ps),
        "dimensions": list(int(x) for x in dimensions),
        "outputs": outputs,
    }
    summary_path = out_dir / f"{prefix}jti_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if not quiet:
        print(str(summary_path))
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Extract delay-delay JTI (Joint Temporal Intensity) matrices from TimeTagger .ttbin ToA timetags.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  python extract_jti.py --data \"E:\\\\Data\\\\YourDataset\" --ttbin \"E:\\\\Data\\\\file.ttbin\" "
            "--binwidth-ps 100 --dimensions 16 --out \"E:\\\\Data\\\\YourDataset\\\\jti_out\" --plot\n"
        ),
    )
    ap.add_argument("--data", required=True, help="Dataset directory (also used to search parsed_timebin_data.npz).")
    ap.add_argument("--ttbin", default=None, help="Optional: explicit *.ttbin file path (Windows or WSL).")
    ap.add_argument("--prefer-ttbin", action="store_true", help="Prefer reading *.ttbin even if parsed_timebin_data.npz exists.")
    ap.add_argument("--max-events", type=int, default=None, help="Optional: stop reading after this many events (debug/perf).")
    ap.add_argument("--raw-ch-a-id", type=int, default=1, help="TimeTagger raw channel id for signal/A channel (default: 1).")
    ap.add_argument("--raw-ch-b-id", type=int, default=2, help="TimeTagger raw channel id for idler/B channel (default: 2).")
    ap.add_argument("--ch-a", type=int, default=0, help="Logical channel value for signal/A in parsed data (default: 0).")
    ap.add_argument("--ch-b", type=int, default=1, help="Logical channel value for idler/B in parsed data (default: 1).")
    ap.add_argument("--binwidth-ps", default="100", help="Comma-separated bin widths in ps.")
    ap.add_argument("--dimensions", default="16", help="Comma-separated dimensions (also used as frame bins per axis).")
    ap.add_argument("--out", default=None, help="Output directory (default: the ttbin folder if available; otherwise --data).")
    ap.add_argument("--no-csv", action="store_true", help="Disable CSV export (CSV is the default output format).")
    ap.add_argument("--npz", action="store_true", help="Also save NPZ (arrays) for each output.")
    ap.add_argument("--plot", action="store_true", help="Also save a normalized heatmap PNG.")
    ap.add_argument("--no-bg", action="store_true", help="Disable accidentals background subtraction.")
    ap.add_argument("--no-align", action="store_true", help="Disable peak alignment to (0,0) (center bin).")
    ap.add_argument(
        "--align-mode",
        default="roll",
        choices=["roll", "pad", "tile"],
        help=(
            "Peak alignment mode when alignment is enabled: "
            "roll=wrap-around shift, pad=zero-padded shift, tile=tiled-window shift (no wrap corners, no loss)."
        ),
    )
    ap.add_argument(
        "--normalize",
        default="sum",
        choices=["none", "sum", "max", "diagmax"],
        help="Normalization mode for output/plot (diagmax: scale so max(diagonal)=1).",
    )
    ap.add_argument("--prefix", default="", help="Prefix for output filenames, e.g. 'run1_'.")
    ap.add_argument("--quiet", action="store_true", help="Suppress console output.")
    args = ap.parse_args()

    if np is None:  # pragma: no cover
        raise SystemExit(
            f"numpy is missing in this Python environment ({sys.executable}). "
            "Run with a Python that has numpy installed."
        )

    data_dir = _normalize_path(args.data)
    if not data_dir.exists():
        raise SystemExit(f"data dir not found: {data_dir}")

    ttbin = _normalize_path(args.ttbin) if args.ttbin else None
    out_dir = Path(args.out) if args.out else None
    if out_dir is None:
        # Default: place outputs next to the source ttbin if one is explicitly provided; otherwise in the dataset dir.
        out_dir = (ttbin.parent if ttbin is not None else data_dir)

    # Common pitfall: users confuse logical channel labels (--ch-a/--ch-b) with TimeTagger raw channel ids.
    # When reading *.ttbin, raw ids are selected with --raw-ch-*-id; logical labels are arbitrary and only used
    # after mapping. Warn for the most frequent mistake pattern.
    if (ttbin is not None or bool(args.prefer_ttbin)) and (
        int(args.ch_a) not in (0, 1) or int(args.ch_b) not in (0, 1)
    ):
        print(
            "Warning: when reading *.ttbin, use --raw-ch-a-id/--raw-ch-b-id to select hardware channels; "
            "--ch-a/--ch-b are logical labels after mapping (usually 0 and 1).",
            file=sys.stderr,
        )
    binwidth_ps = _parse_int_list(args.binwidth_ps)
    dimensions = _parse_int_list(args.dimensions)

    run_extract(
        data_dir=data_dir,
        ttbin=ttbin,
        binwidth_ps=binwidth_ps,
        dimensions=dimensions,
        out_dir=out_dir,
        quiet=bool(args.quiet),
        max_events=args.max_events,
        raw_ch_a_id=int(args.raw_ch_a_id),
        raw_ch_b_id=int(args.raw_ch_b_id),
        logical_ch_a=int(args.ch_a),
        logical_ch_b=int(args.ch_b),
        prefer_ttbin=bool(args.prefer_ttbin),
        background_subtract=not bool(args.no_bg),
        peak_align=not bool(args.no_align),
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
