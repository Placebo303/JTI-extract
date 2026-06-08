"""Tests for CV/DV/SVD unwrapped JTI extraction functions."""
from __future__ import annotations

import numpy as np

from jti_extract.cli.extract import (
    _RawTimetags,
    _compute_cv_histogram,
    _compute_dv_matrix,
    _compute_unwrapped_edge_guarded_jti,
    _find_coincidence_pairs,
    _time_tags_to_bins,
    compute_jti_diagnostics,
    diagonal_coincidence_profile,
)


# ---------------------------------------------------------------------------
# Integer binning precision tests
# ---------------------------------------------------------------------------

def test_time_tags_to_bins_integer_precision() -> None:
    """Verify that 17-digit timestamps are handled without float64 precision loss."""
    # Typical timestamp: ~3.688e16 ps (17 digits)
    # float64 has ~15.9 significant digits, so direct float conversion loses ~1 digit
    times = np.asarray([36880089746026674, 36880089746026684, 36880089746026694], dtype=np.int64)
    bins = _time_tags_to_bins(times, bin_width_ps=10, frame_origin_ps=0)

    # All three timestamps differ by 10ps, so should map to consecutive bins
    assert bins[1] - bins[0] == 1
    assert bins[2] - bins[1] == 1

    # With float64, the differences could be wrong due to precision loss
    # Integer arithmetic should preserve exact bin assignments


def test_time_tags_to_bins_origin_offset() -> None:
    """Verify that frame_origin_ps shifts bins correctly."""
    times = np.asarray([100, 110, 120], dtype=np.int64)

    bins_0 = _time_tags_to_bins(times, bin_width_ps=10, frame_origin_ps=0)
    bins_5 = _time_tags_to_bins(times, bin_width_ps=10, frame_origin_ps=5)

    # Origin shift of 5ps should shift bins by -0.5, floored to -1
    assert bins_0.tolist() == [10, 11, 12]
    assert bins_5.tolist() == [9, 10, 11]


# ---------------------------------------------------------------------------
# CV histogram tests
# ---------------------------------------------------------------------------

def test_compute_cv_histogram_shape() -> None:
    """Verify CV histogram has correct shape."""
    t_a = np.asarray([100, 200, 300], dtype=np.int64)
    t_b = np.asarray([105, 205, 305], dtype=np.int64)

    cv = _compute_cv_histogram(
        t_a, t_b,
        frame_period_ps=1000,
        fine_bin_ps=5,
        frame_origin_ps=0,
    )

    assert cv.shape == (200, 200)  # 1000 / 5 = 200 bins


def test_compute_cv_histogram_integer_binning() -> None:
    """Verify CV histogram uses integer arithmetic (no float64 bias)."""
    # Create pairs with uniform modulo distribution
    n = 10000
    t_a = np.arange(n, dtype=np.int64) * 40  # every 40ps
    t_b = t_a + 5  # 5ps offset

    cv = _compute_cv_histogram(
        t_a, t_b,
        frame_period_ps=40,
        fine_bin_ps=5,
        frame_origin_ps=0,
    )

    # Each row should have exactly one non-zero entry (since t_b = t_a + 5)
    for i in range(cv.shape[0]):
        non_zero = np.count_nonzero(cv[i, :])
        assert non_zero <= 1, f"Row {i} has {non_zero} non-zero entries"


# ---------------------------------------------------------------------------
# DV matrix tests
# ---------------------------------------------------------------------------

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


def test_compute_dv_matrix_integer_binning() -> None:
    """Verify DV matrix uses integer arithmetic (no mod4 bias)."""
    # Create many pairs to test for systematic bias
    n = 100000
    t_a = np.random.randint(0, 1000000, size=n, dtype=np.int64) * 10
    t_b = t_a + np.random.randint(-5, 6, size=n).astype(np.int64)

    dv = _compute_dv_matrix(
        t_a, t_b,
        dimension=128,
        binwidth_ps=10,
        frame_origin_ps=0,
    )

    # Check mod4 distribution on diagonal (should be uniform)
    diag = np.diag(dv)
    means = []
    for m in range(4):
        mask = np.arange(128) % 4 == m
        means.append(float(np.mean(diag[mask])))

    # All mod4 classes should have similar mean counts
    max_ratio = max(means) / min(means) if min(means) > 0 else float('inf')
    assert max_ratio < 1.5, f"mod4 ratio too high: {max_ratio}, means={means}"


# ---------------------------------------------------------------------------
# Unwrapped edge-guarded JTI tests
# ---------------------------------------------------------------------------

def test_compute_unwrapped_edge_guarded_jti_corners_zero() -> None:
    """Verify that unwrapped JTI has zero corners (no wrap-around)."""
    # Create pairs that would wrap around in modulo JTI
    dim = 64
    bw = 10
    frame_period = dim * bw  # 640ps

    # Pairs near frame boundary
    t_a = np.asarray([630, 635, 640, 645], dtype=np.int64)  # near end of frame
    t_b = np.asarray([5, 10, 645, 650], dtype=np.int64)     # near start of next frame

    svd, meta = _compute_unwrapped_edge_guarded_jti(
        t_a, t_b,
        binwidth_ps=bw,
        dim=dim,
        origin_ps=0,
        guard_bins=2,
    )

    # Corners should be zero
    assert svd[0, dim - 1] == 0.0
    assert svd[dim - 1, 0] == 0.0


def test_compute_unwrapped_edge_guarded_jti_rejects_cross_frame() -> None:
    """Verify that cross-frame pairs are rejected."""
    dim = 32
    bw = 20
    frame_period = dim * bw  # 640ps

    # Pairs in same frame
    t_a_same = np.asarray([100, 200, 300], dtype=np.int64)
    t_b_same = np.asarray([105, 205, 305], dtype=np.int64)

    # Pairs across frames
    t_a_cross = np.asarray([630], dtype=np.int64)  # frame 0
    t_b_cross = np.asarray([650], dtype=np.int64)  # frame 1

    t_a = np.concatenate([t_a_same, t_a_cross])
    t_b = np.concatenate([t_b_same, t_b_cross])

    svd, meta = _compute_unwrapped_edge_guarded_jti(
        t_a, t_b,
        binwidth_ps=bw,
        dim=dim,
        origin_ps=0,
        guard_bins=0,  # no edge guard for this test
    )

    # Cross-frame pair should be rejected
    assert meta["rejected_cross_frame_pairs"] == 1
    assert meta["kept_pairs"] == 3


def test_compute_unwrapped_edge_guarded_jti_rejects_edge() -> None:
    """Verify that edge events are rejected by guard."""
    dim = 32
    bw = 20
    guard_bins = 2

    # Events near frame boundary (within guard zone)
    t_a = np.asarray([20, 100, 600], dtype=np.int64)  # 20ps is in guard zone (0-40ps)
    t_b = np.asarray([25, 105, 605], dtype=np.int64)

    svd, meta = _compute_unwrapped_edge_guarded_jti(
        t_a, t_b,
        binwidth_ps=bw,
        dim=dim,
        origin_ps=0,
        guard_bins=guard_bins,
    )

    # Event at 20ps should be rejected (guard zone is 0-40ps)
    assert meta["rejected_edge_pairs"] > 0


def test_compute_unwrapped_edge_guarded_jti_all_int64() -> None:
    """Verify that function works with large int64 timestamps."""
    dim = 128
    bw = 50

    # Large timestamps (17 digits)
    base = np.int64(36880089746026674)
    t_a = np.asarray([base, base + 100, base + 200], dtype=np.int64)
    t_b = np.asarray([base + 5, base + 105, base + 205], dtype=np.int64)

    svd, meta = _compute_unwrapped_edge_guarded_jti(
        t_a, t_b,
        binwidth_ps=bw,
        dim=dim,
        origin_ps=0,
        guard_bins=2,
    )

    # Should not crash and should produce valid output
    assert svd.shape == (dim, dim)
    assert meta["kept_pairs"] >= 0


# ---------------------------------------------------------------------------
# Diagnostics tests
# ---------------------------------------------------------------------------

def test_compute_diagnostics_offdiag_fraction() -> None:
    """Verify that offdiag_fraction is computed correctly."""
    # Create a simple matrix with known values
    counts = np.zeros((4, 4), dtype=np.float64)
    counts[0, 0] = 10  # main diagonal
    counts[1, 1] = 10
    counts[0, 1] = 5   # +1 diagonal (included in band_bins=1)
    counts[1, 0] = 5   # -1 diagonal (included in band_bins=1)

    diag = compute_jti_diagnostics(counts)

    # With band_bins=1, main + pm1 = 20 + 10 = 30, so offdiag = 0
    assert diag["diag_main_fraction"] == 20.0 / 30.0
    assert diag["offdiag_fraction"] == 0.0  # all counts are within band

    # Test with band_bins=0 (only main diagonal)
    diag0 = compute_jti_diagnostics(counts, band_bins=0)
    assert diag0["offdiag_fraction"] == 10.0 / 30.0


def test_compute_diagnostics_empty_matrix() -> None:
    """Verify diagnostics handle empty matrix correctly."""
    counts = np.zeros((4, 4), dtype=np.float64)

    diag = compute_jti_diagnostics(counts)

    assert diag["total_sum"] == 0.0
    assert diag["diag_main_fraction"] == 0.0
    assert diag["offdiag_fraction"] == 0.0
    assert diag["diag_contrast"] == 0.0


# ---------------------------------------------------------------------------
# CLI smoke tests
# ---------------------------------------------------------------------------

def test_extract_cli_help() -> None:
    """Verify CLI help can be accessed."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "jti_extract.cli.extract", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "JTI extraction with CV/DV/SVD unwrapped output" in result.stdout
    assert "--svd-unwrapped" in result.stdout
    assert "--guard-bins" in result.stdout


def test_extract_cli_svd_unwrapped_flag() -> None:
    """Verify --svd-unwrapped flag is accepted."""
    import subprocess
    import sys

    # Just verify the flag is parsed (will fail on missing ttbin, but that's OK)
    result = subprocess.run(
        [sys.executable, "-m", "jti_extract.cli.extract",
         "--ttbin", "nonexistent.ttbin",
         "--svd-unwrapped",
         "--out", "/tmp/test"],
        capture_output=True,
        text=True,
    )

    # Should fail with "ttbin not found", not with argument error
    assert "ttbin not found" in result.stderr or "ttbin not found" in result.stdout
