# Changelog

## [0.3.1] - 2026-11-20

### Added
- Automatic delay calibration from the `.ttbin` time tags themselves:
  ``Δt = t_B - t_A`` pair histogram inside a search window (= windowed A/B
  cross-correlation), 20 ps coarse bins with 300 ps boxcar smoothing, coarse
  peak located with plateau-centre / parabolic interpolation, then a 2 ps
  centroid refinement inside +/-300 ps. Emits `tau_auto` diagnostics
  (peak position, significance, search-edge flag) into `raw_aligned_meta.json`.
- `--tau-auto`, `--tau-search-window-ps`, `--tau-coarse-bin-ps`,
  `--tau-smooth-ps`, `--tau-refine/--no-tau-refine`,
  `--tau-refine-window-ps`, `--tau-refine-bin-ps`.
- `--auto-delay-range`: centre the residual-delay window on the measured
  residual peak instead of 0 ps (`delay_window_center_ps` in metadata).
- Reliability diagnostics for the automatic delay: near-equal correlation
  cluster catalogue (`tau_auto.coarse.near_equal_candidates` /
  `n_near_equal`), a WARNING when fewer than `TAU_AUTO_MIN_TRUSTED_PAIRS`
  (5000) A-B pairs fall inside the search window, and a trust guard that keeps
  `--auto-delay-range` centred on 0 ps when the measured residual peak is weak.
- `tests/test_auto_tau.py`: 16 unit tests for the correlation estimator, peak
  locator, tau resolution priority, cluster ambiguity and the untrusted-residual
  fallback.

### Changed
- `--peaks-csv` is now optional. tau_align_ps resolution order is
  explicit `--tau-align-ps` > ttbin correlation (`--tau-auto` or no peaks
  CSV) > peaks-CSV brightest peak.
- Clearer channel-selection error: lists the channels actually present in the
  .ttbin instead of the generic "No events found" message.
- `tau_align_ps` is now rounded (not truncated) before being applied.
- Version is defined once in `src/jti_extract/_version.py` and exposed through
  the package `__init__` (previously pyproject said 0.3.0 while the package
  said 0.1.0).

### Fixed
- `raw_aligned_meta.json` is now written **after** the optional SVD/K step, so
  `K_raw_aligned`, `purity`, `singular_values`, `lambda_weights` and
  `lambda1`/`lambda2`/`lambda3`/`lambda5_cumsum`/`lambda10_cumsum` really
  appear in the metadata when `--compute-svd` is used (previously only in
  `summary.csv`).
- `summary.csv` now records `tau_align_ps` and `tau_align_source`.
- peaks CSV whose brightest peak is at exactly 0 ps no longer raises
  "Cannot determine tau_align_ps".
- `archived/diagnostics/analyze_interchannel_delay.py` computes its repo root
  correctly (`parents[2]`) so it can run standalone from this checkout.

## [0.3.0] - 2026-06-08

### Added
- `src/jti_extract/cli/raw_aligned.py`: Raw-aligned FPC JTI extraction mode
  - Global residual-delay window pairing (no per-tooth ROI)
  - Chunk-streamed memory-efficient pairing
  - SVD/K computation with `--compute-svd`
  - Diagonal diagnostics and count balance verification
  - `count_balance_error`, `delay_span_exceeds_frame_period` in metadata
- `scripts/run_raw_aligned_scan.py`: Batch parameter scan (binwidth × N)
- Entry point: `jti-raw-aligned`

### Archived
- Mode A (`extract_jti.py`, `compute_jti_schmidt.py`, etc.) → `archived/mode_a/`
- Mode B (`compute_fpc_schmidt.py`, `run_fpc_multiline_analysis.py`) → `archived/mode_b/`
- Diagnostic tools (`analyze_*.py`, `jti_delay_alignment.py`) → `archived/diagnostics/`
- Batch runners (`run_bfc_*.py`, `run_pseudo_*.py`) → `archived/batch_runners/`

### Changed
- Primary extraction mode is now raw-aligned FPC JTI
- All documentation updated for raw-aligned mode
- Removed legacy CLI entry points (jti-extract, jti-schmidt, jti-tdc-residue, jti-tdc-layer-scan)
- Version bumped to 0.3.0

## [0.2.0] - 2026-05-26

### Added
- Mode B: BFC/FPC multi-line Schmidt analysis
- Pseudo-CV batch processing
- TDC layer scan diagnostics

## [0.1.0] - 2026-04-10

### Added
- Mode A: Single-line JTI extraction (CV/DV/SVD)
- Frame origin scanning
- Schmidt number computation
