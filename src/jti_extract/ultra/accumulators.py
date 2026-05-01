"""Minimal accumulators for fixed-lattice G2-like JTI.

Supports:
- coarse JTI (rebin to *coarse_n_bins*)
- diagonal profile (perpendicular width |bin_a - bin_b|)
- diagonal-center profile (ridge localization via (bin_a + bin_b)//2)
- diagonal-center circular profile (wrap-aware ridge localization)
- row marginal
- column marginal
- summary counts: n_candidates_total, n_candidates_after_edge_guard, edge_rejection_ratio
"""

from typing import Dict, Tuple

import numpy as np

from jti_extract.ultra.fold_lattice import bin_indices, edge_guard_mask, frame_length_ps


class FixedLatticeAccumulator:
    """Accumulate G2-like JTI statistics on a fixed global frame lattice.

    Parameters
    ----------
    n_bins : int
        Number of bins (N) per frame dimension.
    bin_width_ps : int
        Bin width (ps).
    frame_origin_ps : float
        Global frame origin (ps).
    coincidence_window_ps : int
        Fixed physical coincidence window (ps).
    edge_guard_ps : int
        Edge-guard margin (ps).
    coarse_n_bins : int, optional
        Coarse JTI dimension for rebinning.  If not given or <= 0,
        no coarse JTI is accumulated.
    """

    def __init__(
        self,
        n_bins: int,
        bin_width_ps: int,
        frame_origin_ps: float,
        coincidence_window_ps: int,
        edge_guard_ps: int,
        coarse_n_bins: int = 0,
    ) -> None:
        self._n_bins = int(n_bins)
        self._bin_width_ps = int(bin_width_ps)
        self._frame_origin_ps = float(frame_origin_ps)
        self._fl_ps = frame_length_ps(n_bins, bin_width_ps)
        self._cw_ps = int(coincidence_window_ps)
        self._eg_ps = int(edge_guard_ps)
        self._coarse_n_bins = int(coarse_n_bins) if coarse_n_bins > 0 else 0

        # accumulators
        self._coarse_jti: np.ndarray | None = (
            np.zeros((self._coarse_n_bins, self._coarse_n_bins), dtype=np.float64)
            if self._coarse_n_bins
            else None
        )
        self._diag_profile: np.ndarray = np.zeros(int(n_bins), dtype=np.float64)
        self._row_marginal: np.ndarray = np.zeros(int(n_bins), dtype=np.float64)
        self._col_marginal: np.ndarray = np.zeros(int(n_bins), dtype=np.float64)
        self._n_candidates_total: int = 0
        self._n_candidates_after_edge_guard: int = 0
        self._n_edge_rejected: int = 0
        self._diag_center_profile: np.ndarray = np.zeros(int(n_bins), dtype=np.float64)
        self._diag_center_circular_profile: np.ndarray = np.zeros(int(n_bins), dtype=np.float64)

    # -- public read-only properties ---------------------------------------

    @property
    def n_candidates_total(self) -> int:
        return self._n_candidates_total

    @property
    def n_candidates_after_edge_guard(self) -> int:
        return self._n_candidates_after_edge_guard

    @property
    def edge_rejection_ratio(self) -> float:
        if self._n_candidates_total <= 0:
            return 0.0
        return float(self._n_edge_rejected) / float(self._n_candidates_total)

    @property
    def diag_profile(self) -> np.ndarray:
        return self._diag_profile.copy()

    @property
    def diag_center_profile(self) -> np.ndarray:
        return self._diag_center_profile.copy()

    @property
    def diag_center_circular_profile(self) -> np.ndarray:
        return self._diag_center_circular_profile.copy()

    @property
    def row_marginal(self) -> np.ndarray:
        return self._row_marginal.copy()

    @property
    def col_marginal(self) -> np.ndarray:
        return self._col_marginal.copy()

    @property
    def coarse_jti(self) -> np.ndarray | None:
        return None if self._coarse_jti is None else self._coarse_jti.copy()

    @staticmethod
    def _quantile_width(profile: np.ndarray, q_lo: float, q_hi: float) -> int:
        total = float(np.sum(profile))
        if total <= 0.0:
            return 0
        cdf = np.cumsum(np.asarray(profile, dtype=np.float64)) / total
        lo = int(np.searchsorted(cdf, q_lo, side="left"))
        hi = int(np.searchsorted(cdf, q_hi, side="left"))
        return max(0, hi - lo + 1)

    @staticmethod
    def _circular_mass_width(profile: np.ndarray, mass_fraction: float) -> int:
        """Find the shortest circular arc covering *mass_fraction* of total mass.

        Parameters
        ----------
        profile : np.ndarray
            1-D nonnegative profile on a circular domain of length N.
        mass_fraction : float
            Target cumulative mass fraction, e.g. 0.90 or 0.95.

        Returns
        -------
        int
            Width of the shortest circular arc (in bins) that contains at
            least *mass_fraction* of the total mass.  Returns 0 if the
            profile is empty.
        """
        total = float(np.sum(profile))
        if total <= 0.0:
            return 0
        N = len(profile)
        p = np.asarray(profile, dtype=np.float64)
        target = mass_fraction * total

        # Try every starting bin; for each, accumulate clockwise until
        # target mass is reached.  Track the minimum arc width.
        # Use cumulative sum on doubled array for O(N) sliding window.
        doubled = np.concatenate([p, p])
        cum = np.cumsum(doubled)
        best = N  # worst case: full circle
        for start in range(N):
            # mass from start to start+width (exclusive)
            # need cum[start+width] - cum[start] >= target
            # binary search for smallest width
            lo_w = 1
            hi_w = N
            while lo_w < hi_w:
                mid = (lo_w + hi_w) // 2
                if cum[start + mid] - cum[start] >= target:
                    hi_w = mid
                else:
                    lo_w = mid + 1
            if lo_w < best:
                best = lo_w
        return best

    # -- addition methods --------------------------------------------------

    def add_candidates(
        self,
        t_a: np.ndarray,
        t_b: np.ndarray,
    ) -> None:
        """Accumulate a batch of candidates (t_a, t_b in ps).

        t_a and t_b should be the raw timestamps of identified candidates.
        This method:
        1. validates that t_a and t_b have equal length;
        2. computes frame-local bin indices for t_a and t_b;
        3. applies edge-guard mask;
        4. updates accumulators.

        Raises
        ------
        ValueError
            If *t_a* and *t_b* have different lengths.
        """
        if t_a.shape != t_b.shape:
            raise ValueError(
                f"t_a and t_b must have the same shape; "
                f"got t_a.shape={t_a.shape}, t_b.shape={t_b.shape}"
            )
        n_cand = int(t_a.size)
        self._n_candidates_total += n_cand
        if n_cand == 0:
            return

        ba = bin_indices(t_a, self._frame_origin_ps, self._bin_width_ps, self._n_bins)
        bb = bin_indices(t_b, self._frame_origin_ps, self._bin_width_ps, self._n_bins)
        mask = edge_guard_mask(
            t_a, self._frame_origin_ps, self._fl_ps, self._eg_ps
        ) & edge_guard_mask(t_b, self._frame_origin_ps, self._fl_ps, self._eg_ps)

        n_kept = int(np.count_nonzero(mask))
        self._n_candidates_after_edge_guard += n_kept
        self._n_edge_rejected += n_cand - n_kept

        if n_kept == 0:
            return

        ba_kept = ba[mask]
        bb_kept = bb[mask]

        # marginal
        np.add.at(self._row_marginal, ba_kept, 1.0)
        np.add.at(self._col_marginal, bb_kept, 1.0)

        # diagonal profile: accumulate at |ba - bb|
        diag_idx = np.abs(np.asarray(ba_kept, dtype=np.int64) - np.asarray(bb_kept, dtype=np.int64))
        np.add.at(self._diag_profile, diag_idx, 1.0)

        # diagonal-center profile (ridge localization): accumulate at (ba+bb)//2
        center_idx = (
            (np.asarray(ba_kept, dtype=np.int64) + np.asarray(bb_kept, dtype=np.int64))
            // 2
        )
        center_idx = np.clip(center_idx, 0, self._n_bins - 1)
        np.add.at(self._diag_center_profile, center_idx, 1.0)

        # diagonal-center circular profile (wrap-aware ridge localization)
        # For pairs that cross frame boundary (ba≈0, bb≈N-1 or vice versa),
        # the linear center (ba+bb)//2 maps to N/2, which is wrong.
        # Circular center: use signed shortest displacement on the torus.
        # d = ((bb - ba + N//2) % N) - N//2  gives signed shortest path.
        # For even N, ties at exactly N/2 are resolved deterministically
        # by choosing the positive direction (d = +N//2).
        ba_i64 = np.asarray(ba_kept, dtype=np.int64)
        bb_i64 = np.asarray(bb_kept, dtype=np.int64)
        N = self._n_bins
        half_N = N // 2
        d = ((bb_i64 - ba_i64 + half_N) % N) - half_N  # signed shortest displacement
        # midpoint on the circle: ba + floor(d/2), then mod N
        circular_center = (ba_i64 + np.floor_divide(d, 2)) % N
        np.add.at(self._diag_center_circular_profile, circular_center, 1.0)

        # coarse JTI
        if self._coarse_jti is not None:
            cn = self._coarse_n_bins
            if cn < self._n_bins:
                ca = np.floor_divide(ba_kept, int(self._n_bins) // cn).astype(np.int64)
                cb = np.floor_divide(bb_kept, int(self._n_bins) // cn).astype(np.int64)
                ca = np.clip(ca, 0, cn - 1)
                cb = np.clip(cb, 0, cn - 1)
            else:
                ca = ba_kept.astype(np.int64, copy=False)
                cb = bb_kept.astype(np.int64, copy=False)
            np.add.at(self._coarse_jti, (ca, cb), 1.0)

    def summary(self) -> Dict[str, object]:
        """Return summary metrics dict."""
        peak_bin = int(np.argmax(self._diag_profile)) if np.sum(self._diag_profile) > 0 else -1

        # diag-center (ridge localization) summary
        center_sum = float(np.sum(self._diag_center_profile))
        center_peak_bin = int(np.argmax(self._diag_center_profile)) if center_sum > 0 else -1
        center_peak_time_ps: float = (
            self._frame_origin_ps + (float(center_peak_bin) + 0.5) * float(self._bin_width_ps)
            if center_sum > 0 else -1.0
        )

        # Cache center quantile widths to avoid redundant _quantile_width calls
        cw90_bins = self._quantile_width(self._diag_center_profile, 0.05, 0.95)
        cw95_bins = self._quantile_width(self._diag_center_profile, 0.025, 0.975)

        # diag-center circular (wrap-aware) summary
        circular_sum = float(np.sum(self._diag_center_circular_profile))
        circular_peak_bin = (
            int(np.argmax(self._diag_center_circular_profile))
            if circular_sum > 0 else -1
        )

        # Circular profile flatness diagnostics
        if circular_sum > 0 and self._n_bins > 0:
            circ_profile = np.asarray(self._diag_center_circular_profile, dtype=np.float64)
            circ_peak_val = float(np.max(circ_profile))
            circ_mean = circular_sum / float(self._n_bins)
            circ_std = float(np.std(circ_profile))
            circ_peak_to_mean = circ_peak_val / circ_mean if circ_mean > 0 else 0.0
            circ_cv = circ_std / circ_mean if circ_mean > 0 else 0.0

            # Shannon entropy in base 2
            p_norm = circ_profile / circular_sum
            p_nonzero = p_norm[p_norm > 0]
            circ_entropy = float(-np.sum(p_nonzero * np.log2(p_nonzero)))
        else:
            circ_peak_to_mean = 0.0
            circ_cv = 0.0
            circ_entropy = 0.0
        circular_peak_time_ps: float = (
            self._frame_origin_ps + (float(circular_peak_bin) + 0.5) * float(self._bin_width_ps)
            if circular_sum > 0 else -1.0
        )
        ccw90_bins = self._quantile_width(self._diag_center_circular_profile, 0.05, 0.95)
        ccw95_bins = self._quantile_width(self._diag_center_circular_profile, 0.025, 0.975)

        # circular minimal-arc width (torus-aware)
        cma90_bins = self._circular_mass_width(self._diag_center_circular_profile, 0.90)
        cma95_bins = self._circular_mass_width(self._diag_center_circular_profile, 0.95)

        # linear vs circular width ratio
        if ccw95_bins > 0:
            linear_vs_circular_ratio = float(cw95_bins) / float(ccw95_bins)
        else:
            linear_vs_circular_ratio = 0.0

        return {
            "n_bins": self._n_bins,
            "bin_width_ps": self._bin_width_ps,
            "frame_origin_ps": self._frame_origin_ps,
            "frame_length_ps": self._fl_ps,
            "coincidence_window_ps": self._cw_ps,
            "edge_guard_ps": self._eg_ps,
            "n_candidates_total": self._n_candidates_total,
            "n_candidates_after_edge_guard": self._n_candidates_after_edge_guard,
            "edge_rejection_ratio": self.edge_rejection_ratio,
            "diag_profile_sum": float(np.sum(self._diag_profile)),
            "diag_profile_peak_bin": peak_bin,
            "diag_profile_mass_width_90_bins": self._quantile_width(self._diag_profile, 0.05, 0.95),
            "diag_profile_mass_width_95_bins": self._quantile_width(self._diag_profile, 0.025, 0.975),
            "diag_profile_edge_fraction": (
                float(self._diag_profile[0] + self._diag_profile[-1]) / float(np.sum(self._diag_profile))
                if np.sum(self._diag_profile) > 0 else 0.0
            ),
            "diag_center_peak_bin": center_peak_bin,
            "diag_center_peak_time_ps": center_peak_time_ps,
            "diag_center_mass_width_90_bins": cw90_bins,
            "diag_center_mass_width_95_bins": cw95_bins,
            "diag_center_mass_width_90_ps": cw90_bins * self._bin_width_ps,
            "diag_center_mass_width_95_ps": cw95_bins * self._bin_width_ps,
            "diag_center_edge_fraction": (
                float(self._diag_center_profile[0] + self._diag_center_profile[-1]) / center_sum
                if center_sum > 0 else 0.0
            ),
            # circular-center (wrap-aware) fields
            "diag_center_circular_peak_bin": circular_peak_bin,
            "diag_center_circular_peak_time_ps": circular_peak_time_ps,
            "diag_center_circular_mass_width_90_bins": ccw90_bins,
            "diag_center_circular_mass_width_95_bins": ccw95_bins,
            "diag_center_circular_mass_width_90_ps": ccw90_bins * self._bin_width_ps,
            "diag_center_circular_mass_width_95_ps": ccw95_bins * self._bin_width_ps,
            "diag_center_circular_edge_fraction": (
                float(
                    self._diag_center_circular_profile[0]
                    + self._diag_center_circular_profile[self._n_bins - 1]
                ) / circular_sum
                if circular_sum > 0 else 0.0
            ),
            "diag_center_linear_vs_circular_width_ratio": linear_vs_circular_ratio,
            # Circular profile flatness diagnostics
            "diag_center_circular_peak_to_mean": circ_peak_to_mean,
            "diag_center_circular_cv": circ_cv,
            "diag_center_circular_entropy_log2": circ_entropy,
            # circular minimal-arc width (torus-aware)
            "diag_center_circular_min_arc_width_90_bins": cma90_bins,
            "diag_center_circular_min_arc_width_95_bins": cma95_bins,
            "diag_center_circular_min_arc_width_90_ps": cma90_bins * self._bin_width_ps,
            "diag_center_circular_min_arc_width_95_ps": cma95_bins * self._bin_width_ps,
            "row_marginal_sum": float(np.sum(self._row_marginal)),
            "col_marginal_sum": float(np.sum(self._col_marginal)),
        }

    def check_internal_consistency(self) -> bool:
        """Check that all accumulator totals match n_candidates_after_edge_guard."""
        s_diag = float(np.sum(self._diag_profile))
        s_center = float(np.sum(self._diag_center_profile))
        s_circular = float(np.sum(self._diag_center_circular_profile))
        s_row = float(np.sum(self._row_marginal))
        s_col = float(np.sum(self._col_marginal))
        target = float(self._n_candidates_after_edge_guard)
        if not np.isclose(s_diag, target):
            return False
        if not np.isclose(s_center, target):
            return False
        if not np.isclose(s_circular, target):
            return False
        if not np.isclose(s_row, target):
            return False
        if not np.isclose(s_col, target):
            return False
        if self._coarse_jti is not None:
            s_coarse = float(np.sum(self._coarse_jti))
            if not np.isclose(s_coarse, target):
                return False
        return True
