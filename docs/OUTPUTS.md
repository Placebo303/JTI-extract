# Output Files

## Mode A: Single-line JTI Output

### H_single_line.csv

Square count matrix. First row and first column are bin indices. Cell `(i, j)` is the number of accepted pairs where channel A maps to bin `i` and channel B maps to bin `j`.

### schmidt_single_line.json

```json
{
  "analysis_mode": "single_line_jti",
  "K_single_line_raw": 3.45,
  "purity": 0.29,
  "n_sv": 15,
  "total_counts": 17267,
  "kept_fraction": 0.94,
  "cross_frame_fraction": 0.03,
  "edge_rejected_fraction": 0.03,
  "invalid_count": 0,
  "residual_tau_diagnostics": {
    "weighted_mean_residual_tau_ps": -50.0,
    "weighted_std_residual_tau_ps": 80.0,
    "offset_min_ps": -200,
    "offset_max_ps": 200
  },
  "result_type": "background-unsubtracted intensity-based Schmidt-like effective mode number",
  "strict_schmidt_number": false,
  "uses_complex_phase": false,
  "background_subtracted": false,
  "amplitude_proxy": "sqrt(normalized_intensity)"
}
```

### singular_values.csv

| Column | Description |
|--------|-------------|
| index | Singular value index |
| singular_value | Singular value |
| lambda | Normalized weight (s^2 / sum(s^2)) |

### meta.json

Full extraction metadata including tau0_ps, pair_center_ps, tau_align_ps, residual diagnostics, etc.

## Mode B: BFC/FPC Multi-line Output

### schmidt_results.json

Complete results with all K values, diagnostics, and metadata. Key fields:

| Field | Description |
|-------|-------------|
| `analysis_mode` | "bfc_multiline_jti" |
| `K_global_comb_raw` | Global K over selected comb-support ROI |
| `K_comb_weight` | Effective number of retained comb components |
| `K_full_window_greedy_unique_raw` | Operational one-to-one K over full delay range |
| `K_tooth_raw` | Per-tooth K values |
| `K_tooth_weighted_mean` | Count-weighted mean of per-tooth K |
| `tooth_details` | Per-tooth detailed results |
| `pairing_diagnostics` | Greedy-unique pairing statistics |
| `residual_tau_diagnostics` | Residual tau statistics |

### summary.csv

Top-level result summary with one row per analysis run.

### pairing_diagnostics.json

Standalone pairing statistics:

```json
{
  "comb": {
    "candidate_count_total": 26656,
    "accepted_pair_count_total": 26379,
    "rejected_due_to_a_reuse": 277,
    "rejected_due_to_b_reuse": 0
  },
  "gap": {
    "candidate_count_total": 4829,
    "accepted_pair_count_total": 4829,
    "rejected_due_to_a_reuse": 0,
    "rejected_due_to_b_reuse": 0
  },
  "full_summary": {
    "candidate_count_comb": 26656,
    "candidate_count_full": 7378,
    "candidate_count_gap": 4829,
    "accepted_pair_count_comb": 26379,
    "accepted_pair_count_gap": 4829,
    "accepted_pair_count_full": 31208
  }
}
```

### H_comb.csv / H_full_window.csv

Square count matrices in the same format as H_single_line.csv.

- H_comb: JTI over tooth ROI union
- H_full_window: JTI over full delay range (comb + gap extension)

### tooth_details.csv

Per-tooth results:

| Column | Description |
|--------|-------------|
| peak_id | Peak identifier |
| tau_raw_ps | Raw delay (t_B - t_A) |
| tau_residual_ps | Residual delay (tau_raw - tau_align) |
| roi_half_ps | ROI half-width |
| fwhm_ps | FWHM from delay histogram |
| counts_in_roi | Retained counts after edge guard |
| K_tooth | Per-tooth Schmidt-like K |
| purity | Per-tooth purity |
| n_singular_values | Number of singular values |
| low_count_warning | true if counts < min_counts_warning |

### per_tooth_svd_input_{peak_id}.csv

Individual per-tooth JTI matrices.

### singular_values_H_comb.csv / singular_values_H_full_window.csv

Singular values and lambda weights for each matrix.

## Diagnostic Outputs

### frame_origin_scan_k{K}.csv

Frame origin scan results with score at each origin.

### summary_k_scan.csv

Summary of all k values with diagnostics.

### CV/DV outputs

- `cv_fine{N}ps_k{K}.csv/png`: Fine-bin 2D histogram (diagnostic)
- `dv_k{K}_bw{BW}ps_dim{D}.csv/png`: Discrete JTI matrix (diagnostic)

These are modulo-wrapped diagnostic outputs, NOT used for SVD/Schmidt analysis.

## TDC Diagnostic Outputs

### tdc_residue

- Residue histograms, plots, and summary files
- See `docs/DIAGNOSTICS_40PS.md` for interpretation

### tdc_layer_scan

- Layer scan CSV summaries, period scan plots, pairing modulo plots
- See `docs/DIAGNOSTICS_40PS.md` for interpretation

### coincidence_timeline

- `coincidence_timeline.csv`: acquisition-time bins with counts and rate
- `coincidence_timeline.png`: rate vs acquisition time
- `coincidence_timeline_summary.json`: parameters and statistics
