"""Tests for jti_extract.ultra.cross_validate."""

import numpy as np

from jti_extract.ultra.cross_validate import cross_validate_ultra_vs_strict


class TestCrossValidateUltraVsStrict:
    def test_returns_expected_keys(self) -> None:
        t_a = np.array([100, 200, 300, 1000], dtype=np.int64)
        t_b = np.array([150, 250, 350, 1050], dtype=np.int64)
        result = cross_validate_ultra_vs_strict(
            t_a, t_b,
            n_bins=1024, bin_width_ps=100, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=0, coarse_n_bins=16,
        )
        expected_keys = {
            "ultra_n_candidates", "ultra_n_after_edge",
            "strict_n_pairs", "strict_n_strict_pairs",
            "strict_single_hit_retention_a", "strict_single_hit_retention_b",
            "ratio_ultra_vs_strict",
        }
        assert expected_keys.issubset(set(result.keys())), (
            f"missing: {expected_keys - set(result.keys())}"
        )

    def test_ultra_ge_strict(self) -> None:
        """Ultra all-candidates should be >= strict pairs."""
        t_a = np.array([100, 200, 300], dtype=np.int64)
        t_b = np.array([150, 250, 350], dtype=np.int64)
        result = cross_validate_ultra_vs_strict(
            t_a, t_b,
            n_bins=1024, bin_width_ps=100, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=0, coarse_n_bins=0,
        )
        assert result["ultra_n_after_edge"] >= result["strict_n_pairs"]

    def test_empty_input(self) -> None:
        t_a = np.array([], dtype=np.int64)
        t_b = np.array([], dtype=np.int64)
        result = cross_validate_ultra_vs_strict(
            t_a, t_b,
            n_bins=4, bin_width_ps=100, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=0, coarse_n_bins=0,
        )
        assert result["ultra_n_candidates"] == 0.0
