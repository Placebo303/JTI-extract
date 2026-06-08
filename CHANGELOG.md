# Changelog

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
