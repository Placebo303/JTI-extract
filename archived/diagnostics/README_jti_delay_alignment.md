# JTI Delay Alignment Diagnostic

`jti_delay_alignment.py` is a standalone diagnostic tool for checking whether
delay-histogram peaks are compatible with a chosen JTI time-bin width.

It does not modify an existing JTI. If the recommended bin width differs from
the width used to generate a JTI, rerun JTI extraction with the recommended
width, then rerun this alignment tool.

## Physical Meaning

The delay convention is:

```text
tau = t_B - t_A
```

Each delay peak `tau_n` corresponds to a parallel diagonal line in a JTI:

```text
idler_bin - signal_bin = k0 + round((tau_n - tau0) / bw_ps)
```

`tau0` is the reference peak, chosen by default as the strongest delay peak.
`k0` is the JTI diagonal offset of that reference line. When a JTI file is
provided, `k0` is inferred from the maximum diagonal sum unless `--jti-k0` is
passed.

## Why Bin Width Matters

The JTI bin width should satisfy three practical conditions:

- Each delay peak width should span about `2` to `6` JTI bins.
- Neighboring peaks should map to distinct rounded diagonal offsets.
- Peak centers should land close to integer diagonal offsets.

If `median_FWHM_ps / bw_ps < 2`, the bin width is too large and a peak is
undersampled. If it is greater than `6`, the bin width is too small, counts can
become sparse, and lines may look broken. If peak spacing divided by bin width
is not near an integer, lines can look broad, fuzzy, or jagged.

## Outputs

`delay_peaks.csv` lists detected and selected delay peaks:

- `tau_ps`: peak center in the original delay coordinate.
- `tau_rel_ps`: `tau_ps - tau0_ps`.
- `bg_sub_counts`: peak height after background subtraction.
- `fwhm_ps`, `left_ips_ps`, `right_ips_ps`: FWHM from explicit half-maximum
  crossings on the background-subtracted original histogram.

`bw_scan.csv` scores candidate bin widths:

- `fwhm_bins`: median FWHM divided by candidate `bw_ps`.
- `spacing_bins`: median peak spacing divided by candidate `bw_ps`.
- `integer_alignment_error_ps`: mean peak-center distance to the nearest
  integer offset.
- `num_unique_offsets`: number of distinct rounded diagonal offsets.
- `total_score`: lower is better.

`selected_peak_offsets.csv` maps peaks to the chosen bin width:

- `diagonal_offset_bin`: `round(tau_rel_ps / chosen_bw_ps)`.
- `alignment_error_ps`: residual error after rounding.
- `fwhm_bins`, `half_width_bins`: peak width in JTI-bin units.
- `rounded_left_offset_bin`, `rounded_right_offset_bin`: approximate offset
  span covered by the peak FWHM.

`alignment_summary.json` is the machine-readable summary for downstream tools.

## Examples

Delay-only analysis:

```bash
python tools/jti_delay_alignment.py ^
  --delay-csv results/fpc_publication_jti_dim256_bw20/90deg/pminus_delay_histogram.csv ^
  --outdir outputs/jti_alignment ^
  --delay-col auto ^
  --counts-col auto ^
  --tau0-ps auto ^
  --candidate-bw-ps 40:400:10 ^
  --chosen-bw-ps auto ^
  --peak-side positive
```

Delay plus JTI overlay:

```bash
python tools/jti_delay_alignment.py ^
  --delay-csv results/fpc_publication_jti_dim256_bw20/90deg/pminus_delay_histogram.csv ^
  --jti-csv results/fpc_publication_jti_dim256_bw20/90deg/publication_jti/publication_jti.counts.csv ^
  --jti-format auto ^
  --outdir outputs/jti_alignment ^
  --candidate-bw-ps 40:400:10 ^
  --chosen-bw-ps auto ^
  --peak-side positive
```

Use the recommended `bw_ps` to decide whether to rerun JTI extraction. The
overlay assumes the chosen bin width is consistent with the provided JTI unless
the JTI bin width can be inferred from file names or metadata.
