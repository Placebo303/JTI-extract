"""Tests for jti_extract.ultra.diagnostics_pairing.

Verifies:
1. strict_retention_meta produces plausible stats on synthetic arrays;
2. method_comparison_summary produces n_candidates_all >= n_nearest >= n_greedy;
3. all functions work with empty inputs without errors.
"""

import numpy as np

from jti_extract.ultra.diagnostics_pairing import (
    _greedy_unique_pairs,
    _nearest_pairs,
    method_comparison_summary,
    strict_retention_meta,
)


class TestStrictRetentionMeta:
    def test_empty(self) -> None:
        t_a = np.array([], dtype=np.int64)
        t_b = np.array([], dtype=np.int64)
        meta = strict_retention_meta(t_a, t_b, 0.0, 100, 1024)
        assert meta["n_events_ch_a"] == 0.0
        assert meta["n_strict_pairs"] == 0.0

    def test_single_hit_frame(self) -> None:
        """Single event per frame per channel -> strict finds a pair."""
        # N=4, bw=100 -> frame_len=400
        # t_a=50, t_b=150 -> same frame (frame 0), single hit each
        t_a = np.array([50], dtype=np.int64)
        t_b = np.array([150], dtype=np.int64)
        meta = strict_retention_meta(t_a, t_b, 0.0, 100, 4)
        assert meta["n_strict_pairs"] == 1.0
        assert meta["single_hit_retention_ratio_a"] == 1.0

    def test_multi_hit_rejected(self) -> None:
        """Frame with two hits on one channel is rejected by strict."""
        # N=4, bw=100 -> frame_len=400, so bin indices [0,400)
        # t_a: 50 -> bin 0, frame 0; 150 -> bin 1, frame 0 (same frame)
        # t_b: 50 -> bin 0, frame 0
        # t_a has multi-hit in frame 0 -> both rejected -> no common frames
        t_a = np.array([50, 150], dtype=np.int64)
        t_b = np.array([50], dtype=np.int64)
        meta = strict_retention_meta(t_a, t_b, 0.0, 100, 4)
        assert meta["n_strict_pairs"] == 0.0
        # both events in t_a are in the multi-hit frame, so 2 are rejected
        assert meta["multi_hit_rejected_a"] == 2.0

    def test_retention_ratios(self) -> None:
        """Compute retention ratio for a mixed case."""
        # N=100, bw=100 -> frame_len=10000
        # t_a: events at 0, 5000, 10000 -> frames 0,0,1
        # t_b: events at 2000, 12000 -> frames 0,1
        t_a = np.array([0, 5000, 10000], dtype=np.int64)
        t_b = np.array([2000, 12000], dtype=np.int64)
        meta = strict_retention_meta(t_a, t_b, 0.0, 100, 100)
        # t_a: frame 0 has 2 events -> multi-hit, rejected
        #      frame 1 has 1 event -> single-hit, kept
        # t_b: frame 0 has 1 event -> single-hit, kept
        #      frame 1 has 1 event -> single-hit, kept
        # common frames: frame 1 -> 1 strict pair
        assert meta["n_strict_pairs"] == 1.0
        assert meta["n_events_ch_a"] == 3.0
        assert meta["n_single_hit_frames_a"] == 1.0  # only frame 1
        assert meta["single_hit_retention_ratio_a"] == 1.0 / 3.0


class TestNearestPairs:
    def test_empty(self) -> None:
        ca, cb, cd = _nearest_pairs(np.array([], dtype=np.int64), np.array([1], dtype=np.int64), 100)
        assert ca.size == 0

    def test_nearest_basic(self) -> None:
        t_a = np.array([100, 200], dtype=np.int64)
        t_b = np.array([150, 250], dtype=np.int64)
        ca, cb, cd = _nearest_pairs(t_a, t_b, 100)
        # t_a=100 -> nearest is 150 (delta=50)
        # t_a=200 -> nearest: right search finds 250 (delta=50),
        #            left search finds 150 (delta=-50).
        #            |50| == |50|, tie.  use_left picks 150 because
        #            |left_delta| < |best_delta| is False (equal),
        #            so left is NOT used -> 250 wins.
        expected = {(100, 150, 50), (200, 250, 50)}
        got = set(zip(ca, cb, cd))
        assert got == expected, f"got {got}"


class TestGreedyUniquePairs:
    def test_empty(self) -> None:
        ca, cb, cd = _greedy_unique_pairs(np.array([], dtype=np.int64), np.array([1], dtype=np.int64), 100)
        assert ca.size == 0

    def test_greedy_basic(self) -> None:
        t_a = np.array([100, 200], dtype=np.int64)
        t_b = np.array([150, 250], dtype=np.int64)
        ca, cb, cd = _greedy_unique_pairs(t_a, t_b, 100)
        # t_a=100 consumes t_b=150, t_a=200 consumes t_b=250
        expected = {(100, 150, 50), (200, 250, 50)}
        got = set(zip(ca, cb, cd))
        assert got == expected, f"got {got}"


class TestMethodComparisonSummary:
    def test_empty(self) -> None:
        t_a = np.array([], dtype=np.int64)
        t_b = np.array([], dtype=np.int64)
        s = method_comparison_summary(t_a, t_b, 200)
        assert s["n_candidates_all"] == 0.0
        assert s["n_nearest_pairs"] == 0.0
        assert s["n_greedy_unique_pairs"] == 0.0

    def test_all_ge_nearest_ge_greedy(self) -> None:
        """All-candidates >= nearest >= greedy-unique."""
        rng = np.random.default_rng(42)
        t_a = np.sort(rng.integers(0, 1_000_000, size=200))
        t_b = np.sort(rng.integers(0, 1_000_000, size=300))
        s = method_comparison_summary(t_a, t_b, 200)
        assert s["n_candidates_all"] >= s["n_nearest_pairs"]
        assert s["n_nearest_pairs"] >= s["n_greedy_unique_pairs"]
