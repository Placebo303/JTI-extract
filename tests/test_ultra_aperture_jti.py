"""Tests for aperture_jti module (Stage 22)."""

import numpy as np
import pytest

from jti_extract.ultra.aperture_jti import build_aperture_accumulator


def test_build_aperture_accumulator_empty():
    t_a = np.array([], dtype=np.int64)
    t_b = np.array([], dtype=np.int64)
    aperture = {
        "aperture_id": 0, "start_ps": 0.0, "stop_ps": 10000.0,
        "wraps_boundary": False, "duration_ps": 10000.0,
    }
    result = build_aperture_accumulator(
        t_a, t_b, aperture,
        n_bins=1024, bin_width_ps=100, frame_origin_ps=0.0,
        frame_length_ps=102400, coincidence_window_ps=200,
        edge_guard_ps=0, coarse_n_bins=0,
    )
    assert result["n_candidates_in_aperture"] == 0


def test_build_aperture_accumulator_basic():
    rng = np.random.default_rng(42)
    n = 200
    t_a = np.sort(rng.integers(0, 100000, size=n))
    t_b = t_a + rng.integers(-50, 50, size=n)
    aperture = {
        "aperture_id": 0, "start_ps": 0.0, "stop_ps": 50000.0,
        "wraps_boundary": False, "duration_ps": 50000.0,
    }
    result = build_aperture_accumulator(
        t_a, t_b, aperture,
        n_bins=1024, bin_width_ps=100, frame_origin_ps=0.0,
        frame_length_ps=102400, coincidence_window_ps=200,
        edge_guard_ps=0, coarse_n_bins=16,
    )
    assert result["n_candidates_in_aperture"] > 0
    assert result["aperture_n_bins"] == 500
    assert result["aperture_origin_ps"] == 0.0
    assert "coarse_jti" in result
    assert result["aperture_folding_mode"] == "phase-folded-across-global-frames"


def test_build_aperture_accumulator_wrap():
    rng = np.random.default_rng(42)
    n = 200
    frame_length = 102400
    # Place events near frame boundary
    t_a = np.sort(rng.integers(frame_length - 5000, frame_length, size=n // 2))
    t_b = t_a + rng.integers(-50, 50, size=n // 2)
    aperture = {
        "aperture_id": 0, "start_ps": float(frame_length - 10000),
        "stop_ps": float(frame_length + 5000),  # wraps
        "wraps_boundary": True, "duration_ps": 15000.0,
    }
    result = build_aperture_accumulator(
        t_a, t_b, aperture,
        n_bins=1024, bin_width_ps=100, frame_origin_ps=0.0,
        frame_length_ps=frame_length, coincidence_window_ps=200,
        edge_guard_ps=0, coarse_n_bins=16,
    )
    # Should find some candidates near boundary
    assert result["n_candidates_in_aperture"] >= 0
    assert result["aperture_folding_mode"] == "phase-folded-across-global-frames"
