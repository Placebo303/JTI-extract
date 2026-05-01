"""Tests for surrogate_controls module (Stage 24)."""

import numpy as np
import pytest

from jti_extract.ultra.surrogate_controls import (
    phase_shuffle_surrogate,
    summarize_contrast_profile,
    time_shift_surrogate,
)


def test_summarize_contrast_profile_empty():
    result = summarize_contrast_profile({"segments": []})
    assert result["max_snr"] == 0.0
    assert result["n_snr3"] == 0


def test_summarize_contrast_profile_basic():
    segments = [
        {"snr": 4.0, "contrast_ratio": 10.0},
        {"snr": 2.0, "contrast_ratio": 5.0},
        {"snr": 6.0, "contrast_ratio": None},
    ]
    result = summarize_contrast_profile({"segments": segments})
    assert result["max_snr"] == 6.0
    assert result["n_snr3"] == 2
    assert result["max_contrast_ratio"] == 10.0


def test_time_shift_surrogate():
    rng = np.random.default_rng(42)
    n = 100
    t_a = np.sort(rng.integers(0, 100000, size=n))
    t_b = t_a + rng.integers(-50, 50, size=n)
    cprof = time_shift_surrogate(
        t_a, t_b, shift_ps=100000,
        contrast_window_ps=3000, n_bins=1024, bin_width_ps=100,
        frame_origin_ps=0.0, frame_length_ps=102400,
        on_diag_band_bins=2, bg_inner_bins=10, bg_outer_bins=30,
        center_coarse_bins=16,
    )
    assert "segments" in cprof


def test_phase_shuffle_surrogate():
    rng = np.random.default_rng(42)
    n = 100
    t_a = np.sort(rng.integers(0, 100000, size=n))
    t_b = t_a + rng.integers(-50, 50, size=n)
    cprof = phase_shuffle_surrogate(
        t_a, t_b, rng,
        contrast_window_ps=3000, n_bins=1024, bin_width_ps=100,
        frame_origin_ps=0.0, frame_length_ps=102400,
        on_diag_band_bins=2, bg_inner_bins=10, bg_outer_bins=30,
        center_coarse_bins=16,
    )
    assert "segments" in cprof
    # Phase-shuffle should preserve frame index, so some candidates should remain
    assert cprof["n_candidates"] > 0
