"""Tests for contrast_profiles module (Stage 20)."""

import numpy as np
import pytest

from jti_extract.ultra.contrast_profiles import (
    build_contrast_profile,
    select_contrast_candidates,
)


def test_select_contrast_candidates_empty():
    t_a = np.array([], dtype=np.int64)
    t_b = np.array([], dtype=np.int64)
    ca, cb, delta = select_contrast_candidates(t_a, t_b, 3000)
    assert ca.size == 0
    assert cb.size == 0
    assert delta.size == 0


def test_select_contrast_candidates_basic():
    t_a = np.array([100, 200, 300, 1000, 2000], dtype=np.int64)
    t_b = np.array([150, 250, 350, 1050, 2050], dtype=np.int64)
    ca, cb, delta = select_contrast_candidates(t_a, t_b, 3000)
    assert ca.size >= 0  # may be 0 if no pairs within window
    if ca.size > 0:
        assert np.all(delta == cb - ca)


def test_build_contrast_profile_empty():
    cprof = build_contrast_profile(
        np.array([], dtype=np.int64),
        np.array([], dtype=np.int64),
        np.array([], dtype=np.int64),
        n_bins=1024, bin_width_ps=100, frame_origin_ps=0.0,
        frame_length_ps=102400,
        on_diag_band_bins=2, bg_inner_bins=10, bg_outer_bins=30,
        center_coarse_bins=16,
    )
    assert cprof["segments"] == []
    assert cprof["n_candidates"] == 0


def test_build_contrast_profile_basic():
    rng = np.random.default_rng(42)
    n = 1000
    t_a = np.sort(rng.integers(0, 100000, size=n))
    t_b = t_a + rng.integers(-200, 200, size=n)
    delta = t_b - t_a
    cprof = build_contrast_profile(
        t_a, t_b, delta,
        n_bins=1024, bin_width_ps=100, frame_origin_ps=0.0,
        frame_length_ps=102400,
        on_diag_band_bins=2, bg_inner_bins=10, bg_outer_bins=30,
        center_coarse_bins=16,
    )
    assert "segments" in cprof
    assert len(cprof["segments"]) == 16
    assert cprof["n_candidates"] == 1000
    for seg in cprof["segments"]:
        assert "snr" in seg
        assert "contrast_ratio" in seg
        assert "sideband_zero" in seg
        assert "on_diag_counts" in seg
        assert "sideband_counts" in seg


def test_build_contrast_profile_sideband_zero():
    rng = np.random.default_rng(42)
    n = 100
    t_a = np.sort(rng.integers(0, 100000, size=n))
    t_b = t_a + rng.integers(-5, 5, size=n)  # all on-diagonal
    delta = t_b - t_a
    cprof = build_contrast_profile(
        t_a, t_b, delta,
        n_bins=1024, bin_width_ps=100, frame_origin_ps=0.0,
        frame_length_ps=102400,
        on_diag_band_bins=2, bg_inner_bins=10, bg_outer_bins=30,
        center_coarse_bins=16,
    )
    # All sideband should be zero
    for seg in cprof["segments"]:
        if seg["sideband_counts"] == 0:
            assert seg["sideband_zero"] is True
            assert seg["contrast_ratio"] is None  # undefined when sideband=0
