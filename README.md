# JTI Extract and BFC/FPC Schmidt-like Analysis

## Overview

This project provides tools for extracting Joint Time-bin Intensity (JTI) matrices from timetag data and computing Schmidt-like effective mode numbers. It supports two analysis modes:

- **Mode A: Single-line JTI** — for ordinary single-peak SPDC JTI analysis.
- **Mode B: BFC/FPC Multi-line JTI** — for biphoton frequency comb / fiber cavity multi-delay-peak structures.

## Analysis Modes

### Mode A: Single-line JTI

For ordinary SPDC or single-peak JTI analysis. Extracts one true-coordinate, unwrapped, edge-guarded, non-cyclic JTI and computes `K_single_line_raw`.

### Mode B: BFC/FPC Multi-line JTI

For biphoton frequency comb / fiber cavity structures with multiple delay peaks. Uses peak-aware greedy-unique pairing to construct:

- `H_comb` — JTI over tooth ROI union
- `H_full_window` — JTI over full delay range (comb + gap extension)
- `H_tooth_m` — per-tooth individual JTI

Computes: `K_global_comb_raw`, `K_comb_weight`, `K_tooth_m`, `K_full_window_greedy_unique_raw`.

## Physical Interpretation

**All K values are:**

```
background-unsubtracted
intensity-based
Schmidt-like effective mode number
using A = sqrt(normalized intensity)
not strict complex-amplitude Schmidt number
```

**Current version is JTI-stage temporal-domain characterization only.** This is NOT a full BFC time-frequency Schmidt decomposition. JSI-stage frequency-domain characterization will be added in a future version.

## Installation

```bash
python -m pip install -e .
python -m pip install -e ".[plotting,dev]"
```

`*.ttbin` reading requires Swabian TimeTagger Python bindings (installed with Swabian software, not on PyPI).

## Usage

### Mode A: Single-line JTI

```bash
python -m jti_extract.cli.extract \
  --ttbin "path/to/data.1.ttbin" \
  --raw-ch-a-id 2 \
  --raw-ch-b-id 3 \
  --binwidth-ps 20 \
  --dimensions 128 \
  --window-ps 200 \
  --pair-center-ps 830 \
  --tau-align-ps 830 \
  --svd-unwrapped \
  --guard-bins 2 \
  --out "output_dir/"
```

Backward-compatible shortcut: `--tau0-ps 830` sets both `--pair-center-ps` and `--tau-align-ps`.

### Mode B: BFC/FPC Multi-line JTI

```bash
python compute_fpc_schmidt.py \
  --ttbin "path/to/data.1.ttbin" \
  --peaks-csv "path/to/pminus_peaks.csv" \
  --delay-csv "path/to/pminus_delay_histogram.csv" \
  --raw-ch-a-id 2 \
  --raw-ch-b-id 3 \
  --tau-align-ps 830 \
  --binwidth-ps 20 \
  --dimensions 128 \
  --guard-bins 2 \
  --out "output_dir/"
```

`peaks_csv.delay_ps` is always interpreted as `raw_tau = t_B - t_A`. The `tau_align_ps` resolution priority: explicit `--tau-align-ps` > peaks_csv max-count peak > `--tau0-ps` fallback.

## Output Files

### Mode A Output

| File | Description |
|------|-------------|
| `H_single_line.csv` | True-coordinate unwrapped edge-guarded JTI matrix |
| `H_single_line.png` | JTI heatmap |
| `schmidt_single_line.json` | Schmidt-like K, purity, singular values, diagnostics |
| `singular_values.csv` | Singular values and lambda weights |
| `meta.json` | Full extraction metadata |

### Mode B Output

| File | Description |
|------|-------------|
| `schmidt_results.json` | Complete results with all K values and diagnostics |
| `summary.csv` | Top-level result summary |
| `pairing_diagnostics.json` | Greedy-unique pairing statistics |
| `H_comb.csv` | JTI over tooth ROI union |
| `H_full_window.csv` | JTI over full delay range (comb + gap) |
| `tooth_details.csv` | Per-tooth K, counts, diagnostics |
| `per_tooth_svd_input_{peak_id}.csv` | Per-tooth individual JTI |
| `singular_values_H_comb.csv` | Singular values for H_comb |
| `singular_values_H_full_window.csv` | Singular values for H_full_window |

## Validation

### Mode A Acceptance Criteria

1. No `np.clip` on bin indices (uses bounds check + reject).
2. `|weighted_mean_residual_tau_ps| < 100 ps` for main-peak JTI.
3. `bw=20`: `kept_fraction > 90%`.
4. `bw=10`: `cross_frame_fraction < 30%`.

### Mode B Acceptance Criteria

1. `sum(H_full_window) >= sum(H_comb)`.
2. `K_global_comb_raw` and `K_comb_weight` are in the same order of magnitude.
3. `K_comb_weight` uses retained counts from `H_tooth` after greedy + unwrap + edge guard.
4. Repeated runs give identical candidate counts, accepted counts, and K values.

## Project Structure

```
src/jti_extract/
    cli/extract.py          Mode A: single-line JTI extraction
    cli/schmidt.py          Schmidt number computation
    cli/tdc_layer_scan.py   TDC layer scan diagnostics
    core/                   Core exports (binning, pairing, schmidt)
    io/                     I/O helpers
    plotting/               Plotting utilities

compute_fpc_schmidt.py      Mode B: BFC/FPC multi-line analysis
compute_jti_schmidt.py      Schmidt number CLI wrapper
extract_jti.py              Legacy wrapper for extract.py

tests/                      Unit tests and regression tests
docs/                       Documentation
```

## Future Work

- JSI-stage frequency-domain characterization (`K_Omega`)
- JTI/JSI basis overlap analysis
- Time-frequency resource product computation

## License

MIT
