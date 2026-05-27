"""Tests for JTI extraction core functions."""
from __future__ import annotations

import numpy as np

from jti_extract.cli.extract import (
    _RawTimetags,
    _compute_dv_matrix,
    _find_coincidence_pairs,
    _time_tags_to_bins,
    compute_jti_diagnostics,
    diagonal_coincidence_profile,
)


def test_frame_origin_changes_bins_as_current_algorithm_defines() -> None:
    """Verify that frame_origin_ps shifts bins correctly."""
    times = np.asarray([10, 60, 110], dtype=np.int64)

    bins_t0 = _time_tags_to_bins(times, bin_width_ps=50, frame_origin_ps=0)
    bins_t25 = _time_tags_to_bins(times, bin_width_ps=50, frame_origin_ps=25)

    assert bins_t0.tolist() == [0, 1, 2]
    assert bins_t25.tolist() == [-1, 0, 1]


def test_time_tags_to_bins_integer_precision() -> None:
    """Verify that 17-digit timestamps are handled without float64 precision loss."""
    # Typical timestamp: ~3.688e16 ps (17 digits)
    times = np.asarray([36880089746026674, 36880089746026684, 36880089746026694], dtype=np.int64)
    bins = _time_tags_to_bins(times, bin_width_ps=10, frame_origin_ps=0)

    # All three timestamps differ by 10ps, so should map to consecutive bins
    assert bins[1] - bins[0] == 1
    assert bins[2] - bins[1] == 1


def test_find_coincidence_pairs_basic() -> None:
    """Verify basic coincidence pairing."""
    timetags = _RawTimetags(
        Ch=np.asarray([0.0, 0.0, 1.0, 1.0], dtype=float),
        TimeTag=np.asarray([100, 200, 105, 205], dtype=np.int64),
        overflow_types=None,
        missed_events=None,
        acquisition_duration_s=None,
        acquisition_duration_source=None,
    )

    result = _find_coincidence_pairs(
        timetags,
        window_ps=10,
        logical_ch_a=0,
        logical_ch_b=1,
    )

    # Two pairs: (100,105) and (200,205)
    assert result.t_a_paired.size == 2
    assert result.t_b_paired.size == 2


def test_find_coincidence_pairs_window_limit() -> None:
    """Verify that pairs outside window are rejected."""
    timetags = _RawTimetags(
        Ch=np.asarray([0.0, 1.0], dtype=float),
        TimeTag=np.asarray([100, 200], dtype=np.int64),  # 100ps apart
        overflow_types=None,
        missed_events=None,
        acquisition_duration_s=None,
        acquisition_duration_source=None,
    )

    result = _find_coincidence_pairs(
        timetags,
        window_ps=10,  # window too small
        logical_ch_a=0,
        logical_ch_b=1,
    )

    # No pairs because |100 - 200| > 10
    assert result.t_a_paired.size == 0


def test_compute_dv_matrix_shape() -> None:
    """Verify DV matrix has correct shape."""
    t_a = np.asarray([100, 200, 300], dtype=np.int64)
    t_b = np.asarray([105, 205, 305], dtype=np.int64)

    dv = _compute_dv_matrix(
        t_a, t_b,
        dimension=64,
        binwidth_ps=10,
        frame_origin_ps=0,
    )

    assert dv.shape == (64, 64)


def test_diagnostics_lock_pm1_golden_value() -> None:
    """Verify diagnostics compute correct values."""
    counts = np.zeros((4, 4), dtype=np.float64)
    counts[0, 1] = 1.0
    counts[1, 2] = 1.0
    counts[2, 3] = 1.0

    diag = compute_jti_diagnostics(counts)

    assert diag["diag_main_sum"] == 0.0
    assert diag["diag_pm1_sum"] == 3.0
    assert diag["total_sum"] == 3.0


def test_diagnostics_offdiag_fraction() -> None:
    """Verify that offdiag_fraction is computed correctly."""
    counts = np.zeros((4, 4), dtype=np.float64)
    counts[0, 0] = 10  # main diagonal
    counts[1, 1] = 10
    counts[0, 1] = 5   # +1 diagonal (included in band_bins=1)
    counts[1, 0] = 5   # -1 diagonal (included in band_bins=1)

    diag = compute_jti_diagnostics(counts)

    # With band_bins=1, main + pm1 = 20 + 10 = 30, so offdiag = 0
    assert diag["diag_main_fraction"] == 20.0 / 30.0
    assert diag["diag_pm1_fraction"] == 10.0 / 30.0
    assert diag["offdiag_fraction"] == 0.0  # all counts are within band

    # Test with band_bins=0 (only main diagonal)
    diag0 = compute_jti_diagnostics(counts, band_bins=0)
    assert diag0["offdiag_fraction"] == 10.0 / 30.0


def test_diagonal_coincidence_profile_sums_band_by_row_bin() -> None:
    """Verify diagonal profile computation."""
    counts = np.zeros((4, 4), dtype=np.float64)
    counts[0, 0] = 2
    counts[0, 1] = 3
    counts[1, 0] = 5
    counts[2, 2] = 7

    assert diagonal_coincidence_profile(counts, band_bins=0).tolist() == [2.0, 0.0, 7.0, 0.0]
    assert diagonal_coincidence_profile(counts, band_bins=1).tolist() == [5.0, 5.0, 7.0, 0.0]
