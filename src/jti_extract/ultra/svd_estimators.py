"""SVD-based effective-mode estimators for ultra JTI sweep.

All functions are pure NumPy library functions:
- consume nonnegative coarse JTI matrices (from FixedLatticeAccumulator.coarse_jti)
- or candidate timestamp arrays (from all_candidates())
- do NOT read .ttbin files
- do NOT write output files
- do NOT depend on baseline jti-extract or jti-schmidt modules
"""

from typing import Dict, List, Optional

import numpy as np


# ---------------------------------------------------------------------------
#  Exact coarse SVD
# ---------------------------------------------------------------------------


def svd_coarse_jti(
    coarse_jti: np.ndarray,
    threshold: float = 1e-12,
) -> Dict[str, float]:
    """Schmidt decomposition of a nonnegative coarse JTI matrix.

    Replicates the logic of ``compute_schmidt_number_from_jti()``
    (``sqrt(probability)`` + full SVD) but operates on an in-memory
    NumPy array rather than a CSV file.

    Parameters
    ----------
    coarse_jti : np.ndarray
        2-D nonnegative counts matrix.
    threshold : float
        Singular values below this threshold are discarded.

    Returns
    -------
    dict
        ``schmidt_number``, ``purity``, ``largest_weight``,
        ``n_singular_values``, ``singular_value_threshold``,
        ``total_counts``, ``normalized_sum``, ``nonzero_bins``,
        ``negative_bins``.

    Raises
    ------
    ValueError
        If the matrix contains negative values or its total sum is
        not positive.
    """
    mat = np.asarray(coarse_jti, dtype=np.float64)
    if mat.ndim != 2:
        raise ValueError("coarse JTI must be a 2D matrix")

    negative_bins = int(np.count_nonzero(mat < 0))
    if negative_bins:
        raise ValueError(
            f"JTI contains {negative_bins} negative values"
        )

    total = float(np.sum(mat))
    if not np.isfinite(total) or total <= 0.0:
        raise ValueError("JTI total sum must be positive")

    nonzero_bins = int(np.count_nonzero(mat > 0))

    probability = mat / total
    normalized_sum = float(np.sum(probability))

    jta = np.sqrt(probability)
    singular_vals = np.linalg.svd(jta, compute_uv=False)

    singular_vals = singular_vals[singular_vals > float(threshold)]
    if singular_vals.size == 0:
        raise ValueError("no singular values above threshold")

    weights = singular_vals**2
    weights = weights / np.sum(weights)
    purity = float(np.sum(weights**2))
    schmidt_number = float(1.0 / purity)

    return {
        "schmidt_number": schmidt_number,
        "purity": purity,
        "largest_weight": float(np.max(weights)),
        "n_singular_values": float(singular_vals.size),
        "singular_value_threshold": float(threshold),
        "total_counts": total,
        "normalized_sum": normalized_sum,
        "nonzero_bins": float(nonzero_bins),
        "negative_bins": float(negative_bins),
    }


# ---------------------------------------------------------------------------
#  Singular spectrum (full squared weights)
# ---------------------------------------------------------------------------


def singular_spectrum(
    coarse_jti: np.ndarray,
    threshold: float = 1e-12,
) -> np.ndarray:
    """Return the full squared-weight singular spectrum.

    The weights are normalized so that they sum to 1.

    Raises
    ------
    ValueError
        If the matrix contains negative values, its total sum is not
        positive, or no singular values remain above *threshold*.
    """
    mat = np.asarray(coarse_jti, dtype=np.float64)
    if mat.ndim != 2:
        raise ValueError("coarse JTI must be a 2D matrix")
    if np.any(mat < 0):
        raise ValueError("coarse JTI contains negative values")
    total = float(np.sum(mat))
    if total <= 0.0:
        raise ValueError("JTI total sum must be positive")
    probability = mat / total
    jta = np.sqrt(probability)
    singular_vals = np.linalg.svd(jta, compute_uv=False)
    singular_vals = singular_vals[singular_vals > float(threshold)]
    if singular_vals.size == 0:
        raise ValueError("no singular values above threshold")
    weights = singular_vals**2
    return weights / np.sum(weights)


# ---------------------------------------------------------------------------
#  Captured Frobenius energy
# ---------------------------------------------------------------------------


def captured_frobenius_energy(
    singular_vals: np.ndarray,
    r: int,
) -> float:
    """Fraction of Frobenius energy captured by the top-r singular values.

    Parameters
    ----------
    singular_vals : np.ndarray
        1-D array of singular values (not squared weights).
    r : int
        Truncation rank.  0 returns 0.0; len(singular_vals) returns 1.0.

    Returns
    -------
    float
        Energy fraction in [0, 1].
    """
    sv = np.asarray(singular_vals, dtype=np.float64)
    total_energy = float(np.sum(sv**2))
    if total_energy <= 0.0:
        return 0.0
    r_clamped = int(max(0, min(r, sv.size)))
    if r_clamped <= 0:
        return 0.0
    captured = float(np.sum(sv[:r_clamped]**2))
    return captured / total_energy


# ---------------------------------------------------------------------------
#  Truncated Schmidt summary
# ---------------------------------------------------------------------------


def truncated_schmidt_summary(
    coarse_jti: np.ndarray,
    r: int,
    threshold: float = 1e-12,
) -> Dict[str, float]:
    """Schmidt metrics using only the top-r singular values.

    Returns the same fields as ``svd_coarse_jti()`` plus
    ``r_truncated``, ``captured_frobenius_energy_r``, and
    ``K_truncated_r``.

    Parameters
    ----------
    coarse_jti : np.ndarray
        2-D nonnegative counts matrix.
    r : int
        Desired truncation rank.
    threshold : float
        Singular value threshold.

    Returns
    -------
    dict
    """
    mat = np.asarray(coarse_jti, dtype=np.float64)
    if mat.ndim != 2:
        raise ValueError("coarse JTI must be a 2D matrix")
    negative_bins = int(np.count_nonzero(mat < 0))
    if negative_bins:
        raise ValueError(
            f"JTI contains {negative_bins} negative values"
        )
    total = float(np.sum(mat))
    if not np.isfinite(total) or total <= 0.0:
        raise ValueError("JTI total sum must be positive")
    nonzero_bins = int(np.count_nonzero(mat > 0))
    probability = mat / total
    normalized_sum = float(np.sum(probability))
    jta = np.sqrt(probability)
    singular_vals = np.linalg.svd(jta, compute_uv=False)

    # Threshold then truncate
    singular_vals = singular_vals[singular_vals > float(threshold)]
    r_actual = min(int(r), int(singular_vals.size))
    if r_actual <= 0:
        raise ValueError("no singular values above threshold after truncation")

    sv_trunc = singular_vals[:r_actual]
    captured_energy = captured_frobenius_energy(singular_vals, r_actual)

    weights = sv_trunc**2
    weights = weights / np.sum(weights)
    purity = float(np.sum(weights**2))
    schmidt_number = float(1.0 / purity)

    full_weights = singular_vals**2
    full_weights = full_weights / np.sum(full_weights)

    return {
        "schmidt_number": schmidt_number,
        "purity": purity,
        "largest_weight": float(np.max(weights)),
        "n_singular_values": float(r_actual),
        "singular_value_threshold": float(threshold),
        "total_counts": total,
        "normalized_sum": normalized_sum,
        "nonzero_bins": float(nonzero_bins),
        "negative_bins": float(negative_bins),
        "r_truncated": float(r_actual),
        "captured_frobenius_energy_r": captured_energy,
        "K_truncated_r": schmidt_number,
    }


# ---------------------------------------------------------------------------
#  Block bootstrap prototype
# ---------------------------------------------------------------------------


def block_bootstrap_coarse_jti(
    candidates_t_a: np.ndarray,
    candidates_t_b: np.ndarray,
    n_bins: int,
    bin_width_ps: int,
    frame_origin_ps: float,
    coincidence_window_ps: int,
    edge_guard_ps: int,
    coarse_n_bins: int,
    n_resamples: int = 100,
    block_size: Optional[int] = None,
    seed: Optional[int] = None,
) -> List[Dict[str, float]]:
    """Block bootstrap resampling of coarse JTI Schmidt metrics.

    This is a **prototype-level** implementation suitable only for tiny
    synthetic validation.  It uses a simple row-wise resampling of
    candidates (each candidate is treated as an i.i.d. sample), which
    is *not* a proper block bootstrap but serves as a placeholder.

    Parameters
    ----------
    candidates_t_a : np.ndarray
        1-D array of channel A candidate timestamps (ps).
    candidates_t_b : np.ndarray
        1-D array of channel B candidate timestamps (ps).
    n_bins, bin_width_ps, frame_origin_ps : int, int, float
        Frame lattice parameters.
    coincidence_window_ps : int
        Fixed physical coincidence window (ps).
    edge_guard_ps : int
        Edge-guard margin (ps).
    coarse_n_bins : int
        Coarse JTI dimension.
    n_resamples : int
        Number of bootstrap resamples (default 100).
    block_size : int or None
        Ignored in this prototype (resamples individual candidates).
    seed : int or None
        Random seed for reproducibility.

    Returns
    -------
    list of dict
        Each dict is the output of ``svd_coarse_jti()`` for one resample.
        Length equals *n_resamples*.
    """
    rng = np.random.default_rng(seed)
    n_candidates = int(candidates_t_a.size)
    if n_candidates == 0:
        return []

    from jti_extract.ultra.accumulators import FixedLatticeAccumulator

    results: List[Dict[str, float]] = []
    for _ in range(int(n_resamples)):
        idx = rng.integers(0, n_candidates, size=n_candidates)
        ba = candidates_t_a[idx]
        bb = candidates_t_b[idx]

        acc = FixedLatticeAccumulator(
            n_bins=n_bins,
            bin_width_ps=bin_width_ps,
            frame_origin_ps=frame_origin_ps,
            coincidence_window_ps=coincidence_window_ps,
            edge_guard_ps=edge_guard_ps,
            coarse_n_bins=coarse_n_bins,
        )
        acc.add_candidates(ba, bb)
        cjti = acc.coarse_jti
        if cjti is None or np.sum(cjti) <= 0:
            continue
        try:
            meta = svd_coarse_jti(cjti)
            results.append(meta)
        except ValueError:
            continue

    return results
