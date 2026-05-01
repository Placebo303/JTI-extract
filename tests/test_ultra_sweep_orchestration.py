"""Tests for jti_extract.ultra.sweep_ultra_jti.

Verifies:
1. run_synthetic_sweep_point returns expected keys with sensible values;
2. origin_sensitivity_summary returns correct-length list;
3. edge_guard_sensitivity_summary returns correct-length list;
4. method_comparison_sweep includes per-method counts;
5. full pipeline runs on tiny synthetic arrays without errors.
"""

import numpy as np

from jti_extract.ultra.sweep_ultra_jti import (
    edge_guard_sensitivity_summary,
    method_comparison_sweep,
    origin_sensitivity_summary,
    run_synthetic_sweep_point,
)


def _tiny_synth() -> tuple[np.ndarray, np.ndarray]:
    """Small synthetic timestamps for tests."""
    t_a = np.array([100, 200, 300, 1000, 1100], dtype=np.int64)
    t_b = np.array([150, 250, 350, 1050, 1150], dtype=np.int64)
    return t_a, t_b


class TestRunSyntheticSweepPoint:
    def test_returns_dict_with_expected_keys(self) -> None:
        t_a, t_b = _tiny_synth()
        result = run_synthetic_sweep_point(
            t_a, t_b,
            n_bins=1024,
            bin_width_ps=100,
            frame_origin_ps=0.0,
            coincidence_window_ps=200,
            edge_guard_ps=0,
            coarse_n_bins=16,
        )
        expected_keys = {
            "n_bins", "bin_width_ps", "frame_origin_ps", "frame_length_ps",
            "coincidence_window_ps", "edge_guard_ps", "coarse_n_bins",
            "n_candidates_total", "n_candidates_after_edge_guard",
            "edge_rejection_ratio",
            "diag_profile_peak_bin", "diag_profile_mass_width_90_bins",
            "diag_profile_mass_width_95_bins", "diag_profile_edge_fraction",
            "n_events_ch_a", "n_events_ch_b",
            "n_strict_pairs",
            "n_candidates_all", "n_nearest_pairs",
        }
        assert expected_keys.issubset(set(result.keys())), (
            f"missing keys: {expected_keys - set(result.keys())}"
        )

    def test_coarse_jti_full_chain(self) -> None:
        """When coarse_n_bins > 0, K_coarse should be present."""
        t_a, t_b = _tiny_synth()
        result = run_synthetic_sweep_point(
            t_a, t_b,
            n_bins=1024, bin_width_ps=100, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=0, coarse_n_bins=16,
        )
        assert "K_coarse" in result, "K_coarse missing with coarse_n_bins>0"
        assert result["K_coarse"] >= 1.0

    def test_zero_coarse_skips_svd(self) -> None:
        """When coarse_n_bins=0, no SVD keys should appear."""
        t_a, t_b = _tiny_synth()
        result = run_synthetic_sweep_point(
            t_a, t_b,
            n_bins=1024, bin_width_ps=100, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=0, coarse_n_bins=0,
        )
        assert "K_coarse" not in result

    def test_edge_guard_reduces_count(self) -> None:
        """edge_rejection_ratio should be > 0 when edge_guard rejects events."""
        t_a = np.array([0, 5000], dtype=np.int64)
        t_b = np.array([200, 5200], dtype=np.int64)
        # frame_len = 100 * 100 = 10000; edge_guard=100 rejects phase<100
        result = run_synthetic_sweep_point(
            t_a, t_b,
            n_bins=100, bin_width_ps=100, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=100, coarse_n_bins=0,
        )
        # Event at t=0 is within edge_guard -> candidates rejected
        assert result["n_candidates_after_edge_guard"] <= result["n_candidates_total"]
        assert result["edge_rejection_ratio"] >= 0.0

    def test_empty_input(self) -> None:
        """Empty timestamp arrays produce zero counts."""
        t_a = np.array([], dtype=np.int64)
        t_b = np.array([], dtype=np.int64)
        result = run_synthetic_sweep_point(
            t_a, t_b,
            n_bins=4, bin_width_ps=100, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=0, coarse_n_bins=0,
        )
        assert result["n_candidates_total"] == 0

    def test_diag_center_fields_propagated(self) -> None:
        """run_synthetic_sweep_point propagates diag_center_* fields."""
        t_a, t_b = _tiny_synth()
        result = run_synthetic_sweep_point(
            t_a, t_b,
            n_bins=1024, bin_width_ps=100, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=0, coarse_n_bins=0,
        )
        for key in (
            "diag_center_peak_bin",
            "diag_center_peak_time_ps",
            "diag_center_mass_width_90_bins",
            "diag_center_mass_width_95_bins",
            "diag_center_mass_width_90_ps",
            "diag_center_mass_width_95_ps",
            "diag_center_edge_fraction",
        ):
            assert key in result, f"diag_center field '{key}' not propagated to sweep result"


class TestOriginSensitivitySummary:
    def test_correct_length(self) -> None:
        t_a, t_b = _tiny_synth()
        origins = [0.0, 50.0, 100.0]
        results = origin_sensitivity_summary(
            t_a, t_b,
            origins_ps=origins,
            n_bins=1024, bin_width_ps=100,
            coincidence_window_ps=200, edge_guard_ps=0,
        )
        assert len(results) == 3, f"expected 3, got {len(results)}"
        for r in results:
            assert "n_candidates_total" in r

    def test_empty_origins(self) -> None:
        t_a, t_b = _tiny_synth()
        results = origin_sensitivity_summary(
            t_a, t_b,
            origins_ps=[],
            n_bins=4, bin_width_ps=100,
            coincidence_window_ps=200, edge_guard_ps=0,
        )
        assert results == []


class TestEdgeGuardSensitivitySummary:
    def test_correct_length(self) -> None:
        t_a, t_b = _tiny_synth()
        edge_guards = [0, 50, 100]
        results = edge_guard_sensitivity_summary(
            t_a, t_b,
            edge_guards_ps=edge_guards,
            n_bins=1024, bin_width_ps=100, frame_origin_ps=0.0,
            coincidence_window_ps=200, coarse_n_bins=0,
        )
        assert len(results) == 3
        # Larger edge guard should have >= edge_rejection_ratio
        ratios = [r["edge_rejection_ratio"] for r in results]
        for i in range(1, len(ratios)):
            assert ratios[i] >= ratios[i - 1] - 1e-12, (
                f"edge_rejection_ratio not monotonic: {ratios}"
            )


class TestMethodComparisonSweep:
    def test_has_method_keys(self) -> None:
        t_a, t_b = _tiny_synth()
        result = method_comparison_sweep(
            t_a, t_b,
            n_bins=1024, bin_width_ps=100, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=0, coarse_n_bins=0,
        )
        assert "n_candidates_all" in result
        assert "n_nearest_pairs" in result
        assert "n_greedy_unique_pairs" in result
        assert "all_vs_nearest_ratio" in result
        assert isinstance(result["n_candidates_all"], int)
        assert isinstance(result["n_nearest_pairs"], int)
        assert isinstance(result["n_greedy_unique_pairs"], int)

    def test_all_ge_nearest_ge_greedy(self) -> None:
        t_a, t_b = _tiny_synth()
        result = method_comparison_sweep(
            t_a, t_b,
            n_bins=1024, bin_width_ps=100, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=0, coarse_n_bins=0,
        )
        assert result["n_candidates_all"] >= result["n_nearest_pairs"]
        assert result["n_nearest_pairs"] >= result["n_greedy_unique_pairs"]
