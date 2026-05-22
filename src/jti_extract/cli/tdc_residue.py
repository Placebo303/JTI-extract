#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np


def _normalize_path(raw: str) -> Path:
    return Path(str(raw).strip().strip('"'))


def _json_default(obj: Any) -> Any:
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, Path):
        return str(obj)
    return str(obj)


def _read_ttbin(path: Path, channels: tuple[int, int], max_events: int | None) -> tuple[dict[str, Any], dict[int, np.ndarray]]:
    try:
        from TimeTagger import FileReader  # type: ignore
    except Exception as exc:
        raise RuntimeError(f"cannot import Swabian TimeTagger Python API from {sys.executable}: {exc}") from exc

    reader = FileReader(str(path))
    config: dict[str, Any] = {}
    try:
        config = dict(reader.getConfiguration())
    except Exception as exc:
        config = {"getConfiguration_error": repr(exc)}

    selected = {int(ch): [] for ch in channels}
    total = 0
    event_type_counts: dict[int, int] = {}
    channel_counts: dict[int, int] = {}

    while reader.hasData():
        n = 1_000_000
        if max_events is not None:
            n = max(1, min(n, int(max_events) - total))
        data = reader.getData(n)
        ch = np.asarray(data.getChannels(), dtype=np.int64)
        ts = np.asarray(data.getTimestamps(), dtype=np.int64)
        et = np.asarray(data.getEventTypes(), dtype=np.int64)

        total += int(ts.size)
        for v, c in zip(*np.unique(et, return_counts=True)):
            event_type_counts[int(v)] = event_type_counts.get(int(v), 0) + int(c)
        for v, c in zip(*np.unique(ch, return_counts=True)):
            channel_counts[int(v)] = channel_counts.get(int(v), 0) + int(c)

        valid = et == 0
        for channel in selected:
            selected[channel].append(ts[np.logical_and(valid, ch == channel)])

        if max_events is not None and total >= int(max_events):
            break

    arrays = {
        channel: np.sort(np.concatenate(parts)) if parts else np.array([], dtype=np.int64)
        for channel, parts in selected.items()
    }
    config["_diagnostic_readback"] = {
        "total_events_read": total,
        "event_type_counts": event_type_counts,
        "channel_counts": channel_counts,
    }
    return config, arrays


def _hist_mod(values_ps: np.ndarray, modulus_ps: int) -> np.ndarray:
    residues = np.mod(values_ps, int(modulus_ps)).astype(np.int64, copy=False)
    return np.bincount(residues, minlength=int(modulus_ps))[: int(modulus_ps)]


def _uniform_stats(counts: np.ndarray) -> dict[str, float | int]:
    counts = np.asarray(counts, dtype=np.float64)
    total = float(np.sum(counts))
    bins = int(counts.size)
    if total <= 0 or bins <= 0:
        return {
            "total": int(total),
            "bins": bins,
            "mean": 0.0,
            "min": 0,
            "max": 0,
            "max_over_mean": math.nan,
            "min_over_mean": math.nan,
            "peak_to_peak_over_mean": math.nan,
            "cv": math.nan,
            "chi2_reduced_vs_uniform": math.nan,
            "first_harmonic_fraction": math.nan,
        }
    mean = total / bins
    centered = counts - mean
    fft = np.fft.rfft(counts)
    first = float(abs(fft[1]) / total) if fft.size > 1 else math.nan
    return {
        "total": int(total),
        "bins": bins,
        "mean": float(mean),
        "min": int(np.min(counts)),
        "max": int(np.max(counts)),
        "max_over_mean": float(np.max(counts) / mean),
        "min_over_mean": float(np.min(counts) / mean),
        "peak_to_peak_over_mean": float((np.max(counts) - np.min(counts)) / mean),
        "cv": float(np.std(counts) / mean),
        "chi2_reduced_vs_uniform": float(np.sum(centered * centered / mean) / max(1, bins - 1)),
        "first_harmonic_fraction": first,
    }


def _nearest_deltas(t1: np.ndarray, t3: np.ndarray, window_ps: int) -> np.ndarray:
    if t1.size == 0 or t3.size == 0:
        return np.array([], dtype=np.int64)

    pos = np.searchsorted(t3, t1)
    best = np.full(t1.shape, np.iinfo(np.int64).max, dtype=np.int64)

    right = pos < t3.size
    best[right] = t3[pos[right]] - t1[right]

    left = pos > 0
    left_delta = t3[pos[left] - 1] - t1[left]
    current = best[left]
    best[left] = np.where(np.abs(left_delta) < np.abs(current), left_delta, current)

    return best[np.abs(best) <= int(window_ps)]


def _write_csv(path: Path, columns: list[str], rows: list[list[Any]]) -> None:
    import csv

    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(columns)
        w.writerows(rows)


def _plot(out: Path, modulus_ps: int, hists: dict[str, np.ndarray], *, normalize: bool = False) -> None:
    import matplotlib.pyplot as plt

    x = np.arange(modulus_ps)
    fig, axes = plt.subplots(len(hists), 1, figsize=(10, 7), sharex=True, constrained_layout=True)
    if len(hists) == 1:
        axes = [axes]
    for ax, (label, counts) in zip(axes, hists.items()):
        y = counts.astype(np.float64, copy=False)
        if normalize:
            mean = float(np.mean(y)) if y.size else 0.0
            y = y / mean if mean > 0 else y
        ax.bar(x, y, width=0.9)
        ax.set_ylabel("count / mean" if normalize else "counts")
        ax.set_title(label)
        mean = float(np.mean(counts)) if counts.size else 0.0
        ax.axhline(1.0 if normalize else mean, color="tab:red", linewidth=1.0, alpha=0.8)
        if normalize and y.size:
            pad = max(0.01, float(np.max(np.abs(y - 1.0))) * 1.2)
            ax.set_ylim(1.0 - pad, 1.0 + pad)
    axes[-1].set_xlabel(f"timestamp residue modulo {modulus_ps} ps")
    fig.savefig(out, dpi=160)
    plt.close(fig)


def _probe_calibration_api() -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "not_available_from_ttbin_filereader",
        "note": (
            "autoCalibration(), getDistributionCount(), and getDistributionPSecs() are methods "
            "of a live TimeTagger object. FileReader exposes stored tags/configuration, not those "
            "hardware calibration distributions."
        ),
    }
    try:
        from TimeTagger import createTimeTagger, freeTimeTagger  # type: ignore

        tagger = createTimeTagger()
    except Exception as exc:
        result["live_hardware_probe"] = {"ok": False, "error": repr(exc)}
        return result

    try:
        result["live_hardware_probe"] = {
            "ok": True,
            "autoCalibration": np.asarray(tagger.autoCalibration()).tolist(),
            "distribution_count_shape": list(np.asarray(tagger.getDistributionCount()).shape),
            "distribution_psecs_shape": list(np.asarray(tagger.getDistributionPSecs()).shape),
        }
    except Exception as exc:
        result["live_hardware_probe"] = {"ok": False, "error": repr(exc)}
    finally:
        try:
            freeTimeTagger(tagger)
        except Exception:
            pass
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Diagnose Time Tagger fine-time residue structure in *.ttbin data.")
    ap.add_argument("--ttbin", required=True, help="Input *.ttbin file.")
    ap.add_argument("--out", default="results/tdc_residue_diagnostics", help="Output directory.")
    ap.add_argument("--ch1", type=int, default=1, help="First hardware channel, default 1.")
    ap.add_argument("--ch3", type=int, default=3, help="Second hardware channel, default 3.")
    ap.add_argument("--modulus-ps", type=int, default=40, help="Residue modulus in ps, default 40.")
    ap.add_argument("--coincidence-window-ps", type=int, default=1000, help="Nearest-pair |t3-t1| window, default 1000 ps.")
    ap.add_argument("--max-events", type=int, default=None, help="Optional maximum raw events to read.")
    ap.add_argument("--probe-live-calibration", action="store_true", help="Also try live hardware calibration API.")
    args = ap.parse_args()

    ttbin = _normalize_path(args.ttbin)
    out = _normalize_path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    config, arrays = _read_ttbin(ttbin, (args.ch1, args.ch3), args.max_events)
    t1 = arrays[int(args.ch1)]
    t3 = arrays[int(args.ch3)]
    deltas = _nearest_deltas(t1, t3, int(args.coincidence_window_ps))

    h_ch1 = _hist_mod(t1, int(args.modulus_ps))
    h_ch3 = _hist_mod(t3, int(args.modulus_ps))
    h_dt = _hist_mod(deltas, int(args.modulus_ps))
    hists = {
        f"ch{args.ch1}: timestamp mod {args.modulus_ps} ps": h_ch1,
        f"ch{args.ch3}: timestamp mod {args.modulus_ps} ps": h_ch3,
        f"nearest pairs: (t{args.ch3}-t{args.ch1}) mod {args.modulus_ps} ps": h_dt,
    }

    _write_csv(
        out / "mod40_histograms.csv",
        ["residue_ps", f"ch{args.ch1}", f"ch{args.ch3}", f"dt_ch{args.ch3}_minus_ch{args.ch1}"],
        [[i, int(h_ch1[i]), int(h_ch3[i]), int(h_dt[i])] for i in range(int(args.modulus_ps))],
    )
    _plot(out / "mod40_histograms.png", int(args.modulus_ps), hists)
    _plot(out / "mod40_histograms_normalized.png", int(args.modulus_ps), hists, normalize=True)

    summary: dict[str, Any] = {
        "ttbin": str(ttbin),
        "output_dir": str(out),
        "channels": [int(args.ch1), int(args.ch3)],
        "modulus_ps": int(args.modulus_ps),
        "coincidence_window_ps": int(args.coincidence_window_ps),
        "events": {
            f"ch{args.ch1}": int(t1.size),
            f"ch{args.ch3}": int(t3.size),
            "nearest_pairs_in_window": int(deltas.size),
        },
        "histogram_stats": {
            f"ch{args.ch1}": _uniform_stats(h_ch1),
            f"ch{args.ch3}": _uniform_stats(h_ch3),
            f"dt_ch{args.ch3}_minus_ch{args.ch1}": _uniform_stats(h_dt),
        },
        "calibration_distribution": _probe_calibration_api()
        if bool(args.probe_live_calibration)
        else {
            "status": "not_queried",
            "note": "Pass --probe-live-calibration to try a live TimeTagger object; FileReader cannot expose these API calls from ttbin alone.",
        },
        "file_configuration": config,
    }
    with (out / "summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=_json_default)

    print(json.dumps({k: summary[k] for k in ["ttbin", "output_dir", "events", "histogram_stats", "calibration_distribution"]}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
