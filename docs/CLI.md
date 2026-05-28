# CLI Reference

## Mode A: Single-line JTI Extraction

**Tool**: `extract_jti.py` or `python -m jti_extract.cli.extract`

### Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--ttbin` | required | Path to .ttbin file |
| `--raw-ch-a-id` | 1 | TimeTagger raw channel id for A |
| `--raw-ch-b-id` | 3 | TimeTagger raw channel id for B |
| `--binwidth-ps` | 10 | Bin width in ps |
| `--dimensions` | 128 | JTI matrix dimension |
| `--window-ps` | None | Pairing window in ps (overrides k * binwidth_ps) |
| `--k-values` | 1 | Comma-separated k values (window = k × binwidth) |
| `--pair-center-ps` | None | Pairing window center offset in ps |
| `--tau-align-ps` | None | B channel alignment correction for unwrapped SVD |
| `--tau0-ps` | 0 | Backward-compatible shortcut: sets both --pair-center-ps and --tau-align-ps |
| `--svd-unwrapped` | true | Enable unwrapped edge-guarded JTI |
| `--guard-bins` | 2 | Edge guard bins |
| `--scan-frame-origin` | false | Scan frame_origin and select best |
| `--out` | required | Output directory |

### Tau Coordinate Handling

- `--pair-center-ps`: shifts the pairing window center. Pair selection: `|t_B - t_A - pair_center_ps| <= window_ps`
- `--tau-align-ps`: shifts B channel for coordinate alignment. `t_B_corr = t_B - tau_align_ps`
- `--tau0-ps`: backward-compatible shortcut, sets both above if not explicitly provided

Resolution priority:
```
pair_center_ps = --pair-center-ps if provided, else --tau0-ps
tau_align_ps = --tau-align-ps if provided, else --tau0-ps
```

### Example

```bash
python -m jti_extract.cli.extract \
  --ttbin "data.1.ttbin" \
  --raw-ch-a-id 2 --raw-ch-b-id 3 \
  --binwidth-ps 20 --dimensions 128 \
  --window-ps 200 \
  --pair-center-ps 830 --tau-align-ps 830 \
  --svd-unwrapped --guard-bins 2 \
  --out "output/"
```

## Mode B: BFC/FPC Multi-line Analysis

**Tool**: `compute_fpc_schmidt.py`

### Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--ttbin` | required | Path to .ttbin file |
| `--peaks-csv` | required | Path to peaks CSV (delay_ps = raw_tau) |
| `--delay-csv` | required | Path to delay histogram CSV |
| `--raw-ch-a-id` | 2 | TimeTagger raw channel id for A |
| `--raw-ch-b-id` | 3 | TimeTagger raw channel id for B |
| `--tau-align-ps` | None | B channel alignment (priority: explicit > peaks_csv > tau0) |
| `--tau0-ps` | None | Fallback for tau_align_ps |
| `--binwidth-ps` | 20 | Bin width in ps |
| `--dimensions` | 128 | JTI matrix dimension |
| `--guard-bins` | 2 | Edge guard bins |
| `--min-counts-included` | 500 | Min counts for included summary statistics |
| `--min-counts-warning` | 10 | Min counts below which low_count_warning is set |
| `--prominence-fractions` | 0.02,0.04,0.08 | Comma-separated prominence thresholds |
| `--primary-prominence` | 0.04 | Primary prominence fraction |
| `--out` | required | Output directory |

### Example

```bash
python compute_fpc_schmidt.py \
  --ttbin "data.1.ttbin" \
  --peaks-csv "pminus_peaks.csv" \
  --delay-csv "pminus_delay_histogram.csv" \
  --tau-align-ps 830 \
  --binwidth-ps 20 --dimensions 128 --guard-bins 2 \
  --out "output/"
```

## Other Tools

### Schmidt Number Analysis

```bash
python -m jti_extract.cli.schmidt --input output/ --pattern "*.counts.csv"
```

### TDC Residue Diagnostics

```bash
python -m jti_extract.cli.tdc_residue --ttbin data.1.ttbin --ch1 1 --ch3 3 --out output/
```

### TDC Layer Scan

```bash
python -m jti_extract.cli.tdc_layer_scan --ttbin data.1.ttbin --ch-a 1 --ch-b 3 --window-ps 1000 --out output/
```

### Coincidence Timeline

```bash
python scripts/analyze_ttbin_coincidence_timeline.py --input data.1.ttbin --channels 2 3 --coinc-window-ps 200 --output-dir output/
```
