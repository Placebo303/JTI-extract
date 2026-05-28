# AGENT_PROJECT_MEMORY.md

## Project: JTI Extract and BFC/FPC Schmidt-like Analysis

### Purpose

Extract Joint Time-bin Intensity (JTI) matrices from timetag data and compute Schmidt-like effective mode numbers for:
- **Mode A**: Single-line SPDC JTI analysis
- **Mode B**: BFC/FPC multi-delay-peak analysis with peak-aware greedy-unique pairing

### Key Files

| File | Purpose |
|------|---------|
| `src/jti_extract/cli/extract.py` | Mode A: single-line JTI extraction |
| `compute_fpc_schmidt.py` | Mode B: BFC/FPC multi-line analysis |
| `src/jti_extract/cli/schmidt.py` | Schmidt number computation |
| `src/jti_extract/cli/tdc_layer_scan.py` | TDC layer scan diagnostics |
| `tests/` | Unit tests (35 tests) |

### Core Algorithm Rules (DO NOT MODIFY)

1. True-coordinate JTI (no synthetic idler axis)
2. Unwrapped non-cyclic JTI for SVD
3. Edge guard (default 2 bins)
4. No modulo-wrapped JTI for SVD
5. No background subtraction
6. No float64 binning for 17-digit ps timestamps
7. No np.clip on bin indices
8. Peak-aware greedy-unique pairing for BFC/FPC
9. H_full_window = accepted_comb + accepted_gap
10. K_comb_weight uses retained counts in H_tooth

### All K Values Are

```
background-unsubtracted
intensity-based
Schmidt-like effective mode number
A = sqrt(normalized intensity)
NOT strict complex-amplitude Schmidt number
```

### Current Status

- Version: v0.1.0 (JTI-stage only)
- Tests: 35/35 passing
- GitHub: https://github.com/Placebo303/JTI-extract.git
- Archived files: `archived/` (P_plus analysis, legacy configs)
