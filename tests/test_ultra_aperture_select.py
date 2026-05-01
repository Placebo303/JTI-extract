"""Tests for aperture_select module (Stage 21)."""

import numpy as np
import pytest

from jti_extract.ultra.aperture_select import select_apertures


def _make_contrast_profile(segments):
    return {"segments": segments}


def test_select_apertures_empty():
    apertures = select_apertures({"segments": []}, threshold="snr3")
    assert apertures == []


def _seg(idx, snr, cr, sb_zero=False, on=10, sb=1):
    return {
        "segment_idx": idx,
        "segment_start_ps": float(idx) * 1000.0,
        "segment_stop_ps": float(idx + 1) * 1000.0,
        "snr": snr,
        "contrast_ratio": cr,
        "sideband_zero": sb_zero,
        "on_diag_counts": on,
        "sideband_counts": sb,
        "bg_scaled_counts": float(sb) * 0.2,
    }


def test_select_apertures_no_pass():
    segments = [_seg(i, 1.0, 1.0) for i in range(10)]
    apertures = select_apertures(_make_contrast_profile(segments), threshold="snr3")
    assert apertures == []


def test_select_apertures_snr3():
    segments = [_seg(i, 4.0, 10.0) for i in range(5)]
    apertures = select_apertures(_make_contrast_profile(segments), threshold="snr3", min_run_segments=3)
    assert len(apertures) == 1
    assert apertures[0]["n_segments"] == 5
    assert apertures[0]["mean_snr"] == 4.0


def test_select_apertures_contrast2_with_none():
    # segment 0 has contrast_ratio=None (sideband_zero), so it fails contrast2 threshold
    # segments 1-3 pass, forming an aperture of 3 segments
    segments = [
        _seg(0, 4.0, None, sb_zero=True),
        _seg(1, 4.0, 10.0),
        _seg(2, 4.0, 10.0),
        _seg(3, 4.0, 10.0),
    ]
    apertures = select_apertures(_make_contrast_profile(segments), threshold="contrast2", min_run_segments=3)
    assert len(apertures) == 1
    # The aperture includes segments 1-3, none of which have sideband_zero
    assert apertures[0]["n_sideband_zero_segments"] == 0
    assert apertures[0]["n_segments"] == 3


def test_select_apertures_gap_merge():
    segments = [
        _seg(0, 4.0, 10.0),
        _seg(1, 4.0, 10.0),
        _seg(2, 1.0, 1.0),  # gap
        _seg(3, 4.0, 10.0),
        _seg(4, 4.0, 10.0),
    ]
    apertures = select_apertures(
        _make_contrast_profile(segments), threshold="snr3",
        min_run_segments=3, max_gap_segments=1
    )
    assert len(apertures) == 1
    assert apertures[0]["n_segments"] == 5
