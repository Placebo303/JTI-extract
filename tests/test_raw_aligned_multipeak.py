"""Minimal synthetic checks for residual-delay multi-peak handling."""
from __future__ import annotations

import numpy as np

from jti_extract.cli.raw_aligned import (
    _non_overlapping_peak_windows,
    build_raw_aligned_jti,
    detect_residual_peaks,
)


def test_resolved_residual_peaks_can_be_counted_independently() -> None:
    # Two equal, frame-local coincidence peaks separated by 40 ps.
    t_a = np.asarray([20 + 160 * k for k in range(8)], dtype=np.int64)
    t_b = np.sort(np.concatenate([t_a, t_a + 40])).astype(np.int64)
    _, discovery = build_raw_aligned_jti(
        t_a, t_b, 0, bw=10, dim=16, origin_ps=0, guard_bins=1,
        delay_min_ps=-70, delay_max_ps=70,
    )
    centers = (discovery["tau_hist_bin_edges"][:-1] + discovery["tau_hist_bin_edges"][1:]) / 2
    peaks = detect_residual_peaks(centers, discovery["tau_hist_counts"], min_relative_height=0.5)

    assert [peak["counts"] for peak in peaks] == [8, 8]

    H_first, first_meta = build_raw_aligned_jti(
        t_a, t_b, 0, bw=10, dim=16, origin_ps=0, guard_bins=1,
        delay_min_ps=-10, delay_max_ps=10,
    )
    H_second, second_meta = build_raw_aligned_jti(
        t_a, t_b, 0, bw=10, dim=16, origin_ps=0, guard_bins=1,
        delay_min_ps=30, delay_max_ps=50,
    )
    assert int(H_first.sum()) == first_meta["retained_in_jti"] == 8
    assert int(H_second.sum()) == second_meta["retained_in_jti"] == 8
    assert np.count_nonzero(H_first) == np.count_nonzero(H_second) == 1
    assert np.argmax(H_first) != np.argmax(H_second)


def test_auto_peak_windows_are_disjoint() -> None:
    detected = [{"delay_ps": 0.0, "counts": 8}, {"delay_ps": 40.0, "counts": 8}]
    windows = _non_overlapping_peak_windows(
        list(enumerate(detected)), detected, requested_half_window_ps=None,
        histogram_binwidth_ps=10,
    )
    assert windows[0][3] < windows[1][2]
