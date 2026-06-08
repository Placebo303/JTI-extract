from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


def _load_module():
    path = Path("scripts/analyze_ttbin_coincidence_timeline.py")
    spec = importlib.util.spec_from_file_location("analyze_ttbin_coincidence_timeline", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


timeline = _load_module()


def test_midpoint_computation() -> None:
    a = np.asarray([0, 10], dtype=np.int64)
    b = np.asarray([4, 20], dtype=np.int64)

    assert timeline.compute_coincidence_midpoints(a, b).tolist() == [2.0, 15.0]


def test_nearest_pairing_histogram_total_matches_pairs() -> None:
    a = np.asarray([100, 200, 1000], dtype=np.int64)
    b = np.asarray([95, 205, 400], dtype=np.int64)
    p_a, p_b = timeline.pair_coincidences(a, b, mode="nearest", window_ps=20)
    mid = timeline.compute_coincidence_midpoints(p_a, p_b)
    counts, _ = timeline.compute_timeline_histogram(mid, start_ps=0, stop_ps=1_000_000_000, time_bin_s=0.001)

    assert p_a.size == 2
    assert int(np.sum(counts)) == 2


def test_greedy_pairing_histogram_total_matches_pairs() -> None:
    a = np.asarray([100, 102, 200], dtype=np.int64)
    b = np.asarray([101, 201], dtype=np.int64)
    p_a, p_b = timeline.pair_coincidences(a, b, mode="greedy_unique", window_ps=5)
    mid = timeline.compute_coincidence_midpoints(p_a, p_b)
    counts, _ = timeline.compute_timeline_histogram(mid, start_ps=0, stop_ps=1_000_000_000, time_bin_s=0.001)

    assert p_a.tolist() == [100, 200]
    assert p_b.tolist() == [101, 201]
    assert int(np.sum(counts)) == 2


def test_all_pairs_stream_counts_one_a_to_many_b() -> None:
    a = np.asarray([100], dtype=np.int64)
    b = np.asarray([95, 105, 300], dtype=np.int64)
    counts, _ = timeline.compute_timeline_histogram_stream(
        timeline.iter_all_pair_midpoints(a, b, window_ps=10),
        start_ps=0,
        stop_ps=1_000_000_000,
        time_bin_s=0.001,
    )

    assert int(np.sum(counts)) == 2


def test_diag_filter_keeps_only_frame_local_band() -> None:
    a = np.asarray([0, 0], dtype=np.int64)
    b = np.asarray([5, 25], dtype=np.int64)
    kept_a, kept_b = timeline.apply_diag_filter(
        a,
        b,
        jti_binwidth_ps=10,
        frame_bins=10,
        diag_halfwidth_bins=0,
    )

    assert kept_a.tolist() == [0]
    assert kept_b.tolist() == [5]
