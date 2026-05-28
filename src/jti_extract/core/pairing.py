"""Pairing helper exports used by regression tests."""

from __future__ import annotations

from jti_extract.cli.extract import (
    _RawTimetags,
    iter_pair_chunks_centered,
    compute_centered_line_jti,
    compute_multiline_raw_offset_jti,
    compute_alignment_centered_display_jti,
)
from jti_extract.cli.tdc_layer_scan import greedy_unique_pairs, nearest_pairs

__all__ = [
    "_RawTimetags",
    "iter_pair_chunks_centered",
    "compute_centered_line_jti",
    "compute_multiline_raw_offset_jti",
    "compute_alignment_centered_display_jti",
    "nearest_pairs",
    "greedy_unique_pairs",
]
