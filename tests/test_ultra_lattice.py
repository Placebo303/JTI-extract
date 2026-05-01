"""Tests for jti_extract.ultra.fold_lattice.

Verifies:
1. fixed lattice binning with frame_origin_ps is correct;
2. edge guard rejects events near frame boundaries;
3. coincidence_window_ps does not depend on N, binwidth_ps, or frame_length_ps.
"""

import numpy as np

from jti_extract.ultra.fold_lattice import (
    bin_indices,
    edge_guard_mask,
    frame_length_ps,
    phase_in_frame,
)
from jti_extract.ultra.g2_accumulate import all_candidates
from jti_extract.ultra.accumulators import FixedLatticeAccumulator


class TestFrameLength:
    def test_simple(self) -> None:
        assert frame_length_ps(1024, 100) == 102400
        assert frame_length_ps(512, 200) == 102400
        assert frame_length_ps(32768, 100) == 3276800


class TestPhaseInFrame:
    def test_origin_zero(self) -> None:
        times = np.array([0, 100, 102400, 102500], dtype=np.int64)
        phase = phase_in_frame(times, 0.0, 102400)
        expected = np.array([0.0, 100.0, 0.0, 100.0])
        assert np.allclose(phase, expected), f"phase={phase}"

    def test_origin_nonzero(self) -> None:
        times = np.array([50000, 152400, 154800], dtype=np.int64)
        phase = phase_in_frame(times, 5000.0, 102400)
        # 50000 - 5000 = 45000, mod 102400 = 45000
        # 152400 - 5000 = 147400, mod 102400 = 45000
        # 154800 - 5000 = 149800, mod 102400 = 47400
        expected = np.array([45000.0, 45000.0, 47400.0])
        assert np.allclose(phase, expected), f"phase={phase}"


class TestBinIndices:
    def test_origin_zero(self) -> None:
        """frame_length=102400, bin_width=100 -> 1024 bins."""
        times = np.array([0, 100, 102400, 102500], dtype=np.int64)
        bins = bin_indices(times, 0.0, 100, 1024)
        # floor((t - 0)/100) % 1024
        # t=0   -> 0   % 1024 = 0
        # t=100 -> 1   % 1024 = 1
        # t=102400 -> 1024 % 1024 = 0
        # t=102500 -> 1025 % 1024 = 1
        expected = np.array([0, 1, 0, 1], dtype=np.int64)
        assert np.array_equal(bins, expected), f"bins={bins}"

    def test_origin_nonzero(self) -> None:
        """offset origin by 5000 ps."""
        times = np.array([50000, 152400], dtype=np.int64)
        bins = bin_indices(times, 5000.0, 100, 1024)
        # (50000 - 5000) / 100 = 450, floor = 450, % 1024 = 450
        # (152400 - 5000) / 100 = 1474, floor = 1474, % 1024 = 450
        expected = np.array([450, 450], dtype=np.int64)
        assert np.array_equal(bins, expected), f"bins={bins}"

    def test_negative_times(self) -> None:
        """Times before frame_origin should wrap correctly."""
        times = np.array([-100, 0], dtype=np.int64)
        bins = bin_indices(times, 0.0, 100, 1024)
        # (-100 - 0) / 100 = -1, floor = -1, mod 1024 = 1023
        expected = np.array([1023, 0], dtype=np.int64)
        assert np.array_equal(bins, expected), f"bins={bins}"


class TestEdgeGuardMask:
    def test_center_kept(self) -> None:
        """Events in the center of a frame should be kept."""
        frame_len = 102400  # 1024 * 100
        edge = 200
        # mid-frame event
        times = np.array([50000], dtype=np.int64)
        mask = edge_guard_mask(times, 0.0, frame_len, edge)
        assert mask[0], "center event should be kept"

    def test_boundary_rejected(self) -> None:
        """Events within edge_guard_ps of boundaries should be rejected."""
        frame_len = 102400
        edge = 200
        times = np.array([50, 102350], dtype=np.int64)  # within 200 of boundaries
        mask = edge_guard_mask(times, 0.0, frame_len, edge)
        assert not mask[0], f"event at t=50 should be rejected (phase=50 < edge={edge})"
        assert not mask[1], f"event at t=102350 should be rejected"

    def test_boundary_exact(self) -> None:
        """Events exactly at edge_guard distance should be kept."""
        frame_len = 102400
        edge = 200
        times = np.array([200, 102200], dtype=np.int64)
        mask = edge_guard_mask(times, 0.0, frame_len, edge)
        assert mask[0], "event exactly at edge guard should be kept"
        assert mask[1], "event exactly at frame_len-edge should be kept"

    def test_nonzero_origin(self) -> None:
        """Edge guard works with nonzero frame_origin."""
        frame_len = 102400
        edge = 200
        # origin = 5000, so frame covers [5000, 107400)
        times = np.array([5050, 107350], dtype=np.int64)
        mask = edge_guard_mask(times, 5000.0, frame_len, edge)
        # phase = (5050-5000)=50 < 200 -> reject
        assert not mask[0], "event too close to start should be rejected"
        # phase = (107350-5000)=102350, 102400-200=102200 -> 102350 > 102200 -> reject
        assert not mask[1], "event too close to end should be rejected"


class TestCoincidenceWindowIndependence:
    """coincidence_window_ps must not depend on N, binwidth_ps, or frame_length_ps."""

    def test_independence(self) -> None:
        """Verify iter_all_candidates and FixedLatticeAccumulator do not scale the window."""
        # 1) iter_all_candidates: candidate set should shrink/grow only
        #    when the *window parameter* changes, not when N or bw changes.
        t_a = np.array([100, 200], dtype=np.int64)
        t_b = np.array([150, 250], dtype=np.int64)
        w = 100

        ca1, cb1, _ = all_candidates(t_a, t_b, w)
        # With w=100: |150-100|=50 -> candidate; |250-100|=150 > 100 -> no
        # |150-200|=50 -> candidate; |250-200|=50 -> candidate
        expected_set = {(100, 150), (200, 150), (200, 250)}
        got_set = set(zip(ca1, cb1))
        assert got_set == expected_set, f"unexpected candidates: {got_set}"

        # 2) FixedLatticeAccumulator stores coincidence_window_ps verbatim
        for n_bins in (4, 100, 1024):
            acc = FixedLatticeAccumulator(
                n_bins=n_bins, bin_width_ps=100,
                frame_origin_ps=0.0,
                coincidence_window_ps=w,
                edge_guard_ps=0, coarse_n_bins=0,
            )
            s = acc.summary()
            assert int(s["coincidence_window_ps"]) == w, (
                f"coincidence_window_ps changed for n_bins={n_bins}: "
                f"got {s['coincidence_window_ps']}"
            )

        # 3) Varying bin_width_ps must not change stored window
        for bw in (10, 100, 1000):
            acc = FixedLatticeAccumulator(
                n_bins=100, bin_width_ps=bw,
                frame_origin_ps=0.0,
                coincidence_window_ps=w,
                edge_guard_ps=0, coarse_n_bins=0,
            )
            s = acc.summary()
            assert int(s["coincidence_window_ps"]) == w, (
                f"coincidence_window_ps changed for bin_width_ps={bw}: "
                f"got {s['coincidence_window_ps']}"
            )

        # 4) Varying frame_length_ps (via n_bins*bw) must not change stored window
        for n_bins, bw in ((4, 100), (100, 10), (1024, 100)):
            acc = FixedLatticeAccumulator(
                n_bins=n_bins, bin_width_ps=bw,
                frame_origin_ps=0.0,
                coincidence_window_ps=w,
                edge_guard_ps=0, coarse_n_bins=0,
            )
            s = acc.summary()
            assert int(s["coincidence_window_ps"]) == w, (
                f"coincidence_window_ps changed for "
                f"frame_length={n_bins * bw}: "
                f"got {s['coincidence_window_ps']}"
            )
