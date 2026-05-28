# Workflows

## Workflow 1: Mode A - Single-line JTI Analysis

For ordinary SPDC or single-peak JTI.

```bash
python -m jti_extract.cli.extract \
  --ttbin "path/to/data.1.ttbin" \
  --raw-ch-a-id 2 --raw-ch-b-id 3 \
  --binwidth-ps 20 --dimensions 128 \
  --window-ps 200 \
  --pair-center-ps 830 --tau-align-ps 830 \
  --svd-unwrapped --guard-bins 2 \
  --out results/single_line
```

Output: `schmidt_single_line.json`, `H_single_line.csv`, `singular_values.csv`

## Workflow 2: Mode B - BFC/FPC Multi-line JTI Analysis

For biphoton frequency comb / fiber cavity with multiple delay peaks.

```bash
python compute_fpc_schmidt.py \
  --ttbin "path/to/data.1.ttbin" \
  --peaks-csv "path/to/pminus_peaks.csv" \
  --delay-csv "path/to/pminus_delay_histogram.csv" \
  --raw-ch-a-id 2 --raw-ch-b-id 3 \
  --tau-align-ps 830 \
  --binwidth-ps 20 --dimensions 128 --guard-bins 2 \
  --out results/bfc_multiline
```

Output: `schmidt_results.json`, `summary.csv`, `H_comb.csv`, `H_full_window.csv`, `tooth_details.csv`

## Workflow 3: Compute Schmidt Number from Existing JTI

```bash
python -m jti_extract.cli.schmidt --input results/jti_dir --pattern "*.counts.csv"
```

## Workflow 4: TDC Residue Diagnostics

```bash
python -m jti_extract.cli.tdc_residue \
  --ttbin "path/to/data.1.ttbin" \
  --ch1 1 --ch3 3 \
  --out results/tdc_residue
```

## Workflow 5: TDC Layer Scan Diagnostics

```bash
python -m jti_extract.cli.tdc_layer_scan \
  --ttbin "path/to/data.1.ttbin" \
  --ch-a 1 --ch-b 3 --window-ps 1000 \
  --out results/tdc_layer_scan
```

## Workflow 6: Coincidence Timeline Stability

```bash
python scripts/analyze_ttbin_coincidence_timeline.py \
  --input "path/to/data.1.ttbin" \
  --channels 2 3 --coinc-window-ps 200 \
  --time-bin-s 0.01 \
  --output-dir results/coincidence_timeline
```

This diagnostic plots coincidence midpoint rate versus absolute acquisition time for stability checks.

## Workflow 7: BFC/FPC with Multiple Binwidths

Run Mode B analysis with multiple binwidths for comparison:

```bash
for bw in 10 20; do
  python compute_fpc_schmidt.py \
    --ttbin "data.1.ttbin" \
    --peaks-csv "pminus_peaks.csv" \
    --delay-csv "pminus_delay_histogram.csv" \
    --tau-align-ps 830 \
    --binwidth-ps $bw --dimensions 128 --guard-bins 2 \
    --out "results/bfc_bw${bw}"
done
```

## Workflow 8: BFC/FPC Multiple Angles

Process multiple angle datasets:

```bash
for angle in 90 135 180; do
  python compute_fpc_schmidt.py \
    --ttbin "Type II FPC ${angle}deg.1.ttbin" \
    --peaks-csv "pminus_peaks_${angle}.csv" \
    --delay-csv "pminus_delay_${angle}.csv" \
    --tau-align-ps 830 \
    --binwidth-ps 20 --dimensions 128 --guard-bins 2 \
    --out "results/bfc_${angle}"
done
```
