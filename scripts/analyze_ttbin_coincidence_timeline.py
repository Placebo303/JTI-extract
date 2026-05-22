#!/usr/bin/env python3
"""Analyze coincidence rate versus absolute acquisition time for TimeTagger .ttbin files."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable, Iterator

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jti_extract.cli.tdc_layer_scan import Tags, greedy_unique_pairs, load_tags, nearest_pairs


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


def normalize_path(text: str) -> Path:
    return Path(str(text).strip().strip('"'))


def load_ttbin_events(input_path: Path, output_dir: Path, channels: tuple[int, int], max_events: int | None = None) -> Tags:
    return load_tags(input_path, output_dir / "_tag_cache", int(channels[0]), int(channels[1]), max_events)


def frame_local_bins(times_ps: np.ndarray, *, bin_width_ps: int, frame_bins: int) -> np.ndarray:
    return np.mod(np.floor(np.asarray(times_ps, dtype=np.float64) / float(bin_width_ps)).astype(np.int64), int(frame_bins))


def apply_diag_filter(
    t_a: np.ndarray,
    t_b: np.ndarray,
    *,
    jti_binwidth_ps: int | None,
    frame_bins: int | None,
    diag_halfwidth_bins: int | None,
) -> tuple[np.ndarray, np.ndarray]:
    if jti_binwidth_ps is None and frame_bins is None and diag_halfwidth_bins is None:
        return t_a, t_b
    if jti_binwidth_ps is None or frame_bins is None or diag_halfwidth_bins is None:
        raise ValueError("--jti-binwidth-ps, --frame-bins, and --diag-halfwidth-bins must be provided together")
    k_a = frame_local_bins(t_a, bin_width_ps=int(jti_binwidth_ps), frame_bins=int(frame_bins))
    k_b = frame_local_bins(t_b, bin_width_ps=int(jti_binwidth_ps), frame_bins=int(frame_bins))
    keep = np.abs(k_b - k_a) <= int(diag_halfwidth_bins)
    return t_a[keep], t_b[keep]


def pair_coincidences(
    t_a: np.ndarray,
    t_b: np.ndarray,
    *,
    mode: str,
    window_ps: int,
    jti_binwidth_ps: int | None = None,
    frame_bins: int | None = None,
    diag_halfwidth_bins: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    if mode == "nearest":
        p_a, p_b, _ = nearest_pairs(t_a, t_b, int(window_ps))
    elif mode == "greedy_unique":
        p_a, p_b, _ = greedy_unique_pairs(t_a, t_b, int(window_ps))
    else:
        raise ValueError(f"pair_coincidences supports nearest/greedy_unique, got: {mode}")
    return apply_diag_filter(
        p_a,
        p_b,
        jti_binwidth_ps=jti_binwidth_ps,
        frame_bins=frame_bins,
        diag_halfwidth_bins=diag_halfwidth_bins,
    )


def iter_all_pair_midpoints(
    t_a: np.ndarray,
    t_b: np.ndarray,
    *,
    window_ps: int,
    chunk_events: int = 200_000,
    jti_binwidth_ps: int | None = None,
    frame_bins: int | None = None,
    diag_halfwidth_bins: int | None = None,
) -> Iterator[np.ndarray]:
    t_b = np.asarray(t_b, dtype=np.int64)
    for start in range(0, int(t_a.size), int(chunk_events)):
        a = np.asarray(t_a[start : start + int(chunk_events)], dtype=np.int64)
        left = np.searchsorted(t_b, a - int(window_ps), side="left")
        right = np.searchsorted(t_b, a + int(window_ps), side="right")
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
        a_rep, b_vals = apply_diag_filter(
            a_rep,
            b_vals,
            jti_binwidth_ps=jti_binwidth_ps,
            frame_bins=frame_bins,
            diag_halfwidth_bins=diag_halfwidth_bins,
        )
        if a_rep.size:
            yield compute_coincidence_midpoints(a_rep, b_vals)


def compute_coincidence_midpoints(t_a: np.ndarray, t_b: np.ndarray) -> np.ndarray:
    return (np.asarray(t_a, dtype=np.float64) + np.asarray(t_b, dtype=np.float64)) * 0.5


def make_hist_edges(start_ps: int, stop_ps: int, time_bin_s: float) -> np.ndarray:
    if time_bin_s <= 0:
        raise ValueError("time_bin_s must be positive")
    duration_ps = max(0, int(stop_ps) - int(start_ps))
    bin_width_ps = float(time_bin_s) * 1e12
    n_bins = max(1, int(math.ceil(float(duration_ps) / bin_width_ps)))
    return int(start_ps) + np.arange(n_bins + 1, dtype=np.float64) * bin_width_ps


def compute_timeline_histogram(midpoints_ps: np.ndarray, *, start_ps: int, stop_ps: int, time_bin_s: float) -> tuple[np.ndarray, np.ndarray]:
    edges = make_hist_edges(start_ps, stop_ps, float(time_bin_s))
    counts, _ = np.histogram(np.asarray(midpoints_ps, dtype=np.float64), bins=edges)
    return counts.astype(np.int64), edges


def compute_timeline_histogram_stream(midpoint_chunks: Iterable[np.ndarray], *, start_ps: int, stop_ps: int, time_bin_s: float) -> tuple[np.ndarray, np.ndarray]:
    edges = make_hist_edges(start_ps, stop_ps, float(time_bin_s))
    counts = np.zeros(edges.size - 1, dtype=np.int64)
    for chunk in midpoint_chunks:
        hist, _ = np.histogram(np.asarray(chunk, dtype=np.float64), bins=edges)
        counts += hist.astype(np.int64)
    return counts, edges


def histogram_rows(counts: np.ndarray, edges_ps: np.ndarray, *, start_ps: int, time_bin_s: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rel_edges_s = (edges_ps - float(start_ps)) * 1e-12
    for i, count in enumerate(np.asarray(counts, dtype=np.int64)):
        rows.append(
            {
                "time_bin_start_s": float(rel_edges_s[i]),
                "time_bin_end_s": float(rel_edges_s[i + 1]),
                "time_bin_center_s": float((rel_edges_s[i] + rel_edges_s[i + 1]) * 0.5),
                "coincidence_counts": int(count),
                "coincidence_rate_cps": float(int(count) / float(time_bin_s)),
            }
        )
    return rows


def histogram_stats(counts: np.ndarray, *, time_bin_s: float) -> dict[str, Any]:
    counts_f = np.asarray(counts, dtype=np.float64)
    rates = counts_f / float(time_bin_s)
    mean_counts = float(np.mean(counts_f)) if counts_f.size else 0.0
    std_counts = float(np.std(counts_f)) if counts_f.size else 0.0
    return {
        "histogram_bins": int(counts_f.size),
        "counts_total": int(np.sum(counts_f)),
        "counts_mean": mean_counts,
        "counts_std": std_counts,
        "counts_min": int(np.min(counts_f)) if counts_f.size else 0,
        "counts_max": int(np.max(counts_f)) if counts_f.size else 0,
        "rate_cps_mean": float(np.mean(rates)) if rates.size else 0.0,
        "rate_cps_std": float(np.std(rates)) if rates.size else 0.0,
        "rate_cps_min": float(np.min(rates)) if rates.size else 0.0,
        "rate_cps_max": float(np.max(rates)) if rates.size else 0.0,
        "std_counts_over_poisson": float(std_counts / math.sqrt(mean_counts)) if mean_counts > 0 else math.nan,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = ["time_bin_start_s", "time_bin_end_s", "time_bin_center_s", "coincidence_counts", "coincidence_rate_cps"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def plot_timeline(path: Path, rows: list[dict[str, Any]], *, title: str) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"matplotlib is required to plot timeline: {exc}") from exc
    x = np.asarray([float(r["time_bin_center_s"]) for r in rows], dtype=np.float64)
    y = np.asarray([float(r["coincidence_rate_cps"]) for r in rows], dtype=np.float64)
    fig, ax = plt.subplots(figsize=(9.0, 4.0), dpi=160)
    ax.plot(x, y, linewidth=0.9)
    ax.set_xlabel("Acquisition time (s)")
    ax.set_ylabel("Coincidence rate (cps)")
    ax.set_title(title)
    ax.grid(True, linewidth=0.4, alpha=0.35)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def save_outputs(output_dir: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "coincidence_timeline.csv"
    png_path = output_dir / "coincidence_timeline.png"
    json_path = output_dir / "coincidence_timeline_summary.json"
    write_csv(csv_path, rows)
    title = (
        f"{Path(summary['input']['path']).name} | ch {summary['input']['channels'][0]}-{summary['input']['channels'][1]} | "
        f"{summary['pairing']['mode']} | window {summary['pairing']['coincidence_window_ps']} ps | "
        f"bin {summary['histogram']['time_bin_s']} s"
    )
    plot_timeline(png_path, rows, title=title)
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    return {"csv": csv_path, "png": png_path, "summary": json_path}


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    input_path = normalize_path(args.input)
    output_dir = normalize_path(args.output_dir)
    channels = (int(args.channels[0]), int(args.channels[1]))
    tags = load_ttbin_events(input_path, output_dir, channels, args.max_events)
    if tags.t_a.size == 0 or tags.t_b.size == 0:
        raise RuntimeError("selected channels contain no events")
    start_ps = int(min(int(tags.t_a[0]), int(tags.t_b[0])))
    stop_ps = int(max(int(tags.t_a[-1]), int(tags.t_b[-1])))

    filter_kwargs = {
        "jti_binwidth_ps": args.jti_binwidth_ps,
        "frame_bins": args.frame_bins,
        "diag_halfwidth_bins": args.diag_halfwidth_bins,
    }
    if args.pairing_mode == "all_pairs":
        counts, edges = compute_timeline_histogram_stream(
            iter_all_pair_midpoints(tags.t_a, tags.t_b, window_ps=int(args.coinc_window_ps), **filter_kwargs),
            start_ps=start_ps,
            stop_ps=stop_ps,
            time_bin_s=float(args.time_bin_s),
        )
    else:
        p_a, p_b = pair_coincidences(
            tags.t_a,
            tags.t_b,
            mode=str(args.pairing_mode),
            window_ps=int(args.coinc_window_ps),
            **filter_kwargs,
        )
        midpoints = compute_coincidence_midpoints(p_a, p_b)
        counts, edges = compute_timeline_histogram(midpoints, start_ps=start_ps, stop_ps=stop_ps, time_bin_s=float(args.time_bin_s))

    rows = histogram_rows(counts, edges, start_ps=start_ps, time_bin_s=float(args.time_bin_s))
    stats = histogram_stats(counts, time_bin_s=float(args.time_bin_s))
    duration_s = float((stop_ps - start_ps) * 1e-12)
    summary = {
        "input": {"path": str(input_path), "channels": [channels[0], channels[1]], "max_events": args.max_events},
        "acquisition": {"start_ps": start_ps, "stop_ps": stop_ps, "duration_s": duration_s},
        "events": {"channel_a": int(tags.t_a.size), "channel_b": int(tags.t_b.size), "loader_meta": tags.meta},
        "pairing": {"mode": str(args.pairing_mode), "coincidence_window_ps": int(args.coinc_window_ps), "coincidence_total": int(stats["counts_total"]), "average_rate_cps": float(stats["counts_total"] / duration_s) if duration_s > 0 else math.nan},
        "histogram": {"time_bin_s": float(args.time_bin_s), **stats},
        "diag_filter": {
            "enabled": args.jti_binwidth_ps is not None or args.frame_bins is not None or args.diag_halfwidth_bins is not None,
            "jti_binwidth_ps": args.jti_binwidth_ps,
            "frame_bins": args.frame_bins,
            "diag_halfwidth_bins": args.diag_halfwidth_bins,
        },
    }
    paths = save_outputs(output_dir, rows, summary)
    summary["outputs"] = {key: str(value) for key, value in paths.items()}
    paths["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze coincidence counts/rate versus absolute acquisition time for a TimeTagger .ttbin file.")
    parser.add_argument("--input", required=True, help="Input .ttbin file.")
    parser.add_argument("--channels", nargs=2, type=int, required=True, metavar=("A", "B"), help="Hardware channels to pair.")
    parser.add_argument("--coinc-window-ps", type=int, default=200, help="Coincidence window in ps.")
    parser.add_argument("--pairing-mode", choices=["nearest", "greedy_unique", "all_pairs"], default="nearest", help="Coincidence pairing mode.")
    parser.add_argument("--time-bin-s", type=float, default=0.01, help="Timeline histogram bin size in seconds.")
    parser.add_argument("--output-dir", required=True, help="Output directory.")
    parser.add_argument("--max-events", type=int, default=None, help="Optional maximum raw events to read.")
    parser.add_argument("--jti-binwidth-ps", type=int, default=None, help="Optional frame-local JTI bin width for diagonal-band filtering.")
    parser.add_argument("--frame-bins", type=int, default=None, help="Optional number of frame-local bins for diagonal-band filtering.")
    parser.add_argument("--diag-halfwidth-bins", type=int, default=None, help="Optional diagonal half-width in frame-local bins.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    summary = analyze(args)
    print(json.dumps({"outputs": summary["outputs"], "pairing": summary["pairing"], "histogram": summary["histogram"]}, indent=2, ensure_ascii=False, default=_json_default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
