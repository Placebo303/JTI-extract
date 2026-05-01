"""Tests for jti_extract.ultra.g2_accumulate and accumulators.

Verifies:
1. all-candidate iterator matches hand-calculated candidates;
2. chunked and unchunked candidate iteration produce the same candidates;
3. coarse JTI, diagonal profile, row marginal, and column marginal totals
   match n_candidates_after_edge_guard.
"""

import numpy as np
import pytest

from jti_extract.ultra.g2_accumulate import all_candidates, iter_all_candidates
from jti_extract.ultra.accumulators import FixedLatticeAccumulator


# ---------------------------------------------------------------------------
#  Hand-calculated candidates
# ---------------------------------------------------------------------------

def _hand_count_candidates(t_a: np.ndarray, t_b: np.ndarray, w: int) -> int:
    """Brute-force O(N^2) count for tiny arrays."""
    count = 0
    for av in t_a:
        count += int(np.count_nonzero(np.abs(t_b - int(av)) <= int(w)))
    return count


def _hand_candidates_set(t_a, t_b, w):
    """Return set of (t_a, t_b) pairs for comparison."""
    pairs: set[tuple[int, int]] = set()
    for av in t_a:
        for bv in t_b:
            if abs(int(bv) - int(av)) <= int(w):
                pairs.add((int(av), int(bv)))
    return pairs


# ---------------------------------------------------------------------------
#  Tests for g2_accumulate
# ---------------------------------------------------------------------------

class TestAllCandidates:
    """Test the all-candidate iterator against hand-calculated results."""

    def test_empty(self) -> None:
        t_a = np.array([], dtype=np.int64)
        t_b = np.array([1, 2, 3], dtype=np.int64)
        ca, cb, cd = all_candidates(t_a, t_b, 100)
        assert ca.size == 0

    def test_simple_pairs(self) -> None:
        """t_a = [100, 200], t_b = [150, 250], w=100."""
        t_a = np.array([100, 200], dtype=np.int64)
        t_b = np.array([150, 250], dtype=np.int64)
        ca, cb, cd = all_candidates(t_a, t_b, 100)
        # hand check: |150-100|=50 <= 100 -> candidate
        #             |250-100|=150 > 100 -> no
        #             |150-200|=50 <= 100 -> candidate
        #             |250-200|=50 <= 100 -> candidate
        expected = {(100, 150), (200, 150), (200, 250)}
        got = set(zip(ca, cb))
        assert got == expected, f"got {got}"

    def test_multiple_per_event(self) -> None:
        """t_a = [0], t_b = [-50, 0, 50], w=100."""
        t_a = np.array([0], dtype=np.int64)
        t_b = np.array([-50, 0, 50], dtype=np.int64)
        ca, cb, cd = all_candidates(t_a, t_b, 100)
        expected = {(0, -50), (0, 0), (0, 50)}
        got = set(zip(ca, cb))
        assert got == expected, f"got {got}"

    def test_no_candidates(self) -> None:
        t_a = np.array([0], dtype=np.int64)
        t_b = np.array([200], dtype=np.int64)
        ca, cb, cd = all_candidates(t_a, t_b, 100)
        assert ca.size == 0

    def test_count_matches_hand(self) -> None:
        rng = np.random.default_rng(42)
        t_a = np.sort(rng.integers(0, 1_000_000, size=50))
        t_b = np.sort(rng.integers(0, 1_000_000, size=80))
        w = 200
        ca, cb, cd = all_candidates(t_a, t_b, w)
        n_expected = _hand_count_candidates(t_a, t_b, w)
        assert ca.size == n_expected, f"{ca.size} != {n_expected}"
        assert cb.size == n_expected
        assert cd.size == n_expected


class TestChunkedUnchunked:
    """Chunked and unchunked iteration must produce identical candidates."""

    def test_chunked_vs_unchunked(self) -> None:
        rng = np.random.default_rng(123)
        t_a = np.sort(rng.integers(0, 1_000_000, size=500))
        t_b = np.sort(rng.integers(0, 1_000_000, size=700))
        w = 200

        # unchunked
        cu_a, cu_b, cu_d = all_candidates(t_a, t_b, w)

        # chunked with small chunk size
        parts_a: list = []
        parts_b: list = []
        parts_d: list = []
        for ca, cb, cd in iter_all_candidates(t_a, t_b, w, chunk_events=100):
            if ca.size:
                parts_a.append(ca)
                parts_b.append(cb)
                parts_d.append(cd)
        if parts_a:
            cc_a = np.concatenate(parts_a)
            cc_b = np.concatenate(parts_b)
            cc_d = np.concatenate(parts_d)
        else:
            cc_a = np.array([], dtype=np.int64)
            cc_b = np.array([], dtype=np.int64)
            cc_d = np.array([], dtype=np.int64)

        assert np.array_equal(cu_a, cc_a), "t_a mismatch"
        assert np.array_equal(cu_b, cc_b), "t_b mismatch"
        assert np.array_equal(cu_d, cc_d), "delta mismatch"

    def test_chunk_events_big(self) -> None:
        """Very large chunk_events (>= t_a size) should give same result."""
        rng = np.random.default_rng(456)
        t_a = np.sort(rng.integers(0, 1_000_000, size=50))
        t_b = np.sort(rng.integers(0, 1_000_000, size=70))
        w = 200

        ref_a, ref_b, ref_d = all_candidates(t_a, t_b, w)
        # chunk with chunk_events larger than t_a size
        parts_a, parts_b, parts_d = [], [], []
        for ca, cb, cd in iter_all_candidates(t_a, t_b, w, chunk_events=10_000):
            if ca.size:
                parts_a.append(ca)
                parts_b.append(cb)
                parts_d.append(cd)
        if parts_a:
            big_a = np.concatenate(parts_a)
            big_b = np.concatenate(parts_b)
            big_d = np.concatenate(parts_d)
        else:
            big_a = big_b = big_d = np.array([], dtype=np.int64)

        assert np.array_equal(ref_a, big_a)
        assert np.array_equal(ref_b, big_b)
        assert np.array_equal(ref_d, big_d)

    def test_single_chunk_equivalence(self) -> None:
        """Chunking with chunk_events=1 must give same result as one big pass."""
        t_a = np.array([100, 200], dtype=np.int64)
        t_b = np.array([150, 250], dtype=np.int64)
        w = 100

        ref_a, ref_b, ref_d = all_candidates(t_a, t_b, w)
        parts_a, parts_b, parts_d = [], [], []
        for ca, cb, cd in iter_all_candidates(t_a, t_b, w, chunk_events=1):
            if ca.size:
                parts_a.append(ca)
                parts_b.append(cb)
                parts_d.append(cd)
        if parts_a:
            s_a = np.concatenate(parts_a)
            s_b = np.concatenate(parts_b)
            s_d = np.concatenate(parts_d)
        else:
            s_a = s_b = s_d = np.array([], dtype=np.int64)

        assert np.array_equal(ref_a, s_a), f"ref={ref_a} got={s_a}"
        assert np.array_equal(ref_b, s_b)
        assert np.array_equal(ref_d, s_d)


# ---------------------------------------------------------------------------
#  Tests for accumulators
# ---------------------------------------------------------------------------

class TestFixedLatticeAccumulator:
    """Test that accumulator totals match candidate counts."""

    def _tiny_candidates(self) -> tuple[np.ndarray, np.ndarray]:
        """Contrived t_a, t_b that produce known candidates."""
        # frame: N=4, bw=100 -> frame_len=400
        # t_a events at 50, 150, 250 (phase 50, 150, 250)
        # t_b events at 100, 200, 300, 500 (phase 100, 200, 300, 100)
        t_a = np.array([50, 150, 250], dtype=np.int64)
        t_b = np.array([100, 200, 300, 500], dtype=np.int64)
        return t_a, t_b

    def test_total_counts_match(self) -> None:
        """Check that after accumulation, all totals equal n_candidates_after_edge_guard."""
        t_a, t_b = self._tiny_candidates()
        acc = FixedLatticeAccumulator(
            n_bins=4,
            bin_width_ps=100,
            frame_origin_ps=0.0,
            coincidence_window_ps=200,
            edge_guard_ps=50,
            coarse_n_bins=2,
        )

        # First find candidates directly
        ca, cb, cd = all_candidates(t_a, t_b, 200)
        acc.add_candidates(ca, cb)

        # Check summary has consistent counts
        s = acc.summary()
        assert s["n_candidates_total"] >= s["n_candidates_after_edge_guard"]
        # Internal consistency check
        assert acc.check_internal_consistency(), (
            f"diag_sum={np.sum(acc.diag_profile):.0f} "
            f"row_sum={np.sum(acc.row_marginal):.0f} "
            f"col_sum={np.sum(acc.col_marginal):.0f} "
            f"target={acc.n_candidates_after_edge_guard}"
        )

    def test_edge_guard_reduces_count(self) -> None:
        """Edge guard should reject some candidates near boundaries."""
        t_a = np.array([5, 1000], dtype=np.int64)  # phase=5 -> near edge
        t_b = np.array([100, 2000], dtype=np.int64)
        # frame: N=100, bw=100 -> frame_len=10000
        acc_no_guard = FixedLatticeAccumulator(
            n_bins=100, bin_width_ps=100, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=0, coarse_n_bins=0,
        )
        acc_with_guard = FixedLatticeAccumulator(
            n_bins=100, bin_width_ps=100, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=100, coarse_n_bins=0,
        )
        ca, cb, cd = all_candidates(t_a, t_b, 200)
        acc_no_guard.add_candidates(ca, cb)
        acc_with_guard.add_candidates(ca, cb)

        assert acc_with_guard.n_candidates_after_edge_guard <= acc_no_guard.n_candidates_after_edge_guard
        assert acc_with_guard.edge_rejection_ratio >= 0.0

    def test_multiple_add_batches(self) -> None:
        """Accumulating candidates in multiple add_candidates calls."""
        rng = np.random.default_rng(789)
        t_a = np.sort(rng.integers(0, 1_000_000, size=200))
        t_b = np.sort(rng.integers(0, 1_000_000, size=300))
        w = 200

        # One-shot
        acc1 = FixedLatticeAccumulator(
            n_bins=1024, bin_width_ps=100, frame_origin_ps=0.0,
            coincidence_window_ps=w, edge_guard_ps=100, coarse_n_bins=64,
        )
        ca, cb, cd = all_candidates(t_a, t_b, w)
        acc1.add_candidates(ca, cb)

        # Split into 3 batches
        acc2 = FixedLatticeAccumulator(
            n_bins=1024, bin_width_ps=100, frame_origin_ps=0.0,
            coincidence_window_ps=w, edge_guard_ps=100, coarse_n_bins=64,
        )
        ca, cb, cd = all_candidates(t_a, t_b, w)
        split = ca.size // 3
        for i in range(3):
            lo = i * split
            hi = ca.size if i == 2 else (i + 1) * split
            acc2.add_candidates(ca[lo:hi], cb[lo:hi])

        assert acc1.n_candidates_total == acc2.n_candidates_total
        assert acc1.n_candidates_after_edge_guard == acc2.n_candidates_after_edge_guard
        assert np.isclose(acc1.edge_rejection_ratio, acc2.edge_rejection_ratio)
        assert acc1.check_internal_consistency()
        assert acc2.check_internal_consistency()

    def test_coarse_jti_shape(self) -> None:
        """Coarse JTI should have the requested shape."""
        acc = FixedLatticeAccumulator(
            n_bins=1024, bin_width_ps=100, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=0, coarse_n_bins=16,
        )
        t_a = np.array([100, 200, 300], dtype=np.int64)
        t_b = np.array([150, 250, 350], dtype=np.int64)
        ca, cb, cd = all_candidates(t_a, t_b, 200)
        acc.add_candidates(ca, cb)
        cjti = acc.coarse_jti
        assert cjti is not None
        assert cjti.shape == (16, 16)

    def test_zero_coarse_n_bins(self) -> None:
        """When coarse_n_bins=0, coarse_jti should remain None."""
        acc = FixedLatticeAccumulator(
            n_bins=1024, bin_width_ps=100, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=0, coarse_n_bins=0,
        )
        assert acc.coarse_jti is None

    def test_profile_width_summary_fields(self) -> None:
        """Summary should expose JSON-only diagonal profile width diagnostics."""
        acc = FixedLatticeAccumulator(
            n_bins=8, bin_width_ps=100, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=0, coarse_n_bins=0,
        )
        acc._diag_profile[:] = np.array([0, 1, 1, 1, 0, 0, 0, 0], dtype=np.float64)
        s = acc.summary()
        assert s["diag_profile_peak_bin"] == 1
        assert s["diag_profile_mass_width_90_bins"] >= 1
        assert s["diag_profile_mass_width_95_bins"] >= s["diag_profile_mass_width_90_bins"]
        assert 0.0 <= s["diag_profile_edge_fraction"] <= 1.0

    def test_diag_center_fields(self) -> None:
        """diag_center_* fields exist and peak bin/time are consistent."""
        n_bins = 16
        bin_width_ps = 100
        acc = FixedLatticeAccumulator(
            n_bins=n_bins, bin_width_ps=bin_width_ps, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=0, coarse_n_bins=0,
        )
        # t_a and t_b at the same timestamp → ba==bb → center bin near the middle
        t_a = np.array([500, 500, 500, 800], dtype=np.int64)
        t_b = np.array([500, 500, 500, 800], dtype=np.int64)
        ca, cb, _ = all_candidates(t_a, t_b, 200)
        acc.add_candidates(ca, cb)

        s = acc.summary()
        # diag_center_* keys must exist
        assert "diag_center_peak_bin" in s
        assert "diag_center_peak_time_ps" in s
        assert "diag_center_mass_width_90_bins" in s
        assert "diag_center_mass_width_95_bins" in s
        assert "diag_center_mass_width_90_ps" in s
        assert "diag_center_mass_width_95_ps" in s
        assert "diag_center_edge_fraction" in s

        # For ba=5 (t=500 ps, bw=100, origin=0), bb=5, center_bin = (5+5)//2 = 5
        # peak_time = 0 + (5 + 0.5) * 100 = 550 ps
        assert s["diag_center_peak_bin"] == 5
        assert s["diag_center_peak_time_ps"] == 550.0
        assert s["diag_center_mass_width_90_bins"] >= 1
        assert s["diag_center_mass_width_95_bins"] >= s["diag_center_mass_width_90_bins"]
        assert 0.0 <= s["diag_center_edge_fraction"] <= 1.0

    def test_diag_center_symmetry(self) -> None:
        """Symmetric pair positions should map to frame midpoint."""
        acc = FixedLatticeAccumulator(
            n_bins=100, bin_width_ps=100, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=0, coarse_n_bins=0,
        )
        # ba=0, bb=100-1=99 → center = (0+99)//2 = 49
        t_a = np.array([0], dtype=np.int64)
        t_b = np.array([99 * 100], dtype=np.int64)
        ca, cb, _ = all_candidates(t_a, t_b, 10_000)
        acc.add_candidates(ca, cb)

        s = acc.summary()
        # center_bin = 49, peak_time = 0 + (49+0.5)*100 = 4950 ps
        assert s["diag_center_peak_bin"] == 49
        assert s["diag_center_peak_time_ps"] == 4950.0

    def test_diag_center_circular_fields_exist(self) -> None:
        """diag_center_circular_* fields exist in summary."""
        acc = FixedLatticeAccumulator(
            n_bins=16, bin_width_ps=100, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=0, coarse_n_bins=0,
        )
        t_a = np.array([500, 500], dtype=np.int64)
        t_b = np.array([500, 500], dtype=np.int64)
        ca, cb, _ = all_candidates(t_a, t_b, 200)
        acc.add_candidates(ca, cb)

        s = acc.summary()
        for key in (
            "diag_center_circular_peak_bin",
            "diag_center_circular_peak_time_ps",
            "diag_center_circular_mass_width_90_bins",
            "diag_center_circular_mass_width_95_bins",
            "diag_center_circular_mass_width_90_ps",
            "diag_center_circular_mass_width_95_ps",
            "diag_center_circular_edge_fraction",
            "diag_center_linear_vs_circular_width_ratio",
        ):
            assert key in s, f"missing key: {key}"

    def test_diag_center_circular_non_wrap(self) -> None:
        """Non-wrap pair: ba=100, bb=102 → linear and circular centers agree."""
        n_bins = 1024
        bw = 100
        acc = FixedLatticeAccumulator(
            n_bins=n_bins, bin_width_ps=bw, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=0, coarse_n_bins=0,
        )
        # ba=100 (t=10000 ps), bb=102 (t=10200 ps)
        t_a = np.array([10000], dtype=np.int64)
        t_b = np.array([10200], dtype=np.int64)
        ca, cb, _ = all_candidates(t_a, t_b, 200)
        acc.add_candidates(ca, cb)

        s = acc.summary()
        # linear center: (100+102)//2 = 101
        assert s["diag_center_peak_bin"] == 101
        # circular center: delta = (102-100) % 1024 = 2, not > 512, so no unwrap
        # circular_center = (100+102)//2 = 101
        assert s["diag_center_circular_peak_bin"] == 101
        # Both should be identical for non-wrap pairs
        assert s["diag_center_mass_width_95_bins"] == s["diag_center_circular_mass_width_95_bins"]
        assert s["diag_center_linear_vs_circular_width_ratio"] == 1.0

    def test_diag_center_circular_wrap(self) -> None:
        """Wrap pair: ba=0, bb=N-1 → linear center at N/2, circular center near boundary."""
        n_bins = 100
        bw = 100
        acc = FixedLatticeAccumulator(
            n_bins=n_bins, bin_width_ps=bw, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=0, coarse_n_bins=0,
        )
        # ba=0 (t=0 ps), bb=99 (t=9900 ps)
        t_a = np.array([0], dtype=np.int64)
        t_b = np.array([9900], dtype=np.int64)
        ca, cb, _ = all_candidates(t_a, t_b, 10_000)
        acc.add_candidates(ca, cb)

        s = acc.summary()
        # linear center: (0+99)//2 = 49
        assert s["diag_center_peak_bin"] == 49
        # circular center: delta = (99-0) % 100 = 99, > 50 → unwrap bb to 99-100 = -1
        # circular_center = (0 + (-1)) // 2 = -1 (integer division), mod 100 = 99
        assert s["diag_center_circular_peak_bin"] == 99
        # Circular center should be near boundary, not at N/2
        assert s["diag_center_circular_peak_bin"] != n_bins // 2

    def test_diag_center_circular_empty(self) -> None:
        """Empty input: all circular fields should be zero/-1."""
        acc = FixedLatticeAccumulator(
            n_bins=16, bin_width_ps=100, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=0, coarse_n_bins=0,
        )
        t_a = np.array([], dtype=np.int64)
        t_b = np.array([], dtype=np.int64)
        acc.add_candidates(t_a, t_b)

        s = acc.summary()
        assert s["diag_center_circular_peak_bin"] == -1
        assert s["diag_center_circular_peak_time_ps"] == -1.0
        assert s["diag_center_circular_mass_width_90_bins"] == 0
        assert s["diag_center_circular_mass_width_95_bins"] == 0
        assert s["diag_center_circular_mass_width_90_ps"] == 0
        assert s["diag_center_circular_mass_width_95_ps"] == 0
        assert s["diag_center_circular_edge_fraction"] == 0.0

    def test_diag_center_circular_consistency(self) -> None:
        """Circular profile total must equal n_candidates_after_edge_guard."""
        rng = np.random.default_rng(42)
        t_a = np.sort(rng.integers(0, 1_000_000, size=200))
        t_b = np.sort(rng.integers(0, 1_000_000, size=300))
        acc = FixedLatticeAccumulator(
            n_bins=1024, bin_width_ps=100, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=100, coarse_n_bins=0,
        )
        ca, cb, _ = all_candidates(t_a, t_b, 200)
        acc.add_candidates(ca, cb)

        assert acc.check_internal_consistency()
        s = acc.summary()
        assert s["diag_center_circular_mass_width_95_bins"] >= s["diag_center_circular_mass_width_90_bins"]

    def test_diag_center_circular_reverse_wrap(self) -> None:
        """Reverse wrap pair: ba=N-1, bb=0 → circular center near boundary, not N/2."""
        n_bins = 100
        bw = 100
        acc = FixedLatticeAccumulator(
            n_bins=n_bins, bin_width_ps=bw, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=0, coarse_n_bins=0,
        )
        # ba=99 (t=9900 ps), bb=0 (t=0 ps)
        t_a = np.array([9900], dtype=np.int64)
        t_b = np.array([0], dtype=np.int64)
        ca, cb, _ = all_candidates(t_a, t_b, 10_000)
        acc.add_candidates(ca, cb)

        s = acc.summary()
        # linear center: (99+0)//2 = 49
        assert s["diag_center_peak_bin"] == 49
        # circular center: d = ((0-99+50)%100)-50 = (51%100)-50 = 51-50 = 1
        # circular_center = (99 + floor(1/2)) % 100 = (99+0) % 100 = 99
        assert s["diag_center_circular_peak_bin"] == 99
        # Circular center should be near boundary, not at N/2
        assert s["diag_center_circular_peak_bin"] != n_bins // 2

    def test_diag_center_circular_min_arc_width_fields_exist(self) -> None:
        """circular_min_arc_width_* fields exist in summary."""
        acc = FixedLatticeAccumulator(
            n_bins=16, bin_width_ps=100, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=0, coarse_n_bins=0,
        )
        t_a = np.array([500, 500], dtype=np.int64)
        t_b = np.array([500, 500], dtype=np.int64)
        ca, cb, _ = all_candidates(t_a, t_b, 200)
        acc.add_candidates(ca, cb)

        s = acc.summary()
        for key in (
            "diag_center_circular_min_arc_width_90_bins",
            "diag_center_circular_min_arc_width_95_bins",
            "diag_center_circular_min_arc_width_90_ps",
            "diag_center_circular_min_arc_width_95_ps",
        ):
            assert key in s, f"missing key: {key}"

    def test_diag_center_circular_min_arc_width_narrow(self) -> None:
        """Narrow cluster at boundary → min_arc_width should be small."""
        n_bins = 100
        bw = 100
        acc = FixedLatticeAccumulator(
            n_bins=n_bins, bin_width_ps=bw, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=0, coarse_n_bins=0,
        )
        # Manually set circular profile: mass concentrated at bins 99, 0, 1
        acc._diag_center_circular_profile[99] = 10.0
        acc._diag_center_circular_profile[0] = 10.0
        acc._diag_center_circular_profile[1] = 10.0
        acc._n_candidates_after_edge_guard = 30

        s = acc.summary()
        # 95% of 30 = 28.5, covered by 3 bins → min_arc_width_95 should be ≤ 3
        assert s["diag_center_circular_min_arc_width_95_bins"] <= 3
        assert s["diag_center_circular_min_arc_width_95_ps"] <= 300

    def test_diag_center_circular_min_arc_width_uniform(self) -> None:
        """Uniform profile → min_arc_width should be close to N."""
        n_bins = 100
        bw = 100
        acc = FixedLatticeAccumulator(
            n_bins=n_bins, bin_width_ps=bw, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=0, coarse_n_bins=0,
        )
        # Uniform profile
        acc._diag_center_circular_profile[:] = 1.0
        acc._n_candidates_after_edge_guard = 100

        s = acc.summary()
        # 95% of 100 = 95, need 95 bins → min_arc_width_95 should be 95
        assert s["diag_center_circular_min_arc_width_95_bins"] == 95

    def test_diag_center_circular_min_arc_width_empty(self) -> None:
        """Empty profile → min_arc_width should be 0."""
        acc = FixedLatticeAccumulator(
            n_bins=16, bin_width_ps=100, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=0, coarse_n_bins=0,
        )
        s = acc.summary()
        assert s["diag_center_circular_min_arc_width_90_bins"] == 0
        assert s["diag_center_circular_min_arc_width_95_bins"] == 0
        assert s["diag_center_circular_min_arc_width_90_ps"] == 0
        assert s["diag_center_circular_min_arc_width_95_ps"] == 0


# ---------------------------------------------------------------------------
#  Hardening tests
# ---------------------------------------------------------------------------

class TestChunkEventsValidation:
    """chunk_events <= 0 must raise ValueError."""

    def test_zero(self) -> None:
        t_a = np.array([100, 200], dtype=np.int64)
        t_b = np.array([150, 250], dtype=np.int64)
        with pytest.raises(ValueError, match="chunk_events must be positive"):
            next(iter_all_candidates(t_a, t_b, 100, chunk_events=0))

    def test_negative(self) -> None:
        t_a = np.array([100, 200], dtype=np.int64)
        t_b = np.array([150, 250], dtype=np.int64)
        with pytest.raises(ValueError, match="chunk_events must be positive"):
            next(iter_all_candidates(t_a, t_b, 100, chunk_events=-1))


class TestAddCandidatesValidation:
    """add_candidates must reject mismatched input arrays."""

    def test_shape_mismatch(self) -> None:
        acc = FixedLatticeAccumulator(
            n_bins=4, bin_width_ps=100, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=0,
        )
        t_a = np.array([100, 200], dtype=np.int64)
        t_b = np.array([150], dtype=np.int64)  # different length
        with pytest.raises(ValueError, match="t_a and t_b must have the same shape"):
            acc.add_candidates(t_a, t_b)

    def test_both_empty(self) -> None:
        """Both empty is allowed (no error)."""
        acc = FixedLatticeAccumulator(
            n_bins=4, bin_width_ps=100, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=0,
        )
        t_a = np.array([], dtype=np.int64)
        t_b = np.array([], dtype=np.int64)
        acc.add_candidates(t_a, t_b)  # must not raise
        assert acc.n_candidates_total == 0
