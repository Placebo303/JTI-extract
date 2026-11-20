"""Tests for the ttbin-only automatic delay calibration (auto tau)."""
from __future__ import annotations

import csv
import tempfile
from pathlib import Path

import numpy as np

from jti_extract.cli.raw_aligned import (
    _measure_residual_peak_ps,
    DEFAULT_TAU_COARSE_BIN_PS,
    DEFAULT_TAU_SEARCH_WINDOW_PS,
    DEFAULT_TAU_SMOOTH_PS,
    build_parser,
    delta_histogram,
    estimate_tau_align_from_tags,
    locate_histogram_peak,
    resolve_tau_align_ps,
)

_SYNTH_DIR = Path(__file__).resolve().parent


def _synthetic_tags(
    delay_ps: int = 1150,
    *,
    n_signal: int = 1500,
    n_a_bg: int = 2000,
    n_b_bg: int = 500,
    jitter_ps: float = 8.0,
    span_ps: int = 10_000_000,
    seed: int = 7,
) -> tuple[np.ndarray, np.ndarray]:
    """Two time-tag streams with a known coincidence delay plus flat accidentals."""
    rng = np.random.default_rng(seed)
    t_a = np.sort(rng.integers(0, span_ps, n_a_bg).astype(np.int64))
    t_b = np.sort(rng.integers(0, span_ps, n_b_bg).astype(np.int64))
    source = rng.choice(t_a, n_signal, replace=False)
    jitter = rng.normal(0.0, jitter_ps, n_signal).astype(np.int64)
    signal_b = np.sort(source + int(delay_ps) + jitter)
    return t_a, np.sort(np.concatenate([t_b, signal_b]))


def _write_peaks_csv(path: Path, rows: list[tuple[float, float]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["delay_ps", "counts"])
        writer.writeheader()
        for delay_ps, counts in rows:
            writer.writerow({"delay_ps": delay_ps, "counts": counts})
    return path


def test_delta_histogram_bins_known_delay() -> None:
    t_a = np.asarray([1000, 2000, 3000], dtype=np.int64)
    t_b = np.asarray([1100, 2100, 3100], dtype=np.int64)

    centers, counts = delta_histogram(t_a, t_b, half_window_ps=500, bin_ps=20)

    assert centers.size == counts.size == 51
    assert int(counts.sum()) == 3
    peak = int(np.argmax(counts))
    # Every pair sits at +100 ps, i.e. inside the bin centred on +100 ps.
    assert abs(centers[peak] - 100.0) <= 10.0


def test_delta_histogram_respects_center_offset() -> None:
    t_a = np.asarray([5000], dtype=np.int64)
    t_b = np.asarray([6000], dtype=np.int64)  # delta = +1000 ps

    centers, counts = delta_histogram(
        t_a, t_b, half_window_ps=100, bin_ps=10, center_ps=1000.0
    )

    assert int(counts.sum()) == 1
    assert abs(centers[int(np.argmax(counts))] - 1000.0) <= 5.0


def test_locate_histogram_peak_sub_bin_interpolation() -> None:
    centers = np.arange(-100.0, 100.0, 2.0) + 1.0
    counts = np.exp(-0.5 * ((centers - 12.7) / 6.0) ** 2) * 500.0

    peak = locate_histogram_peak(centers, counts.astype(np.int64), smooth_bins=5)

    assert peak is not None
    assert abs(peak["peak_ps"] - 12.7) <= 2.0
    assert peak["significance"] > 5.0
    assert peak["at_search_edge"] is False


def test_estimate_tau_align_recovers_known_delay() -> None:
    t_a, t_b = _synthetic_tags(delay_ps=1150)

    info = estimate_tau_align_from_tags(t_a, t_b)

    assert info["method"] == "auto_correlation"
    assert info["n_pairs"] > 0
    assert abs(info["tau_align_ps"] - 1150) <= 10
    assert abs(info["tau_align_ps_exact"] - 1150.0) <= 10.0
    assert info["coarse"]["significance"] > 5.0
    assert info["refine"]["significance"] > 5.0


def test_estimate_tau_align_recovers_negative_delay() -> None:
    t_a, t_b = _synthetic_tags(delay_ps=-830, seed=11)

    info = estimate_tau_align_from_tags(t_a, t_b)

    assert "refine" in info
    assert abs(info["tau_align_ps"] - (-830)) <= 10


def test_coarse_only_estimate_stays_within_one_smoothing_width() -> None:
    t_a, t_b = _synthetic_tags(delay_ps=-830, seed=11)

    info = estimate_tau_align_from_tags(t_a, t_b, refine=False)

    assert "refine" not in info
    # Without the centroid pass the boxcar plateau leaves up to half a kernel
    # width of ambiguity, so only that loose bound may be asserted.
    assert abs(info["tau_align_ps"] - (-830)) <= DEFAULT_TAU_SMOOTH_PS / 2 + DEFAULT_TAU_COARSE_BIN_PS


def test_estimate_tau_align_rejects_empty_pair_window() -> None:
    t_a = np.asarray([10_000], dtype=np.int64)
    t_b = np.asarray([50_000], dtype=np.int64)

    try:
        estimate_tau_align_from_tags(t_a, t_b, search_window_ps=10)
    except RuntimeError as exc:
        assert "no A-B pairs" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected RuntimeError for an empty pair window")


def test_parser_makes_peaks_csv_optional() -> None:
    parser = build_parser()

    args = parser.parse_args(["--ttbin", "data.1.ttbin", "--out", "results"])

    assert args.peaks_csv is None
    assert args.tau_auto is False
    assert args.tau_align_ps is None
    assert args.tau_search_window_ps == DEFAULT_TAU_SEARCH_WINDOW_PS
    assert args.tau_coarse_bin_ps == DEFAULT_TAU_COARSE_BIN_PS
    assert args.tau_smooth_ps == DEFAULT_TAU_SMOOTH_PS
    assert args.tau_refine is True
    assert args.auto_delay_range is False


def test_parser_accepts_no_tau_refine() -> None:
    parser = build_parser()

    args = parser.parse_args(
        ["--ttbin", "data.1.ttbin", "--out", "results", "--no-tau-refine", "--tau-auto"]
    )

    assert args.tau_refine is False
    assert args.tau_auto is True


def test_resolve_tau_prefers_explicit_value() -> None:
    t_a, t_b = _synthetic_tags(delay_ps=400)

    tau, source, info = resolve_tau_align_ps(
        t_a=t_a,
        t_b=t_b,
        explicit_tau_align_ps=-1234.0,
        peaks_csv=None,
        force_auto=True,
        auto_kwargs={},
    )

    assert tau == -1234.0
    assert source == "explicit"
    assert info is None


def test_resolve_tau_falls_back_to_correlation_when_peaks_csv_missing() -> None:
    t_a, t_b = _synthetic_tags(delay_ps=400)

    tau, source, info = resolve_tau_align_ps(
        t_a=t_a,
        t_b=t_b,
        explicit_tau_align_ps=None,
        peaks_csv=None,
        force_auto=False,
        auto_kwargs={},
    )

    assert source == "auto_correlation"
    assert info is not None
    assert abs(tau - 400) <= 10


def test_resolve_tau_uses_brightest_peak_of_peaks_csv() -> None:
    t_a, t_b = _synthetic_tags(delay_ps=400)
    with tempfile.TemporaryDirectory(dir=_SYNTH_DIR) as raw_dir:
        peaks_csv = _write_peaks_csv(
            Path(raw_dir) / "pminus_peaks.csv",
            [(-500.0, 10.0), (830.0, 99.0), (1200.0, 30.0)],
        )

        tau, source, info = resolve_tau_align_ps(
            t_a=t_a,
            t_b=t_b,
            explicit_tau_align_ps=None,
            peaks_csv=peaks_csv,
            force_auto=False,
            auto_kwargs={},
        )

    assert tau == 830.0
    assert source == "brightest_peak"
    assert info is None


def test_resolve_tau_force_auto_ignores_peaks_csv() -> None:
    t_a, t_b = _synthetic_tags(delay_ps=400)
    with tempfile.TemporaryDirectory(dir=_SYNTH_DIR) as raw_dir:
        peaks_csv = _write_peaks_csv(
            Path(raw_dir) / "pminus_peaks.csv", [(830.0, 99.0)]
        )

        tau, source, info = resolve_tau_align_ps(
            t_a=t_a,
            t_b=t_b,
            explicit_tau_align_ps=None,
            peaks_csv=peaks_csv,
            force_auto=True,
            auto_kwargs={},
        )

    assert source == "auto_correlation"
    assert info is not None
    assert abs(tau - 400) <= 10


def test_residual_probe_untrusted_for_tiny_sample() -> None:
    t_a = np.asarray([1_000_000, 2_000_000, 3_000_000], dtype=np.int64)
    t_b = np.sort(
        np.concatenate([t_a + 500, np.arange(0, 10_000_000, 3_000_000)]).astype(np.int64)
    )

    residual_ps, trusted, info = _measure_residual_peak_ps(
        t_a,
        t_b,
        -130.0,
        tau_auto=None,
        auto_kwargs={"search_window_ps": 25_000},
    )

    assert trusted is False
    assert info["n_pairs"] < 5_000
    assert np.isfinite(residual_ps)


def test_residual_probe_trusted_for_well_populated_sample() -> None:
    t_a, t_b = _synthetic_tags(delay_ps=400)

    residual_ps, trusted, info = _measure_residual_peak_ps(
        t_a,
        t_b,
        500.0,
        tau_auto=None,
        auto_kwargs={"search_window_ps": 25_000},
    )

    assert trusted is True
    assert info["n_pairs"] >= 5_000
    # The residual peak is the true delay minus the applied tau.
    assert abs(residual_ps - (-100.0)) <= 10.0


def test_estimator_reports_near_equal_clusters() -> None:
    rng = np.random.default_rng(23)
    span = 10_000_000
    t_a = np.sort(rng.integers(0, span, 4000).astype(np.int64))
    t_b = np.sort(rng.integers(0, span, 500).astype(np.int64))
    first = rng.choice(t_a, 800, replace=False)
    remaining = np.setdiff1d(t_a, first, assume_unique=True)
    second = rng.choice(remaining, 800, replace=False)
    signal = np.concatenate(
        [
            first + 400 + rng.normal(0.0, 8.0, 800).astype(np.int64),
            second + 2400 + rng.normal(0.0, 8.0, 800).astype(np.int64),
        ]
    )
    t_b = np.sort(np.concatenate([t_b, signal]))

    info = estimate_tau_align_from_tags(t_a, t_b, refine=False)

    assert info["coarse"]["n_near_equal"] >= 2
    candidate_positions = [c["peak_ps"] for c in info["coarse"]["near_equal_candidates"]]
    assert any(abs(pos - 400) <= 60 for pos in candidate_positions)
    assert any(abs(pos - 2400) <= 60 for pos in candidate_positions)
