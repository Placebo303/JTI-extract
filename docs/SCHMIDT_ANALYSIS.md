# Schmidt-like Analysis

## Algorithm

All Schmidt-like K values in this project use the same computation:

```
P = H / sum(H)           # normalize counts to probability
A = sqrt(P)              # Joint Temporal Amplitude (intensity-based proxy)
s = SVD(A)               # singular values
lambda_n = s_n^2 / sum(s_n^2)   # normalized weights
purity = sum(lambda_n^2)
K = 1 / purity           # Schmidt-like effective mode number
```

## Physical Interpretation

**All K values are:**

- `background-unsubtracted`: no background or accidental subtraction applied
- `intensity-based`: uses `A = sqrt(normalized intensity)`, not complex amplitude
- `Schmidt-like effective mode number`: not a strict complex-amplitude Schmidt number

**This is JTI-stage temporal-domain characterization only.** It is NOT a full BFC time-frequency Schmidt decomposition. JSI-stage frequency-domain characterization will be added in a future version.

## Mode A: Single-line JTI

For ordinary SPDC or single-peak JTI analysis.

**Output**: `K_single_line_raw`

**Tool**: `extract_jti.py` (or `python -m jti_extract.cli.extract`)

**Process**:
1. Extract true-coordinate, unwrapped, edge-guarded, non-cyclic JTI
2. Compute `K_single_line_raw` from the full JTI matrix

## Mode B: BFC/FPC Multi-line JTI

For biphoton frequency comb / fiber cavity structures with multiple delay peaks.

**Outputs**:
- `K_global_comb_raw`: global K over selected comb-support ROI
- `K_comb_weight`: effective number of retained comb/delay components
- `K_tooth_m`: per-tooth local temporal Schmidt-like indicator
- `K_full_window_greedy_unique_raw`: operational one-to-one K over full delay range

**Tool**: `compute_fpc_schmidt.py`

**Process**:
1. Load peaks from `peaks_csv` (delay_ps = raw_tau = t_B - t_A)
2. For each peak, define ROI: `roi_half_ps = min(0.4 * tooth_spacing, max(3*bw, 1.5*FWHM/2))`
3. Generate candidate pairs for each peak ROI (comb mode) and full delay range (full mode)
4. Run greedy-unique pairing: each A and B event used at most once
5. Construct H_comb (tooth ROI union), H_full_window (comb + gap), H_tooth_m (per-tooth)
6. Compute K for each matrix

### H_full_window Construction

```
accepted_comb = greedy_unique(candidate_comb)
gap_candidates = candidate_full - candidate_comb
accepted_gap = greedy_unique(gap_candidates, inheriting used_a/used_b)
accepted_full = accepted_comb + accepted_gap
```

This ensures `sum(H_full_window) >= sum(H_comb)`.

### K_comb_weight

Uses retained counts from H_tooth after greedy + unwrap + edge guard:

```python
counts_per_tooth = {pid: int(sum(H_tooth[pid])) for pid in H_tooth}
p_m = counts_m / sum(counts_m)
K_comb_weight = 1 / sum(p_m^2)
```

## Validation Criteria

### Mode A

| Criterion | Threshold |
|-----------|-----------|
| No np.clip on bin indices | Required |
| \|weighted_mean_residual_tau_ps\| | < 100 ps |
| bw=20 kept_fraction | > 90% |
| bw=10 cross_frame_fraction | < 30% |

### Mode B

| Criterion | Requirement |
|-----------|-------------|
| sum(H_full_window) | >= sum(H_comb) |
| K_global_comb_raw vs K_comb_weight | Same order of magnitude |
| K_comb_weight source | H_tooth retained counts |
| Deterministic repeat | Identical candidate/accepted counts and K values |

## Future Work

- JSI-stage frequency-domain characterization (K_Omega)
- JTI/JSI basis overlap analysis
- Time-frequency resource product computation
