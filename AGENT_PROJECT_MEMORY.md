# AGENT_PROJECT_MEMORY.md

## 1. Project Identity

- Project name: `jti-extract` [repo-observed]
- Research purpose: Reproducible extraction and analysis of joint time-bin / joint temporal intensity data from time-tag records, including TDC residue diagnostics and Schmidt-number analysis. [repo-observed]
- Main scientific/engineering objective: Build and validate workflows that convert TimeTagger or parsed time-bin data into JTI count matrices, diagnostic summaries, Schmidt-number summaries, and direct Type0ppln `P_plus` support profiles. [repo-observed]
- Current maturity: Research tooling / pilot-analysis codebase with package layout, CLI entrypoints, tests, documentation, and several generated-result directories. The worktree observed during this handoff is dirty and contains many pre-existing changes/deletions. [repo-observed]

## 2. Repository Structure Observed

- `src/jti_extract/` - installable Python package root. [repo-observed]
- `src/jti_extract/cli/` - CLI implementations:
  - `extract.py` - JTI extraction CLI with CV/DV/SVD unwrapped output. [updated 2026-05-27]
  - `schmidt.py` - Schmidt-number analysis CLI. [repo-observed]
  - `tdc_layer_scan.py` - offline TimeTagger layer/residue diagnostics. [repo-observed]
  - `tdc_residue.py` - TimeTagger fine-time residue diagnostics. [repo-observed]
- `src/jti_extract/core/` - core logic modules:
  - `binning.py`, `diagnostics.py`, `pairing.py`, `residue.py`, `schmidt.py`. [repo-observed]
- `src/jti_extract/io/` - CSV, JSON, NPZ, path, and ttbin IO helpers. [repo-observed]
- `src/jti_extract/plotting/` - heatmap and residue plotting helpers. [repo-observed]
- `scripts/run_type0ppln_pplus_auto_dim.py` - direct Type0ppln `P_plus` / auto-dim pilot script with high-dimensional sparse mode. [repo-observed]
- Top-level compatibility/legacy scripts:
  - `extract_jti.py` [repo-observed]
  - `compute_jti_schmidt.py` [repo-observed]
  - `tdc_layer_scan.py` [repo-observed]
  - `tdc_residue_diagnostics.py` [repo-observed]
- `configs/` - observed YAML configs:
  - `smoke.yaml`, `type0ppln.yaml`, `type2.yaml`. [repo-observed]
- `docs/` - documentation:
  - `CLI.md`, `DATA_CONTRACT.md`, `DIAGNOSTICS_40PS.md`, `OUTPUTS.md`, `SCHMIDT_ANALYSIS.md`, `TROUBLESHOOTING.md`, `TYPE0PPLN_PPLUS_AUTO_DIM_REPORT.md`, `WORKFLOWS.md`, `index.md`. [repo-observed]
- `tests/` - pytest tests and fixtures:
  - `test_binning.py`, `test_cli_smoke.py`, `test_io_contract.py`, `test_pairing.py`, `test_schmidt.py`, `test_cv_extract.py`. [updated 2026-05-27]
- `results/` - generated results and previously generated artifacts. Treat as output area, not source. [repo-observed]
- `pyproject.toml` - package metadata, dependencies, console scripts, pytest configuration. [repo-observed]

## 3. Execution Environment

- Expected OS: WSL/Linux is preferred for future portable harness work; Windows has been used historically. [memory-derived]
- Expected Python/MATLAB/Octave/other runtime:
  - Python `>=3.9`. [repo-observed]
  - Core dependency: `numpy`. [repo-observed]
  - Optional dependencies: `matplotlib` for plotting, `pytest` for tests. [repo-observed]
  - Swabian TimeTagger Python bindings are needed for direct `*.ttbin` reading and are distributed with Swabian software, not reliably from PyPI. [repo-observed]
  - MATLAB/Octave runtime is not a primary observed requirement for this project. [uncertain]
- Known environment constraints:
  - `*.ttbin` workflows depend on TimeTagger bindings and may fail where those bindings are absent. [repo-observed]
  - Large Type0ppln high-dimensional `P_plus` analysis must use sparse profile logic; dense `dim` arrays or dense `dim x dim` JTI matrices are not feasible at high dimensions. [memory-derived]
  - Full data processing may read large time-tag files and should not be launched as a default smoke test. [memory-derived]
  - Windows PowerShell in the observed environment displayed UTF-8 Markdown as mojibake in terminal previews; this is a console-encoding display issue, not necessarily file corruption. [repo-observed]
- WSL migration notes:
  - Use POSIX paths in new harness files and commands. [memory-derived]
  - Do not encode Windows absolute paths as executable defaults in harness files. If a historical Windows path is recorded, mark it as `legacy Windows path`. [memory-derived]
  - For historical Type0ppln data, a legacy Windows data root was used: `D:\Data\Raw Data\Type0ppln JTI` (legacy Windows path). In WSL, verify the actual mounted path before running. [memory-derived]

## 4. Main Workflows

### Data preprocessing / JTI extraction

- entrypoint: `jti-extract` console script or `python -m jti_extract.cli.extract`. [repo-observed]
- input: Dataset directory containing parsed `parsed_timebin_data.npz` or explicit `*.ttbin`; channel and binning parameters are supplied by CLI. [repo-observed]
- output: JTI counts CSV by default; optional NPZ, metadata, and plot outputs depending on flags. [repo-observed]
- safe smoke command: `python -m jti_extract.cli.extract --self-test` [repo-observed]
- heavy command, if known: Full extraction against real `*.ttbin` with `--prefer-ttbin`, large dimensions, plotting, and NPZ export. [repo-observed]
- do-not-run-by-default commands: Any command targeting raw production `*.ttbin` files or writing into shared `results/` without a new output directory. [memory-derived]

### Schmidt-number analysis

- entrypoint: `jti-schmidt` console script or `python -m jti_extract.cli.schmidt`. [repo-observed]
- input: One JTI CSV file or a directory containing JTI count CSV files. [repo-observed]
- output: `jti_schmidt_summary.csv` by default when processing a directory, or user-selected summary CSV. [repo-observed]
- safe smoke command: `python -m jti_extract.cli.schmidt --self-test` [repo-observed]
- heavy command, if known: Recursive Schmidt analysis over large result trees with many large counts CSV files. [repo-observed]
- do-not-run-by-default commands: Batch recursive analysis over production output directories without explicit output path and review. [memory-derived]

### TDC residue diagnostics

- entrypoint: `jti-tdc-residue` console script or `python -m jti_extract.cli.tdc_residue`. [repo-observed]
- input: One `*.ttbin` file and selected channel IDs. [repo-observed]
- output: Residue histograms, plots, and summary files under an output directory. [repo-observed]
- safe smoke command: No repository-scanned self-test was observed for this CLI. Prefer `pytest` tests instead. [repo-observed]
- heavy command, if known: Full `*.ttbin` residue diagnostic with live hardware calibration probe or large event count. [repo-observed]
- do-not-run-by-default commands: Commands using `--probe-live-calibration` or production `*.ttbin` paths. [repo-observed]

### TDC layer scan diagnostics

- entrypoint: `jti-tdc-layer-scan` console script or `python -m jti_extract.cli.tdc_layer_scan`. [repo-observed]
- input: One `*.ttbin` file, channel IDs, pairing window, period scan settings, surrogate settings, bin widths, dimensions. [repo-observed]
- output: Layer scan CSV summaries, period scan plots, pairing modulo plots, surrogate/time-split summaries. [repo-observed]
- safe smoke command: No self-test argument was observed for this CLI. Prefer focused pytest tests for harness smoke. [repo-observed]
- heavy command, if known: Full layer scan with surrogates and many period/bin-width/dim combinations. [repo-observed]
- do-not-run-by-default commands: Full layer scan on production `.ttbin` with surrogates enabled. [repo-observed]

### Type0ppln direct `P_plus` / auto-dim pilot

- entrypoint: `python scripts/run_type0ppln_pplus_auto_dim.py`. [repo-observed]
- input: A data root containing `*.ttbin` files, channel selection, pairing cutoff, bin width, dim sweep settings, optional previous output directory for continuation. [repo-observed]
- output: `README.md`, `run_config.json`, `dedupe_report.csv`, `pplus_auto_dim_summary.csv`, `auto_dim_decision.csv`, `file_summary.csv`, profile CSVs, plots, logs, and optional tag cache under a new output directory. [repo-observed]
- safe smoke command: `python scripts/run_type0ppln_pplus_auto_dim.py --dry-run --data-root <POSIX_DATA_ROOT>` [repo-observed]
- heavy command, if known: High-dimensional continuation with `--auto-dim`, large `--high-dim-max-dim`, production `*.ttbin`, and `--jobs 15`. [memory-derived]
- do-not-run-by-default commands: Any non-dry-run command against production Type0ppln data, especially high-dimensional scans beyond `dim=65536`. [memory-derived]

### Plotting and report/table generation

- entrypoint: Plotting occurs through extraction/diagnostic CLIs and the Type0ppln `P_plus` script. [repo-observed]
- input: Counts CSVs, profile CSVs, diagnostic summaries, or result directories. [repo-observed]
- output: PNG figures and CSV/JSON summary files under output directories. [repo-observed]
- safe smoke command: Use pytest tests; do not generate production plots in a harness smoke run. [memory-derived]
- heavy command, if known: Full plotting over real JTI/result directories. [uncertain]
- do-not-run-by-default commands: Commands that overwrite existing figures in `results/`, raw data folders, or legacy output directories. [memory-derived]

## 5. Data and Result Policy

- raw data directories:
  - Production raw data lives outside the repository in historical runs. Example only: `D:\Data\Raw Data\Type0ppln JTI` (legacy Windows path). [memory-derived]
  - Future WSL harnesses must use a configurable POSIX data root such as an environment variable or explicit CLI placeholder, not a baked-in Windows path. [memory-derived]
- result/output directories:
  - `results/` is an observed repository output area. Treat existing contents as generated artifacts and do not overwrite without explicit instruction. [repo-observed]
  - Type0ppln `P_plus` runs historically wrote output directories under the external data root using timestamped names such as `pplus_auto_dim_YYYYMMDD_HHMMSS`. [memory-derived]
- checkpoint directories:
  - No ML checkpoint directory was observed in the repository scan. [repo-observed]
  - `tag_cache/` may appear under Type0ppln `P_plus` output directories and should be treated as generated cache, not source. [memory-derived]
- files/directories agents must not overwrite:
  - Raw `*.ttbin` files. [memory-derived]
  - External raw data directories. [memory-derived]
  - Existing `results/` artifacts unless explicitly requested. [repo-observed]
  - Existing output directories named by timestamp, including Type0ppln `pplus_auto_dim_*` directories. [memory-derived]
  - Any `logs/`, `runs/`, `outputs/`, or `checkpoints/` directories if present in future copies. [memory-derived]
- preferred new-output naming convention:
  - Use timestamped directories, e.g. `<workflow>_YYYYMMDD_HHMMSS`. [memory-derived]
  - For experiments under the repository, prefer a new subdirectory under a clearly marked scratch/output root rather than reusing an existing result directory. [memory-derived]

## 6. Schema and Interface Contract

- CSV columns that must not silently change:
  - Type0ppln `dedupe_report.csv`: `logical_id`, `kept_path`, `duplicate_paths`, `dedupe_method`, `total_events`, `selected_channel_counts`, `status`, `error`, `suggestion`. [memory-derived]
  - Type0ppln `pplus_auto_dim_summary.csv`: `logical_id`, `file_name`, `file_path`, `dim`, `bin_width_ps`, `frame_length_ps`, `frame_origin_ps`, `tau0_ps`, `channels`, `pairing_rule`, `coincidence_window_ps`, `diag_band_bins`, `total_pairs`, `pairs_in_diag_band`, `diag_band_fraction`, `P_plus_total`, `P_plus_peak`, `P_plus_peak_index`, `P_plus_FWHM_ps`, `P_plus_central_50_width_ps`, `P_plus_central_90_width_ps`, `P_plus_central_95_width_ps`, `P_plus_sigma_ps`, `P_plus_participation_time_ps`, `width_ratio_95`, `edge_fraction`, `relative_change_W95`, `covered`, `P_minus_peak_delta_bins`, `P_minus_FWHM_ps`, `P_minus_sigma_ps`, `P_minus_central_90_width_ps`, `P_minus_central_95_width_ps`, `status`, `error`, `suggestion`, `profile_storage`, `n_nonzero_P_plus_bins`, `estimated_profile_bytes`, `frame_origin_method`. [memory-derived]
  - Type0ppln `auto_dim_decision.csv`: `logical_id`, `dim`, `frame_length_ps`, `W95_ps`, `width_ratio_95`, `edge_fraction`, `relative_change_W95`, `covered`, `stop_reason`. [memory-derived]
  - Type0ppln `file_summary.csv`: `logical_id`, `kept_file`, `duplicate_count`, `n_pairs`, `tau0_ps`, `final_dim`, `final_frame_length_ps`, `final_W95_ps`, `final_width_ratio_95`, `final_edge_fraction`, `final_covered`, `final_status`, `stop_reason`, `output_profile_path`, `output_plot_path`. [memory-derived]
  - Type0ppln `P_plus` profile CSV: `bin_index`, `time_ps`, `counts`; may include rolled-profile columns when implemented. [memory-derived]
  - Type0ppln `P_minus` profile CSV: `delta_bins`, `delta_time_ps`, `counts`. [memory-derived]
- JSON/YAML keys:
  - `run_config.json` keys mirror Type0ppln script config. Do not rename without explicit migration. [memory-derived]
  - Config YAML keys in `configs/*.yaml` were not fully inspected; verify before editing. [uncertain]
- CLI arguments that must not silently change:
  - `jti-extract`: `--data`, `--ttbin`, `--prefer-ttbin`, `--max-events`, `--raw-ch-a-id`, `--raw-ch-b-id`, `--ch-a`, `--ch-b`, `--binwidth-ps`, `--dimensions`, `--frame-origin-ps`, `--scan-frame-origin`, `--frame-origin-start-ps`, `--frame-origin-stop-ps`, `--frame-origin-step-ps`, `--out`, `--no-csv`, `--npz`, `--plot`, `--background-subtract`, `--peak-align`, `--align-mode`, `--normalize`, `--prefix`, `--quiet`, `--self-test`. [repo-observed]
  - `jti-schmidt`: `--input`, `--pattern`, `--recursive`, `--output`, `--threshold`, `--self-test`. [repo-observed]
  - `jti-tdc-residue`: `--ttbin`, `--out`, `--ch1`, `--ch3`, `--modulus-ps`, `--coincidence-window-ps`, `--max-events`, `--probe-live-calibration`. [repo-observed]
  - `jti-tdc-layer-scan`: `--ttbin`, `--out`, `--ch-a`, `--ch-b`, `--window-ps`, `--period-start-ps`, `--period-stop-ps`, `--period-step-ps`, `--hist-bin-ps`, `--time-splits`, `--surrogate-block-ms`, `--surrogate-shifts`, `--seed`, `--bin-widths-ps`, `--dims`, `--frame-origin-ps`, `--max-events`, `--skip-surrogates`, `--skip-folding`. [repo-observed]
  - `scripts/run_type0ppln_pplus_auto_dim.py`: `--data-root`, `--channels`, `--pairing-rule`, `--coincidence-window-ps`, `--bin-width-ps`, `--dims`, `--auto-dim`, `--auto-stop`, `--start-dim`, `--max-dim`, `--dim-growth`, `--jobs`, `--dense-profile-max-bins`, `--continue-from-existing`, `--min-next-dim`, `--high-dim-max-dim`, `--profile-storage`, `--diag-band-bins`, `--edge-bins-fraction`, `--edge-fraction-threshold`, `--stop-width-ratio`, `--stop-width-change`, `--dedupe-ttbin`, `--dry-run`, `--output-dir`. [repo-observed]
- config keys:
  - Config files exist but key-level contracts were not scanned for this handoff. Verify before changes. [uncertain]
- function signatures:
  - `src/jti_extract/cli/extract.py` exposes `run_extract(...)`; preserve signature unless explicitly requested. [repo-observed]
  - Core pairing, binning, and Schmidt functions are used by tests; do not silently change signatures. [repo-observed]
- output file naming conventions:
  - JTI extraction uses counts CSV naming and optional NPZ/PNG/meta outputs. Exact pattern should be verified in `docs/OUTPUTS.md` or implementation before edits. [uncertain]
  - Type0ppln `P_plus` output directories use `pplus_auto_dim_YYYYMMDD_HHMMSS`; profile files use `P_plus_<safe_file_stem>_dim<dim>.csv` and `P_minus_<safe_file_stem>_dim<dim>.csv`. [memory-derived]

## 7. Baseline and Scientific Semantics

- baseline algorithms:
  - JTI extraction from parsed or TimeTagger event data into joint time-bin count matrices. [repo-observed]
  - Nearest-neighbor and greedy-unique pairing are baseline pairing rules. [repo-observed]
  - Schmidt-number analysis uses singular-value spectrum of JTI counts. [repo-observed]
  - TDC diagnostics include residue/modulo structure and pairing-layer scans. [repo-observed]
  - Type0ppln direct `P_plus` analysis estimates main-diagonal time-support profile without dense JTI allocation. [memory-derived]
- current assumptions:
  - Type0ppln pilot used channels `1,3`, `pairing_rule=nearest`, `coincidence_window_ps=200`, `bin_width_ps=100`, `diag_band_bins=1`. [memory-derived]
  - Type0ppln final high-dimensional pilot used a global `tau0_ps=-4.0` from prior run context. [memory-derived]
  - `coincidence_window_ps` is a pairing cutoff and must remain independent of `bin_width_ps`. [memory-derived]
- high-risk variables:
  - Channel IDs and channel semantics. [repo-observed]
  - `coincidence_window_ps`, `bin_width_ps`, `dimensions` / `dim`, `frame_origin_ps`, `tau0_ps`. [repo-observed]
  - Pairing rule and duplicate-recording dedupe method. [memory-derived]
  - Background subtraction and peak alignment flags in extraction; docs indicate they should not change counts CSV semantics. [repo-observed]
- known coupling/confounding factors:
  - TimeTagger hardware residue structure can confound apparent timing/binning patterns. [repo-observed]
  - Frame origin affects diagonal concentration and must match the dense-JTI selection semantics when comparing direct profiles with JTI matrices. [memory-derived]
  - For high-dimensional `P_plus`, sparse support and acquisition-time span can make per-bin counts mostly 1; density should be interpreted after coarse binning. [memory-derived]
- metrics that must preserve meaning:
  - Schmidt number and singular spectrum weights. [repo-observed]
  - JTI raw counts CSV values. [repo-observed]
  - TDC residue histograms and pairing-layer summaries. [repo-observed]
  - Type0ppln `P_plus_central_95_width_ps`, `width_ratio_95`, `edge_fraction`, `relative_change_W95`, `covered`, and `final_status`. [memory-derived]

## 8. Known Issues and Fragile Points

- path issues:
  - Historical runs used Windows absolute paths. Do not copy those as WSL execution paths. Mark them legacy when documenting. [memory-derived]
  - Paths may contain spaces; use `pathlib` and shell quoting. [memory-derived]
  - WSL migration requires verifying mount paths for external data. [memory-derived]
- environment issues:
  - Swabian TimeTagger Python bindings may be unavailable in clean Python environments. [repo-observed]
  - Windows PowerShell execution policy may emit profile-loading errors and terminal encoding may display UTF-8 text incorrectly. [repo-observed]
  - Optional plotting needs `matplotlib`. [repo-observed]
- data format issues:
  - `*.ttbin` files can represent duplicate logical recordings, including suffix variants such as `.1.ttbin`; dedupe is needed for Type0ppln pilot. [memory-derived]
  - Parsed NPZ data and raw TimeTagger data have different channel conventions; do not interchange raw and logical channel IDs without checking CLI docs. [repo-observed]
- numerical/scientific interpretation risks:
  - Do not interpret `P_plus` as Schmidt number. [memory-derived]
  - Do not claim approximate or direct profile scans are exact dense cumulative SVD. [memory-derived]
  - High-dimensional `P_plus` width near acquisition span can indicate acquisition-window support rather than a narrow physical peak. [memory-derived]
  - Dense `dim x dim` JTI construction is infeasible for high dims and must not be used in high-dimensional `P_plus` scans. [memory-derived]
- long-running commands:
  - Full `.ttbin` extraction, layer scans, surrogate scans, high-dimensional `P_plus` continuation, recursive Schmidt batch processing over large result trees. [repo-observed]

## 9. Agent Operating Constraints

- Minimal patch only. [memory-derived]
- No broad refactoring unless explicitly requested. [memory-derived]
- No raw data modification. [memory-derived]
- No result overwrite. [memory-derived]
- No checkpoint/cache/output/log deletion unless explicitly requested and path-verified. [memory-derived]
- No baseline semantic change. [memory-derived]
- No schema change unless explicitly requested. [memory-derived]
- Preserve variable names, config names, CLI parameters, CSV columns, JSON/YAML keys, and output filenames unless the task explicitly requires migration. [memory-derived]
- WSL/POSIX path default for future harness documents and commands. [memory-derived]
- If historical Windows paths are mentioned, label them `legacy Windows path` and do not make them the default execution path. [memory-derived]
- Do not run full experiments as part of harness generation. Use dry-run or self-test commands only. [memory-derived]
- Treat the current dirty worktree as user-owned; do not revert unrelated changes. [repo-observed]

## 10. Unknowns To Verify

- Exact schema of all YAML config files in `configs/`. [uncertain]
- Exact output filename patterns for every `jti-extract` combination of flags. [uncertain]
- Whether top-level compatibility scripts call into package CLIs or contain divergent behavior. [uncertain]
- Whether all docs are UTF-8 clean in the WSL project copy; Windows terminal preview showed mojibake in the observed environment. [uncertain]
- Whether TimeTagger bindings and hardware metadata APIs are available in the target WSL environment. [uncertain]
- Whether Roo Code should create a dedicated sample-data smoke fixture beyond current `tests/fixtures`. [uncertain]
- Whether generated `pytest-cache-files-*`, `tests/_tmp_pytest`, `tests/_work`, and `__pycache__` directories exist in the WSL copy and should be ignored/cleaned by separate maintenance tasks. [uncertain]

## 11. Recommended Harness Files To Generate

- `AGENTS.md`
  - State repository-wide agent rules, path policy, data/result safety policy, schema-preservation rules, and WSL/POSIX default expectations. [memory-derived]
- `CURRENT_TASK.md`
  - Describe the immediate task in small, reviewable steps with explicit allowed files and forbidden side effects. [memory-derived]
- `RUN_COMMANDS.md`
  - List safe setup, lint/compile, self-test, dry-run, and optional heavy commands. Commands should use POSIX placeholders such as `<DATA_ROOT>` rather than legacy Windows paths. [memory-derived]
- `REVIEW_CHECKLIST.md`
  - Include checks for schema changes, CLI changes, output overwrite risk, raw-data safety, numerical semantics, and whether only allowed files changed. [memory-derived]
- `AGENT_HANDOFF.md`
  - Summarize current branch, dirty-worktree expectations, recent implemented workflows, known outputs, known risks, and next recommended actions. [memory-derived]
