# Changelog

## v0.1.0 - JTI-stage Schmidt-like Analysis Stable Version

### Added
- Single-line JTI Schmidt-like analysis (Mode A) via `extract_jti.py`.
- BFC/FPC peak-aware greedy-unique multi-line JTI analysis (Mode B) via `compute_fpc_schmidt.py`.
- True-coordinate unwrapped edge-guarded non-cyclic JTI construction.
- `--pair-center-ps` and `--tau-align-ps` parameters for proper tau coordinate handling.
- `--window-ps` direct parameter (overrides `k * binwidth_ps`).
- `K_global_comb_raw`, `K_comb_weight`, `K_tooth_m`, `K_full_window_greedy_unique_raw` metrics.
- `K_tooth_weighted_mean` (count-weighted mean of per-tooth K values).
- Singular value CSV outputs for H_comb and H_full_window.
- Standalone `pairing_diagnostics.json` output.
- `summary.csv` top-level result summary.
- Residual tau diagnostics (weighted mean, std, min, max).
- `analysis_stage`, `future_stage`, `interpretation` meta fields.
- Sensitivity analysis across multiple prominence thresholds.

### Fixed
- Removed 6 instances of `np.clip` on bin indices in `extract.py`; replaced with bounds check + reject + `invalid_count`.
- Fixed float64 precision-sensitive binning in `tdc_layer_scan.py` and `run_fpc_multiline_analysis.py`.
- Fixed tau alignment vs pair center separation (previously conflated under `tau0_ps`).
- Fixed H_full_window construction: now uses comb + gap extension (`accepted_comb + accepted_gap`), not independent greedy.
- Fixed NaN propagation in `K_tooth_weighted_mean` when some teeth have zero counts.
- Fixed broken imports in `core/binning.py` and `core/pairing.py`.

### Notes
- All K values are `background-unsubtracted, intensity-based Schmidt-like effective mode numbers` using `A = sqrt(normalized intensity)`.
- Current version is JTI-stage temporal-domain characterization only.
- JSI-stage frequency-domain characterization will be added in a future version.
- This is NOT a full BFC time-frequency Schmidt decomposition.
