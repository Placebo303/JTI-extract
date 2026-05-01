"""Tests for jti_extract.ultra.svd_estimators.

Verifies:
1. svd_coarse_jti: rejects negatives, returns plausible metrics,
   matches expected values for known matrices.
2. singular_spectrum: returns valid weight array.
3. captured_frobenius_energy: correct for full rank, r=0, monotonic.
4. truncated_schmidt_summary: n_singular_values <= r, matches full
   when r >= full rank.
5. block_bootstrap_coarse_jti: returns correct-length list (prototype).
"""

import numpy as np
import pytest

from jti_extract.ultra.svd_estimators import (
    block_bootstrap_coarse_jti,
    captured_frobenius_energy,
    singular_spectrum,
    svd_coarse_jti,
    truncated_schmidt_summary,
)


# ---------------------------------------------------------------------------
#  svd_coarse_jti
# ---------------------------------------------------------------------------

class TestSvdCoarseJti:
    def test_rejects_negative_matrix(self) -> None:
        mat = np.array([[1.0, -2.0], [3.0, 4.0]])
        with pytest.raises(ValueError, match="negative"):
            svd_coarse_jti(mat)

    def test_small_diagonal_matrix(self) -> None:
        """A 4x4 diagonal matrix with different weights."""
        mat = np.diag(np.array([4.0, 3.0, 2.0, 1.0]))
        result = svd_coarse_jti(mat)
        assert result["schmidt_number"] >= 1.0
        assert result["purity"] <= 1.0
        assert result["largest_weight"] <= 1.0
        assert result["negative_bins"] == 0.0
        assert result["nonzero_bins"] == 4.0

    def test_identity_matrix(self) -> None:
        """Identity is close to full-rank uniform."""
        n = 8
        mat = np.eye(n, dtype=np.float64)
        result = svd_coarse_jti(mat)
        # For identity, all singular values of sqrt(p) are equal,
        # so schmidt_number ≈ n
        assert result["schmidt_number"] >= n * 0.9
        assert result["schmidt_number"] <= n * 1.1

    def test_rank1_matrix(self) -> None:
        """Rank-1 matrix should give schmidt_number ≈ 1."""
        mat = np.ones((4, 4), dtype=np.float64)
        result = svd_coarse_jti(mat)
        assert result["schmidt_number"] <= 1.1
        assert result["schmidt_number"] >= 0.9

    def test_zero_total_raises(self) -> None:
        mat = np.zeros((4, 4), dtype=np.float64)
        with pytest.raises(ValueError, match="total sum must be positive"):
            svd_coarse_jti(mat)

    def test_normalized_sum_is_one(self) -> None:
        mat = np.array([[3.0, 1.0], [1.0, 3.0]])
        result = svd_coarse_jti(mat)
        assert np.isclose(result["normalized_sum"], 1.0)

    def test_threshold_filtering(self) -> None:
        """High threshold reduces n_singular_values."""
        mat = np.eye(16, dtype=np.float64)
        r1 = svd_coarse_jti(mat, threshold=1e-12)
        r2 = svd_coarse_jti(mat, threshold=0.1)
        assert r2["n_singular_values"] <= r1["n_singular_values"]

    def test_key_set(self) -> None:
        mat = np.array([[1.0, 0.0], [0.0, 1.0]])
        result = svd_coarse_jti(mat)
        expected_keys = {
            "schmidt_number", "purity", "largest_weight",
            "n_singular_values", "singular_value_threshold",
            "total_counts", "normalized_sum", "nonzero_bins",
            "negative_bins",
        }
        assert set(result.keys()) == expected_keys, (
            f"key mismatch: got {set(result.keys())}"
        )


# ---------------------------------------------------------------------------
#  singular_spectrum
# ---------------------------------------------------------------------------

class TestSingularSpectrum:
    def test_weights_sum_to_one(self) -> None:
        mat = np.array([[3.0, 1.0], [1.0, 3.0]])
        w = singular_spectrum(mat)
        assert np.isclose(np.sum(w), 1.0)

    def test_rejects_negative(self) -> None:
        with pytest.raises(ValueError, match="negative"):
            singular_spectrum(np.array([[-1.0, 0.0], [0.0, 1.0]]))

    def test_high_threshold_rejects_empty_spectrum(self) -> None:
        """High threshold should raise when no singular values remain."""
        mat = np.eye(4, dtype=np.float64)
        with pytest.raises(ValueError, match="no singular values above threshold"):
            singular_spectrum(mat, threshold=0.99)


# ---------------------------------------------------------------------------
#  captured_frobenius_energy
# ---------------------------------------------------------------------------

class TestCapturedFrobeniusEnergy:
    def test_full_rank_gives_one(self) -> None:
        sv = np.array([3.0, 2.0, 1.0])
        e = captured_frobenius_energy(sv, len(sv))
        assert np.isclose(e, 1.0)

    def test_r_zero(self) -> None:
        sv = np.array([3.0, 2.0, 1.0])
        e = captured_frobenius_energy(sv, 0)
        assert np.isclose(e, 0.0)

    def test_monotonic(self) -> None:
        sv = np.array([5.0, 3.0, 2.0, 1.0, 0.5])
        energies = [captured_frobenius_energy(sv, r) for r in range(1, len(sv) + 1)]
        for i in range(1, len(energies)):
            assert energies[i] >= energies[i - 1] - 1e-12, (
                f"not monotonic at r={i+1}: {energies[i]} < {energies[i-1]}"
            )

    def test_known_spectrum(self) -> None:
        """Known weights [0.7, 0.2, 0.1] give captured ~0.9 at r=2."""
        sv = np.sqrt(np.array([0.7, 0.2, 0.1]))  # sv = sqrt(weight)
        e = captured_frobenius_energy(sv, 2)
        expected = (0.7 + 0.2) / (0.7 + 0.2 + 0.1)
        assert np.isclose(e, expected, atol=1e-12)


# ---------------------------------------------------------------------------
#  truncated_schmidt_summary
# ---------------------------------------------------------------------------

class TestTruncatedSchmidtSummary:
    def test_truncation_reduces_n_singular_values(self) -> None:
        mat = np.eye(16, dtype=np.float64)
        result = truncated_schmidt_summary(mat, r=4)
        assert result["n_singular_values"] <= 4.0

    def test_full_rank_matches_svd_coarse_jti(self) -> None:
        mat = np.array([[2.0, 0.5], [0.5, 2.0]])
        full = svd_coarse_jti(mat)
        truncated = truncated_schmidt_summary(mat, r=16)
        assert np.isclose(
            truncated["schmidt_number"], full["schmidt_number"],
            atol=1e-10
        )
        assert truncated["captured_frobenius_energy_r"] == pytest.approx(1.0)

    def test_extra_keys_present(self) -> None:
        mat = np.array([[1.0, 0.0], [0.0, 1.0]])
        result = truncated_schmidt_summary(mat, r=2)
        assert "r_truncated" in result
        assert "captured_frobenius_energy_r" in result
        assert "K_truncated_r" in result


# ---------------------------------------------------------------------------
#  block_bootstrap_coarse_jti (prototype)
# ---------------------------------------------------------------------------

class TestBlockBootstrapCoarseJti:
    @pytest.mark.prototype
    def test_returns_correct_length(self) -> None:
        """Simple smoke test: returns n_resamples items with expected keys."""
        t_a = np.array([100, 200, 300], dtype=np.int64)
        t_b = np.array([150, 250, 350], dtype=np.int64)
        results = block_bootstrap_coarse_jti(
            candidates_t_a=t_a,
            candidates_t_b=t_b,
            n_bins=4,
            bin_width_ps=100,
            frame_origin_ps=0.0,
            coincidence_window_ps=200,
            edge_guard_ps=0,
            coarse_n_bins=2,
            n_resamples=5,
            seed=42,
        )
        assert len(results) == 5, f"expected 5 results, got {len(results)}"
        if results:
            keys = {"schmidt_number", "purity", "largest_weight",
                    "n_singular_values", "singular_value_threshold"}
            for r in results:
                assert keys.issubset(set(r.keys())), f"missing keys in {r}"

    def test_empty_candidates(self) -> None:
        """Empty candidate arrays should return empty list."""
        results = block_bootstrap_coarse_jti(
            np.array([], dtype=np.int64),
            np.array([], dtype=np.int64),
            n_bins=4, bin_width_ps=100, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=0,
            coarse_n_bins=2, n_resamples=3,
        )
        assert results == []
