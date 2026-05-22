from __future__ import annotations

import numpy as np

from jti_extract.cli.extract import (
    _RawTimetags,
    _counts_for_frame_origin,
    _jti_from_pairs,
    _pairs_from_timetags,
    _time_tags_to_bins,
    compute_jti_diagnostics,
    diagonal_coincidence_profile,
)


def test_jti_counts_shape_and_total() -> None:
    pairs = np.asarray([(0, 0), (1, 1), (2, 2)], dtype=np.int64)
    counts = _jti_from_pairs(pairs, n_bins=4)

    assert counts.shape == (4, 4)
    assert float(np.sum(counts)) == 3.0
    assert float(np.trace(counts)) == 3.0


def test_frame_origin_changes_bins_as_current_algorithm_defines() -> None:
    times = np.asarray([10, 60, 110], dtype=np.int64)

    bins_t0 = _time_tags_to_bins(times, bin_width_ps=50, frame_origin_ps=0)
    bins_t25 = _time_tags_to_bins(times, bin_width_ps=50, frame_origin_ps=25)

    assert bins_t0.tolist() == [0, 1, 2]
    assert bins_t25.tolist() == [-1, 0, 1]


def test_strict_single_hit_per_frame_filters_duplicate_frame_hits() -> None:
    timetags = _RawTimetags(
        Ch=np.asarray([0.0, 0.0, 1.0, 1.0], dtype=float),
        TimeTag=np.asarray([10, 20, 15, 115], dtype=np.int64),
        overflow_types=None,
        missed_events=None,
        acquisition_duration_s=None,
        acquisition_duration_source=None,
    )

    pairs, meta = _pairs_from_timetags(
        timetags,
        bin_width_ps=50,
        frame_bins=4,
        frame_origin_ps=0,
        logical_ch_a=0,
        logical_ch_b=1,
    )

    assert pairs.tolist() == []
    assert meta["n_pairs"] == 0


def test_nearest_window_accepts_multi_hit_frames() -> None:
    timetags = _RawTimetags(
        Ch=np.asarray([0.0, 0.0, 1.0, 1.0], dtype=float),
        TimeTag=np.asarray([10, 20, 15, 115], dtype=np.int64),
        overflow_types=None,
        missed_events=None,
        acquisition_duration_s=None,
        acquisition_duration_source=None,
    )

    counts, meta, diag = _counts_for_frame_origin(
        timetags,
        bin_width_ps=50,
        frame_bins=4,
        frame_origin_ps=0,
        logical_ch_a=0,
        logical_ch_b=1,
        pairing_mode="nearest_window",
        coincidence_window_ps=20,
    )

    assert meta["n_pairs"] == 2
    assert diag["total_sum"] == 2.0
    assert counts[0, 0] == 2.0


def test_greedy_unique_window_accepts_multi_hit_frames() -> None:
    timetags = _RawTimetags(
        Ch=np.asarray([0.0, 0.0, 1.0, 1.0], dtype=float),
        TimeTag=np.asarray([10, 20, 15, 115], dtype=np.int64),
        overflow_types=None,
        missed_events=None,
        acquisition_duration_s=None,
        acquisition_duration_source=None,
    )

    counts, meta, diag = _counts_for_frame_origin(
        timetags,
        bin_width_ps=50,
        frame_bins=4,
        frame_origin_ps=0,
        logical_ch_a=0,
        logical_ch_b=1,
        pairing_mode="greedy_unique_window",
        coincidence_window_ps=20,
    )

    assert meta["n_pairs"] == 1
    assert diag["total_sum"] == 1.0
    assert counts[0, 0] == 1.0


def test_all_pairs_window_counts_multiple_b_hits() -> None:
    timetags = _RawTimetags(
        Ch=np.asarray([0.0, 1.0, 1.0], dtype=float),
        TimeTag=np.asarray([100, 95, 105], dtype=np.int64),
        overflow_types=None,
        missed_events=None,
        acquisition_duration_s=None,
        acquisition_duration_source=None,
    )

    counts, meta, diag = _counts_for_frame_origin(
        timetags,
        bin_width_ps=50,
        frame_bins=4,
        frame_origin_ps=0,
        logical_ch_a=0,
        logical_ch_b=1,
        pairing_mode="all_pairs_window",
        coincidence_window_ps=10,
    )

    assert meta["n_pairs"] == 2
    assert meta["max_b_per_a_in_window"] == 2
    assert diag["total_sum"] == 2.0
    assert counts[2, 1] == 1.0
    assert counts[2, 2] == 1.0


def test_diagnostics_lock_pm1_golden_value() -> None:
    counts = _jti_from_pairs(np.asarray([(0, 1), (1, 2), (2, 3)], dtype=np.int64), n_bins=4)
    diag = compute_jti_diagnostics(counts)

    assert diag["diag_main_sum"] == 0.0
    assert diag["diag_pm1_sum"] == 3.0
    assert diag["total_sum"] == 3.0


def test_diagonal_coincidence_profile_sums_band_by_row_bin() -> None:
    counts = np.zeros((4, 4), dtype=np.float64)
    counts[0, 0] = 2
    counts[0, 1] = 3
    counts[1, 0] = 5
    counts[2, 2] = 7

    assert diagonal_coincidence_profile(counts, band_bins=0).tolist() == [2.0, 0.0, 7.0, 0.0]
    assert diagonal_coincidence_profile(counts, band_bins=1).tolist() == [5.0, 5.0, 7.0, 0.0]
