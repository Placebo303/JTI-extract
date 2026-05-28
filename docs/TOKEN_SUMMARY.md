# Token Summary

## Project Purpose

JTI extraction and BFC/FPC Schmidt-like effective mode number analysis from timetag data.

## Analysis Modes

| Mode | Tool | Purpose | Output |
|------|------|---------|--------|
| A | `extract_jti.py` | Single-line SPDC JTI | K_single_line_raw |
| B | `compute_fpc_schmidt.py` | BFC/FPC multi-line JTI | K_global_comb_raw, K_comb_weight, K_tooth_m, K_full_window_greedy_unique_raw |

## Key Files

| File | Purpose |
|------|---------|
| `src/jti_extract/cli/extract.py` | Mode A: single-line JTI extraction with SVD unwrapped output |
| `compute_fpc_schmidt.py` | Mode B: BFC/FPC peak-aware greedy-unique multi-line analysis |
| `src/jti_extract/cli/schmidt.py` | Schmidt number computation |
| `src/jti_extract/cli/tdc_layer_scan.py` | TDC layer scan diagnostics |
| `src/jti_extract/cli/tdc_residue.py` | TDC residue diagnostics |
| `scripts/analyze_ttbin_coincidence_timeline.py` | Coincidence timeline stability diagnostic |

## Data Contract

- Timestamps: picoseconds (ps)
- NPZ requires: `Ch`, `TimeTag` arrays
- TTBIN requires: Swabian TimeTagger Python bindings
- `peaks_csv.delay_ps`: always `raw_tau = t_B - t_A`

## Core Algorithm Rules

1. True-coordinate JTI (no synthetic idler axis)
2. Unwrapped non-cyclic JTI for SVD
3. Edge guard (default 2 bins)
4. No background subtraction
5. No float64 binning for 17-digit ps timestamps
6. No np.clip on bin indices
7. Peak-aware greedy-unique pairing for BFC/FPC

## All K Values

```
background-unsubtracted
intensity-based
Schmidt-like effective mode number
A = sqrt(normalized intensity)
NOT strict complex-amplitude Schmidt number
```

## Quick Commands

```bash
# Mode A: Single-line JTI
python -m jti_extract.cli.extract --ttbin data.1.ttbin --raw-ch-a-id 2 --raw-ch-b-id 3 \
  --binwidth-ps 20 --dimensions 128 --window-ps 200 --pair-center-ps 830 --tau-align-ps 830 \
  --svd-unwrapped --guard-bins 2 --out output/

# Mode B: BFC/FPC multi-line
python compute_fpc_schmidt.py --ttbin data.1.ttbin --peaks-csv peaks.csv --delay-csv delay.csv \
  --raw-ch-a-id 2 --raw-ch-b-id 3 --tau-align-ps 830 --binwidth-ps 20 --dimensions 128 \
  --guard-bins 2 --out output/

# Tests
python -m pytest
```

## Current Status

- Version: v0.1.0 (JTI-stage only)
- Tests: 35/35 passing
- Archived files: `archived/` (P_plus analysis, legacy configs)
