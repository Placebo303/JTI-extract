#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
DEFAULT_TTBIN = ""
DEFAULT_OUT = "results/tdc_layer_scan"
TWO_PI = 2.0 * math.pi


def _normalize_path(raw: str) -> Path:
    return Path(str(raw).strip().strip('"'))


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


def _write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def _safe_ratio(a: float, b: float) -> float:
    return float(a / b) if b else math.nan


def _circular_std(phases: np.ndarray) -> float:
    if phases.size == 0:
        return math.nan
    z = np.mean(np.exp(1j * phases.astype(np.float64, copy=False)))
    r = abs(z)
    if r <= 0:
        return math.inf
    return float(math.sqrt(max(0.0, -2.0 * math.log(min(1.0, r)))))


def _phase_ps(phase_rad: float, period_ps: float) -> float:
    return float((phase_rad % TWO_PI) * float(period_ps) / TWO_PI)


def _hist_cv(hist: np.ndarray) -> float:
    hist = np.asarray(hist, dtype=np.float64)
    mean = float(np.mean(hist)) if hist.size else 0.0
    return float(np.std(hist) / mean) if mean > 0 else math.nan


def _hist_chi2(hist: np.ndarray) -> float:
    hist = np.asarray(hist, dtype=np.float64)
    total = float(np.sum(hist))
    if total <= 0 or hist.size <= 1:
        return math.nan
    mean = total / float(hist.size)
    return float(np.sum((hist - mean) ** 2 / mean) / float(hist.size - 1))


def _hist_stats(hist: np.ndarray) -> dict[str, Any]:
    hist = np.asarray(hist, dtype=np.float64)
    total = float(np.sum(hist))
    mean = float(np.mean(hist)) if hist.size else 0.0
    if total <= 0 or mean <= 0:
        return {
            "total": int(total),
            "bins": int(hist.size),
            "mean": mean,
            "min": 0,
            "max": 0,
            "cv": math.nan,
            "chi2_reduced": math.nan,
            "peak_to_peak_over_mean": math.nan,
            "max_over_mean": math.nan,
            "min_over_mean": math.nan,
        }
    return {
        "total": int(total),
        "bins": int(hist.size),
        "mean": mean,
        "min": int(np.min(hist)),
        "max": int(np.max(hist)),
        "cv": _hist_cv(hist),
        "chi2_reduced": _hist_chi2(hist),
        "peak_to_peak_over_mean": float((np.max(hist) - np.min(hist)) / mean),
        "max_over_mean": float(np.max(hist) / mean),
        "min_over_mean": float(np.min(hist) / mean),
    }


@dataclass
class Tags:
    t_a: np.ndarray
    t_b: np.ndarray
    meta: dict[str, Any]


@dataclass
class PeriodResult:
    layer: str
    periods: np.ndarray
    n_pairs: int
    sums: np.ndarray
    hists: dict[int, np.ndarray]

    def rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for idx, period in enumerate(self.periods.astype(int).tolist()):
            z = self.sums[idx] / float(self.n_pairs) if self.n_pairs else 0.0 + 0.0j
            hist = self.hists[int(period)]
            rows.append(
                {
                    "layer": self.layer,
                    "period_ps": int(period),
                    "n_pairs": int(self.n_pairs),
                    "amplitude": float(abs(z)),
                    "phase_rad": float(np.angle(z)) if self.n_pairs else math.nan,
                    "phase_ps": _phase_ps(float(np.angle(z)), float(period)) if self.n_pairs else math.nan,
                    "chi2_reduced": _hist_chi2(hist),
                    "cv": _hist_cv(hist),
                }
            )
        return rows

    def at_period(self, period_ps: int) -> dict[str, Any]:
        period_ps = int(period_ps)
        matches = np.flatnonzero(self.periods.astype(int) == period_ps)
        if matches.size == 0:
            return {"period_ps": period_ps, "n_pairs": int(self.n_pairs), "amplitude": math.nan, "phase_rad": math.nan, "phase_ps": math.nan, "chi2_reduced": math.nan, "cv": math.nan}
        idx = int(matches[0])
        z = self.sums[idx] / float(self.n_pairs) if self.n_pairs else 0.0 + 0.0j
        hist = self.hists[period_ps]
        return {
            "period_ps": period_ps,
            "n_pairs": int(self.n_pairs),
            "amplitude": float(abs(z)),
            "phase_rad": float(np.angle(z)) if self.n_pairs else math.nan,
            "phase_ps": _phase_ps(float(np.angle(z)), float(period_ps)) if self.n_pairs else math.nan,
            "chi2_reduced": _hist_chi2(hist),
            "cv": _hist_cv(hist),
        }

    def best(self) -> dict[str, Any]:
        if not self.n_pairs:
            return {"period_ps": math.nan, "amplitude": math.nan, "phase_rad": math.nan, "phase_ps": math.nan}
        amps = np.abs(self.sums / float(self.n_pairs))
        idx = int(np.argmax(amps))
        period = int(self.periods[idx])
        phase = float(np.angle(self.sums[idx] / float(self.n_pairs)))
        return {"period_ps": period, "amplitude": float(amps[idx]), "phase_rad": phase, "phase_ps": _phase_ps(phase, float(period))}


class PeriodAccumulator:
    def __init__(self, layer: str, periods: np.ndarray):
        self.layer = str(layer)
        self.periods = periods.astype(np.float64, copy=True)
        self.period_ints = periods.astype(int).tolist()
        self.sums = np.zeros(self.periods.shape, dtype=np.complex128)
        self.hists = {int(p): np.zeros(int(p), dtype=np.int64) for p in self.period_ints}
        self.n_pairs = 0

    def add(self, deltas: np.ndarray) -> None:
        deltas = np.asarray(deltas, dtype=np.int64)
        if deltas.size == 0:
            return
        self.n_pairs += int(deltas.size)
        d = deltas.astype(np.float64, copy=False)
        for idx, p in enumerate(self.periods):
            self.sums[idx] += np.sum(np.exp(1j * TWO_PI * d / p))
            pi = int(p)
            self.hists[pi] += np.bincount(np.mod(deltas, pi), minlength=pi)[:pi]

    def result(self) -> PeriodResult:
        return PeriodResult(self.layer, self.periods.astype(int), int(self.n_pairs), self.sums.copy(), {k: v.copy() for k, v in self.hists.items()})


def load_tags(ttbin: Path, out: Path, ch_a: int, ch_b: int, max_events: int | None) -> Tags:
    out.mkdir(parents=True, exist_ok=True)
    cache = out / f"tags_cache_ch{int(ch_a)}_ch{int(ch_b)}.npz"
    stat = ttbin.stat()
    expected = {
        "ttbin": str(ttbin.resolve()),
        "ttbin_size": int(stat.st_size),
        "ttbin_mtime_ns": int(stat.st_mtime_ns),
        "ch_a": int(ch_a),
        "ch_b": int(ch_b),
        "max_events": int(max_events) if max_events is not None else None,
    }
    if cache.exists():
        try:
            with np.load(str(cache), allow_pickle=False) as z:
                meta = json.loads(str(z["meta_json"].item()))
                if all(meta.get(k) == v for k, v in expected.items()):
                    return Tags(np.asarray(z["t_a"], dtype=np.int64), np.asarray(z["t_b"], dtype=np.int64), meta)
        except Exception:
            pass

    try:
        from TimeTagger import FileReader  # type: ignore
    except Exception as exc:
        raise RuntimeError(f"cannot import Swabian TimeTagger Python API from {sys.executable}: {exc}") from exc

    reader = FileReader(str(ttbin))
    try:
        config: dict[str, Any] = dict(reader.getConfiguration())
    except Exception as exc:
        config = {"getConfiguration_error": repr(exc)}

    chunks_a: list[np.ndarray] = []
    chunks_b: list[np.ndarray] = []
    total = 0
    event_type_counts: Counter[int] = Counter()
    channel_counts: Counter[int] = Counter()

    while reader.hasData():
        n = 1_000_000
        if max_events is not None:
            remaining = int(max_events) - total
            if remaining <= 0:
                break
            n = max(1, min(n, remaining))
        data = reader.getData(n)
        channels = np.asarray(data.getChannels(), dtype=np.int64)
        timestamps = np.asarray(data.getTimestamps(), dtype=np.int64)
        event_types = np.asarray(data.getEventTypes(), dtype=np.int64)
        total += int(timestamps.size)

        for value, count in zip(*np.unique(event_types, return_counts=True)):
            event_type_counts[int(value)] += int(count)
        for value, count in zip(*np.unique(channels, return_counts=True)):
            channel_counts[int(value)] += int(count)

        valid = event_types == 0
        chunks_a.append(timestamps[np.logical_and(valid, channels == int(ch_a))])
        chunks_b.append(timestamps[np.logical_and(valid, channels == int(ch_b))])

    t_a = np.sort(np.concatenate(chunks_a)) if chunks_a else np.array([], dtype=np.int64)
    t_b = np.sort(np.concatenate(chunks_b)) if chunks_b else np.array([], dtype=np.int64)
    span_ps = int(max(t_a[-1] if t_a.size else 0, t_b[-1] if t_b.size else 0) - min(t_a[0] if t_a.size else 0, t_b[0] if t_b.size else 0)) if t_a.size and t_b.size else 0
    meta = {
        **expected,
        "cache_path": str(cache),
        "n_events_read": int(total),
        "n_ch_a": int(t_a.size),
        "n_ch_b": int(t_b.size),
        "span_ps": int(span_ps),
        "span_s": float(span_ps * 1e-12),
        "event_type_counts": {str(k): int(v) for k, v in sorted(event_type_counts.items())},
        "channel_counts": {str(k): int(v) for k, v in sorted(channel_counts.items())},
        "file_configuration": config,
    }
    np.savez_compressed(str(cache), t_a=t_a, t_b=t_b, meta_json=np.array(json.dumps(meta, ensure_ascii=False), dtype=str))
    return Tags(t_a, t_b, meta)


def _iter_all_pair_delta_chunks(t_a: np.ndarray, t_b: np.ndarray, window_ps: int, chunk_events: int = 200_000) -> Iterable[np.ndarray]:
    t_b = np.asarray(t_b, dtype=np.int64)
    for start in range(0, int(t_a.size), int(chunk_events)):
        a = np.asarray(t_a[start : start + int(chunk_events)], dtype=np.int64)
        left = np.searchsorted(t_b, a - int(window_ps), side="left")
        right = np.searchsorted(t_b, a + int(window_ps), side="right")
        total = int(np.sum(right - left))
        if total <= 0:
            continue
        out = np.empty(total, dtype=np.int64)
        pos = 0
        for av, lo, hi in zip(a, left, right):
            n = int(hi - lo)
            if n:
                out[pos : pos + n] = t_b[lo:hi] - int(av)
                pos += n
        yield out[:pos]


def period_scan_all_pairs(layer: str, t_a: np.ndarray, t_b: np.ndarray, window_ps: int, periods: np.ndarray) -> PeriodResult:
    acc = PeriodAccumulator(layer, periods)
    for deltas in _iter_all_pair_delta_chunks(t_a, t_b, window_ps):
        acc.add(deltas)
    return acc.result()


def period_scan_deltas(layer: str, deltas: np.ndarray, periods: np.ndarray) -> PeriodResult:
    acc = PeriodAccumulator(layer, periods)
    acc.add(deltas)
    return acc.result()


def nearest_pairs(t_a: np.ndarray, t_b: np.ndarray, window_ps: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if t_a.size == 0 or t_b.size == 0:
        return np.array([], dtype=np.int64), np.array([], dtype=np.int64), np.array([], dtype=np.int64)
    pos = np.searchsorted(t_b, t_a)
    best_delta = np.full(t_a.shape, np.iinfo(np.int64).max, dtype=np.int64)
    best_t_b = np.zeros(t_a.shape, dtype=np.int64)
    right = pos < t_b.size
    best_delta[right] = t_b[pos[right]] - t_a[right]
    best_t_b[right] = t_b[pos[right]]
    left = pos > 0
    left_delta = t_b[pos[left] - 1] - t_a[left]
    use_left = np.abs(left_delta) < np.abs(best_delta[left])
    left_indices = np.flatnonzero(left)
    replace = left_indices[use_left]
    best_delta[replace] = left_delta[use_left]
    best_t_b[replace] = t_b[pos[replace] - 1]
    keep = np.abs(best_delta) <= int(window_ps)
    return t_a[keep].copy(), best_t_b[keep].copy(), best_delta[keep].copy()


def greedy_unique_pairs(t_a: np.ndarray, t_b: np.ndarray, window_ps: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    i = 0
    j = 0
    out_a: list[int] = []
    out_b: list[int] = []
    out_d: list[int] = []
    n_a = int(t_a.size)
    n_b = int(t_b.size)
    w = int(window_ps)
    while i < n_a and j < n_b:
        av = int(t_a[i])
        while j < n_b and int(t_b[j]) < av - w:
            j += 1
        if j >= n_b:
            break
        candidates: list[tuple[int, int]] = []
        if abs(int(t_b[j]) - av) <= w:
            candidates.append((abs(int(t_b[j]) - av), j))
        if j + 1 < n_b and abs(int(t_b[j + 1]) - av) <= w:
            candidates.append((abs(int(t_b[j + 1]) - av), j + 1))
        if candidates:
            _, jj = min(candidates)
            bv = int(t_b[jj])
            out_a.append(av)
            out_b.append(bv)
            out_d.append(bv - av)
            i += 1
            j = jj + 1
        else:
            i += 1
    return np.asarray(out_a, dtype=np.int64), np.asarray(out_b, dtype=np.int64), np.asarray(out_d, dtype=np.int64)


def _summary_row(layer: str, result: PeriodResult, target_period: int) -> dict[str, Any]:
    at = result.at_period(target_period)
    best = result.best()
    return {
        "layer": layer,
        "n_pairs": int(result.n_pairs),
        "A40": at["amplitude"],
        "phase40_rad": at["phase_rad"],
        "phase40_ps": at["phase_ps"],
        "cv40": at["cv"],
        "chi2_40": at["chi2_reduced"],
        "best_period_ps": best["period_ps"],
        "best_amplitude": best["amplitude"],
        "best_phase_rad": best["phase_rad"],
        "best_phase_ps": best["phase_ps"],
    }


def _shift_surrogate(t_a: np.ndarray, t_b: np.ndarray, rng: np.random.Generator, window_ps: int, span_ps: int) -> tuple[np.ndarray, int]:
    low = max(int(window_ps) * 100, int(window_ps) + 1)
    high = max(low + 1, int(span_ps) - int(window_ps) * 100)
    shift = int(rng.integers(low, high)) if high > low else int(window_ps) * 100
    sign = -1 if int(rng.integers(0, 2)) == 0 else 1
    shifted = t_b + sign * shift
    lo = min(int(t_a[0]) if t_a.size else 0, int(t_b[0]) if t_b.size else 0)
    hi = max(int(t_a[-1]) if t_a.size else 0, int(t_b[-1]) if t_b.size else 0)
    shifted = shifted[(shifted >= lo) & (shifted <= hi)]
    return np.sort(shifted), sign * shift


def _block_shuffle_surrogate(t_b: np.ndarray, block_ps: int, rng: np.random.Generator) -> np.ndarray:
    if t_b.size == 0:
        return t_b.copy()
    t0 = int(t_b[0])
    block_ids = np.floor_divide(t_b - t0, int(block_ps)).astype(np.int64)
    unique_blocks = np.unique(block_ids)
    shuffled = unique_blocks.copy()
    rng.shuffle(shuffled)
    mapping = {int(src): int(dst) for src, dst in zip(unique_blocks.tolist(), shuffled.tolist())}
    out = np.empty_like(t_b)
    for block in unique_blocks.tolist():
        mask = block_ids == int(block)
        src_start = t0 + int(block) * int(block_ps)
        dst_start = t0 + mapping[int(block)] * int(block_ps)
        out[mask] = dst_start + (t_b[mask] - src_start)
    return np.sort(out)


def surrogate_shift_summary(t_a: np.ndarray, t_b: np.ndarray, window_ps: int, periods: np.ndarray, n_shifts: int, seed: int, real_a40: float, span_ps: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rng = np.random.default_rng(int(seed))
    for i in range(int(n_shifts)):
        tb_s, shift = _shift_surrogate(t_a, t_b, rng, window_ps, span_ps)
        result = period_scan_all_pairs(f"surrogate_shift_{i}", t_a, tb_s, window_ps, periods)
        row = _summary_row("surrogate_shift", result, 40)
        row["replicate"] = i
        row["shift_ps"] = int(shift)
        rows.append(row)
    a40 = np.asarray([float(r["A40"]) for r in rows], dtype=np.float64)
    best = [int(r["best_period_ps"]) for r in rows if np.isfinite(float(r["best_period_ps"]))]
    summary = {
        "A40_mean": float(np.mean(a40)) if a40.size else math.nan,
        "A40_std": float(np.std(a40)) if a40.size else math.nan,
        "surrogate_A40_ratio": _safe_ratio(float(np.mean(a40)) if a40.size else math.nan, float(real_a40)),
        "best_period_mode": Counter(best).most_common(1)[0][0] if best else math.nan,
        "n_replicates": int(len(rows)),
    }
    return rows, summary


def surrogate_block_summary(t_a: np.ndarray, t_b: np.ndarray, window_ps: int, periods: np.ndarray, block_ms_values: list[float], seed: int, real_a40: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    summary: dict[str, Any] = {}
    rng = np.random.default_rng(int(seed) + 1000)
    for block_ms in block_ms_values:
        block_ps = int(round(float(block_ms) * 1e9))
        tb_s = _block_shuffle_surrogate(t_b, block_ps, rng)
        result = period_scan_all_pairs(f"surrogate_block_{block_ms:g}ms", t_a, tb_s, window_ps, periods)
        row = _summary_row("surrogate_block_shuffle", result, 40)
        row["block_ms"] = float(block_ms)
        row["block_ps"] = int(block_ps)
        rows.append(row)
        summary[str(block_ms)] = {
            "A40": row["A40"],
            "surrogate_A40_ratio": _safe_ratio(float(row["A40"]), float(real_a40)),
            "best_period_ps": row["best_period_ps"],
        }
    return rows, summary


def time_split_summary(t_a: np.ndarray, t_b: np.ndarray, window_ps: int, periods: np.ndarray, n_splits: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if t_a.size == 0 or t_b.size == 0:
        return [], {"phase40_circular_std": math.nan, "A40_cv": math.nan, "best_period_counts": {}}
    start = min(int(t_a[0]), int(t_b[0]))
    stop = max(int(t_a[-1]), int(t_b[-1]))
    edges = np.linspace(float(start), float(stop), int(n_splits) + 1)
    rows: list[dict[str, Any]] = []
    for i in range(int(n_splits)):
        lo = int(math.floor(edges[i]))
        hi = int(math.floor(edges[i + 1]))
        aa = t_a[(t_a >= lo) & (t_a < hi)]
        bb = t_b[(t_b >= lo) & (t_b < hi)]
        result = period_scan_all_pairs(f"time_split_{i}", aa, bb, window_ps, periods)
        row = _summary_row("time_split", result, 40)
        row["segment_index"] = i
        row["t_start_ps"] = lo
        row["t_stop_ps"] = hi
        rows.append(row)
    phases = np.asarray([float(r["phase40_rad"]) for r in rows if np.isfinite(float(r["phase40_rad"]))], dtype=np.float64)
    a40 = np.asarray([float(r["A40"]) for r in rows if np.isfinite(float(r["A40"]))], dtype=np.float64)
    best = [int(r["best_period_ps"]) for r in rows if np.isfinite(float(r["best_period_ps"]))]
    summary = {
        "phase40_circular_std": _circular_std(phases),
        "A40_cv": float(np.std(a40) / np.mean(a40)) if a40.size and float(np.mean(a40)) > 0 else math.nan,
        "best_period_counts": {str(k): int(v) for k, v in sorted(Counter(best).items())},
        "n_segments": int(len(rows)),
    }
    return rows, summary


def _pairs_to_counts(bin_a: np.ndarray, bin_b: np.ndarray, dim: int) -> np.ndarray:
    counts = np.zeros((int(dim), int(dim)), dtype=np.float64)
    if bin_a.size == 0:
        return counts
    valid = (bin_a >= 0) & (bin_a < int(dim)) & (bin_b >= 0) & (bin_b < int(dim))
    np.add.at(counts, (bin_a[valid], bin_b[valid]), 1.0)
    return counts


def _jti_diag_metrics(counts: np.ndarray) -> dict[str, Any]:
    total = float(np.sum(counts))
    diag = np.diag(counts).astype(np.float64, copy=False)
    diag_sum = float(np.sum(diag))
    diag_mean = float(np.mean(diag)) if diag.size else 0.0
    diag_fft = np.fft.rfft(diag - diag_mean) if diag.size else np.array([], dtype=np.complex128)
    nonzero = np.abs(diag_fft[1:]) if diag_fft.size > 1 else np.array([], dtype=np.float64)
    dim = int(counts.shape[0])
    k_dim2 = dim // 2 if dim % 2 == 0 else None
    k_dim4 = dim // 4 if dim % 4 == 0 else None
    norm = max(1.0, diag_sum)
    return {
        "total_sum": total,
        "diag_main_sum": diag_sum,
        "diag_main_fraction": float(diag_sum / total) if total > 0 else 0.0,
        "diag_uniformity_cv": float(np.std(diag) / diag_mean) if diag_mean > 0 else math.nan,
        "diag_fft_k_dim2": float(abs(diag_fft[k_dim2]) / norm) if k_dim2 is not None and k_dim2 < diag_fft.size else math.nan,
        "diag_fft_k_dim4": float(abs(diag_fft[k_dim4]) / norm) if k_dim4 is not None and k_dim4 < diag_fft.size else math.nan,
        "diag_fft_max_nonzero": float(np.max(nonzero) / norm) if nonzero.size else 0.0,
    }


def _unique_frame_values(frames: np.ndarray, values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if frames.size == 0:
        return frames, values
    order = np.argsort(frames, kind="mergesort")
    f = frames[order]
    v = values[order]
    change = np.flatnonzero(f[1:] != f[:-1]) + 1 if f.size > 1 else np.array([], dtype=np.int64)
    starts = np.concatenate(([0], change))
    ends = np.concatenate((change, [f.size]))
    keep = (ends - starts) == 1
    idx = starts[keep]
    return f[idx], v[idx]


def _strict_single_hit_pairs(t_a: np.ndarray, t_b: np.ndarray, bin_width_ps: int, dim: int, frame_origin_ps: float) -> tuple[np.ndarray, np.ndarray]:
    ba = np.floor((t_a.astype(np.float64) - float(frame_origin_ps)) / float(bin_width_ps)).astype(np.int64)
    bb = np.floor((t_b.astype(np.float64) - float(frame_origin_ps)) / float(bin_width_ps)).astype(np.int64)
    fa = np.floor_divide(ba, int(dim))
    fb = np.floor_divide(bb, int(dim))
    da = np.mod(ba, int(dim)).astype(np.int64)
    db = np.mod(bb, int(dim)).astype(np.int64)
    ua_f, ua_d = _unique_frame_values(fa, da)
    ub_f, ub_d = _unique_frame_values(fb, db)
    common, ia, ib = np.intersect1d(ua_f, ub_f, assume_unique=True, return_indices=True)
    del common
    return ua_d[ia], ub_d[ib]


def folding_summary(pair_sets: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]], periods: np.ndarray, bin_widths: list[int], dims: list[int], frame_origin_ps: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for layer, (pa, pb, deltas) in pair_sets.items():
        raw = period_scan_deltas(f"{layer}_raw", deltas, periods)
        raw40 = raw.at_period(40)
        rows.append(
            {
                "pairing_layer": layer,
                "folding_layer": "raw_paired_dt",
                "bin_width_ps": 0,
                "dim": 0,
                "frame_origin_ps": float(frame_origin_ps),
                "n_pairs": int(deltas.size),
                "A40": raw40["amplitude"],
                "total_sum": float(deltas.size),
                "diag_main_sum": math.nan,
                "diag_main_fraction": math.nan,
                "diag_uniformity_cv": math.nan,
                "diag_fft_k_dim2": math.nan,
                "diag_fft_k_dim4": math.nan,
                "diag_fft_max_nonzero": math.nan,
            }
        )
        for bw in bin_widths:
            for dim in dims:
                ba = np.mod(np.floor((pa.astype(np.float64) - float(frame_origin_ps)) / float(bw)).astype(np.int64), int(dim))
                bb = np.mod(np.floor((pb.astype(np.float64) - float(frame_origin_ps)) / float(bw)).astype(np.int64), int(dim))
                counts = _pairs_to_counts(ba, bb, dim)
                rows.append({"pairing_layer": layer, "folding_layer": "folded_without_strict", "bin_width_ps": int(bw), "dim": int(dim), "frame_origin_ps": float(frame_origin_ps), "n_pairs": int(deltas.size), "A40": raw40["amplitude"], **_jti_diag_metrics(counts)})
                sa, sb = _strict_single_hit_pairs(pa, pb, bw, dim, frame_origin_ps)
                strict_counts = _pairs_to_counts(sa, sb, dim)
                rows.append({"pairing_layer": layer, "folding_layer": "folded_strict_single_hit_per_frame", "bin_width_ps": int(bw), "dim": int(dim), "frame_origin_ps": float(frame_origin_ps), "n_pairs": int(sa.size), "A40": raw40["amplitude"], **_jti_diag_metrics(strict_counts)})
    return rows


def _plot_period_scan(path: Path, results: list[PeriodResult]) -> None:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9.0, 5.0), dpi=160)
    for result in results:
        amps = np.abs(result.sums / float(result.n_pairs)) if result.n_pairs else np.zeros_like(result.periods, dtype=float)
        ax.plot(result.periods, amps, label=result.layer)
    ax.axvline(40, color="tab:red", linewidth=1.0, alpha=0.8)
    ax.set_xlabel("Period P (ps)")
    ax.set_ylabel("A(P)")
    ax.set_title("Period scan")
    ax.legend()
    fig.tight_layout()
    fig.savefig(str(path))
    plt.close(fig)


def _plot_mod40(path: Path, results: list[PeriodResult]) -> None:
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(len(results), 1, figsize=(10.0, 2.5 * len(results)), dpi=160, sharex=True, constrained_layout=True)
    if len(results) == 1:
        axes = [axes]
    x = np.arange(40)
    for ax, result in zip(axes, results):
        hist = result.hists.get(40, np.zeros(40, dtype=np.int64)).astype(np.float64)
        mean = float(np.mean(hist)) if hist.size else 0.0
        y = hist / mean if mean > 0 else hist
        ax.bar(x, y, width=0.9)
        ax.axhline(1.0, color="tab:red", linewidth=1.0)
        pad = max(0.01, float(np.max(np.abs(y - 1.0))) * 1.2) if y.size else 0.01
        ax.set_ylim(1.0 - pad, 1.0 + pad)
        ax.set_ylabel("count / mean")
        ax.set_title(f"{result.layer} mod 40 ps")
    axes[-1].set_xlabel("dt residue modulo 40 ps")
    fig.savefig(str(path))
    plt.close(fig)


def _plot_time_split(path: Path, rows: list[dict[str, Any]]) -> None:
    import matplotlib.pyplot as plt

    if not rows:
        return
    x = np.asarray([int(r["segment_index"]) for r in rows], dtype=int)
    a40 = np.asarray([float(r["A40"]) for r in rows], dtype=float)
    phase = np.asarray([float(r["phase40_ps"]) for r in rows], dtype=float)
    fig, axes = plt.subplots(2, 1, figsize=(9.0, 6.0), dpi=160, sharex=True, constrained_layout=True)
    axes[0].plot(x, a40, marker="o")
    axes[0].set_ylabel("A(40 ps)")
    axes[0].set_title("Time-split stability")
    axes[1].plot(x, phase, marker="o")
    axes[1].set_xlabel("Segment")
    axes[1].set_ylabel("phase at 40 ps (ps)")
    fig.savefig(str(path))
    plt.close(fig)


def classify(pairing_rows: list[dict[str, Any]], shift_summary: dict[str, Any], block_summary: dict[str, Any], split_summary: dict[str, Any]) -> str:
    by_layer = {str(r["layer"]): r for r in pairing_rows}
    all_a = float(by_layer.get("all_pairs", {}).get("A40", math.nan))
    nearest_a = float(by_layer.get("nearest", {}).get("A40", math.nan))
    greedy_a = float(by_layer.get("greedy_unique", {}).get("A40", math.nan))
    shift_ratio = float(shift_summary.get("surrogate_A40_ratio", math.nan))
    block_ratios = [float(v.get("surrogate_A40_ratio", math.nan)) for v in block_summary.values() if isinstance(v, dict)]
    block_ratio = float(np.nanmean(block_ratios)) if block_ratios else math.nan
    phase_std = float(split_summary.get("phase40_circular_std", math.nan))

    all_strong = np.isfinite(all_a) and all_a >= 0.003
    nearest_much_stronger = np.isfinite(nearest_a) and np.isfinite(all_a) and nearest_a > max(0.004, all_a * 1.75)
    greedy_much_stronger = np.isfinite(greedy_a) and np.isfinite(all_a) and greedy_a > max(0.004, all_a * 1.75)
    surrogate_stays = (np.isfinite(shift_ratio) and shift_ratio >= 0.5) or (np.isfinite(block_ratio) and block_ratio >= 0.5)
    surrogate_drops = (np.isfinite(shift_ratio) and shift_ratio < 0.25) and (not np.isfinite(block_ratio) or block_ratio < 0.25)
    phase_stable = np.isfinite(phase_std) and phase_std < 0.8

    if all_strong and surrogate_stays and phase_stable:
        return "fixed_electronics_or_tdc_differential_grid"
    if all_strong and surrogate_drops and not phase_stable:
        return "real_coincidence_bound_source_or_optical_structure"
    if not all_strong and (nearest_much_stronger or greedy_much_stronger):
        return "pairing_selection_bias"
    if all_strong and (nearest_much_stronger or greedy_much_stronger):
        return "weak_pair_level_residue_amplified_by_pairing_or_folding"
    return "inconclusive_mixed_pair_residue_and_selection_amplification"


def _parse_int_list(text: str) -> list[int]:
    return [int(x.strip()) for x in str(text).split(",") if x.strip()]


def _parse_float_list(text: str) -> list[float]:
    return [float(x.strip()) for x in str(text).split(",") if x.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description="Four-layer offline Time Tagger .ttbin residue diagnostic.")
    ap.add_argument("--ttbin", default=DEFAULT_TTBIN)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--ch-a", type=int, default=1)
    ap.add_argument("--ch-b", type=int, default=3)
    ap.add_argument("--window-ps", type=int, default=1000)
    ap.add_argument("--period-start-ps", type=int, default=10)
    ap.add_argument("--period-stop-ps", type=int, default=100)
    ap.add_argument("--period-step-ps", type=int, default=1)
    ap.add_argument("--hist-bin-ps", type=int, default=1)
    ap.add_argument("--time-splits", type=int, default=20)
    ap.add_argument("--surrogate-block-ms", default="1,10,100")
    ap.add_argument("--surrogate-shifts", type=int, default=10)
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--bin-widths-ps", default="20,25,30,35,40,50,60,80")
    ap.add_argument("--dims", default="4,8,16")
    ap.add_argument("--frame-origin-ps", type=float, default=0.0)
    ap.add_argument("--max-events", type=int, default=None)
    ap.add_argument("--skip-surrogates", action="store_true")
    ap.add_argument("--skip-folding", action="store_true")
    args = ap.parse_args()

    if int(args.hist_bin_ps) != 1:
        raise SystemExit("--hist-bin-ps currently supports only 1 ps bins.")
    if not str(args.ttbin).strip():
        raise SystemExit("--ttbin is required.")

    ttbin = _normalize_path(args.ttbin)
    out = _normalize_path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    periods = np.arange(int(args.period_start_ps), int(args.period_stop_ps) + 1, int(args.period_step_ps), dtype=int)

    tags = load_tags(ttbin, out, int(args.ch_a), int(args.ch_b), args.max_events)
    t_a = tags.t_a
    t_b = tags.t_b

    singles_a = period_scan_deltas("single_ch_a", t_a, periods)
    singles_b = period_scan_deltas("single_ch_b", t_b, periods)
    all_pairs = period_scan_all_pairs("all_pairs", t_a, t_b, int(args.window_ps), periods)
    n_a, n_b, n_d = nearest_pairs(t_a, t_b, int(args.window_ps))
    g_a, g_b, g_d = greedy_unique_pairs(t_a, t_b, int(args.window_ps))
    nearest = period_scan_deltas("nearest", n_d, periods)
    greedy = period_scan_deltas("greedy_unique", g_d, periods)

    scan_fields = ["layer", "period_ps", "n_pairs", "amplitude", "phase_rad", "phase_ps", "chi2_reduced", "cv"]
    for name, result in [("all_pairs", all_pairs), ("nearest", nearest), ("greedy_unique", greedy)]:
        _write_csv(out / f"period_scan_{name}.csv", scan_fields, result.rows())

    summary_fields = ["layer", "n_pairs", "A40", "phase40_rad", "phase40_ps", "cv40", "chi2_40", "best_period_ps", "best_amplitude", "best_phase_rad", "best_phase_ps"]
    pairing_rows = [_summary_row("all_pairs", all_pairs, 40), _summary_row("nearest", nearest, 40), _summary_row("greedy_unique", greedy, 40)]
    _write_csv(out / "pairing_layer_summary.csv", summary_fields, pairing_rows)

    real_a40 = float(pairing_rows[0]["A40"])
    shift_rows: list[dict[str, Any]] = []
    shift_sum: dict[str, Any] = {"skipped": True}
    block_rows: list[dict[str, Any]] = []
    block_sum: dict[str, Any] = {"skipped": True}
    if not bool(args.skip_surrogates):
        shift_rows, shift_sum = surrogate_shift_summary(t_a, t_b, int(args.window_ps), periods, int(args.surrogate_shifts), int(args.seed), real_a40, int(tags.meta.get("span_ps", 0)))
        _write_csv(out / "surrogate_shift_summary.csv", ["replicate", "shift_ps", *summary_fields], shift_rows)
        block_rows, block_sum = surrogate_block_summary(t_a, t_b, int(args.window_ps), periods, _parse_float_list(args.surrogate_block_ms), int(args.seed), real_a40)
        _write_csv(out / "surrogate_block_shuffle_summary.csv", ["block_ms", "block_ps", *summary_fields], block_rows)

    split_rows, split_sum = time_split_summary(t_a, t_b, int(args.window_ps), periods, int(args.time_splits))
    _write_csv(out / "time_split_summary.csv", ["segment_index", "t_start_ps", "t_stop_ps", *summary_fields], split_rows)

    folding_rows: list[dict[str, Any]] = []
    if not bool(args.skip_folding):
        folding_rows = folding_summary({"nearest": (n_a, n_b, n_d), "greedy_unique": (g_a, g_b, g_d)}, periods, _parse_int_list(args.bin_widths_ps), _parse_int_list(args.dims), float(args.frame_origin_ps))
        _write_csv(
            out / "folding_layer_summary.csv",
            ["pairing_layer", "folding_layer", "bin_width_ps", "dim", "frame_origin_ps", "n_pairs", "A40", "total_sum", "diag_main_sum", "diag_main_fraction", "diag_uniformity_cv", "diag_fft_k_dim2", "diag_fft_k_dim4", "diag_fft_max_nonzero"],
            folding_rows,
        )

    _plot_period_scan(out / "period_scan.png", [all_pairs, nearest, greedy])
    _plot_mod40(out / "pairing_mod40_normalized.png", [all_pairs, nearest, greedy])
    _plot_time_split(out / "time_split_phase.png", split_rows)

    singles_summary = {
        "ch_a": {"period40": singles_a.at_period(40), "best": singles_a.best(), "hist40": _hist_stats(singles_a.hists[40])},
        "ch_b": {"period40": singles_b.at_period(40), "best": singles_b.best(), "hist40": _hist_stats(singles_b.hists[40])},
    }
    interpretation = classify(pairing_rows, shift_sum, block_sum, split_sum)
    summary = {
        "ttbin": str(ttbin),
        "output_dir": str(out),
        "parameters": vars(args),
        "tag_meta": tags.meta,
        "singles_summary": singles_summary,
        "pairing_layer_summary": {r["layer"]: r for r in pairing_rows},
        "surrogate_shift_summary": shift_sum,
        "surrogate_block_shuffle_summary": block_sum,
        "time_split_summary": split_sum,
        "folding_layer_rows": int(len(folding_rows)),
        "interpretation": interpretation,
        "notes": [
            "This is an offline software diagnostic. It cannot by itself provide final physical attribution without hardware swap/control experiments.",
            "all_pairs is accumulated as exact streaming statistics; full all-pairs arrays are not stored.",
        ],
    }
    with (out / "summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=_json_default)

    print(json.dumps({"output_dir": str(out), "events": {"ch_a": int(t_a.size), "ch_b": int(t_b.size)}, "pairing_layer_summary": summary["pairing_layer_summary"], "surrogate_shift_summary": shift_sum, "surrogate_block_shuffle_summary": block_sum, "time_split_summary": split_sum, "interpretation": interpretation}, indent=2, ensure_ascii=False, default=_json_default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
