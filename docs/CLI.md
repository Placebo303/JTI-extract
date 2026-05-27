# CLI

## Main Entry Points

Module entry points:

- `python -m jti_extract.cli.extract` - JTI extraction with CV/DV/SVD output
- `python -m jti_extract.cli.schmidt` - Schmidt number analysis
- `python -m jti_extract.cli.tdc_residue` - TDC residue diagnostics
- `python -m jti_extract.cli.tdc_layer_scan` - TDC layer scan diagnostics

Console scripts after installation:

- `jti-extract`
- `jti-schmidt`
- `jti-tdc-residue`
- `jti-tdc-layer-scan`

## JTI Extraction (`jti-extract`)

The main JTI extraction tool produces three types of output:

### Output Types

1. **CV (Continuous Variable)**: Fine-bin 2D histogram showing modulo-time distribution
   - File: `cv_fine{N}ps_k{K}.csv/png`
   - Purpose: Diagnostic visualization of coincidence distribution

2. **DV (Divided Variable)**: Discrete JTI matrix for physical analysis
   - File: `dv_k{K}_bw{BW}ps_dim{D}.csv/png`
   - Purpose: Standard JTI matrix for coincidence analysis

3. **SVD (Unwrapped Edge-Guarded)**: Non-cyclic finite-window JTI for Schmidt/SVD analysis
   - File: `svd_jti_unwrapped_guarded_k{K}_bw{BW}ps_dim{D}.csv/png`
   - Purpose: SVD/Schmidt analysis (no wrap-around artifacts)

### Key Parameters

| Parameter | Default | Description |
|---|---|---|
| `--ttbin` | required | Path to .ttbin file |
| `--raw-ch-a-id` | 1 | TimeTagger raw channel id for A |
| `--raw-ch-b-id` | 3 | TimeTagger raw channel id for B |
| `--binwidth-ps` | 10 | Bin width in ps for DV output |
| `--dimensions` | 128 | Dimension for DV output |
| `--fine-bins` | 5 | Comma-separated fine bin widths for CV |
| `--k-values` | 1 | Comma-separated k values (window = k × binwidth) |
| `--scan-frame-origin` | false | Scan frame_origin and select best |
| `--svd-unwrapped` | true | Enable unwrapped edge-guarded JTI |
| `--guard-bins` | 2 | Edge guard bins for unwrapped JTI |
| `--tau0-ps` | 0 | B channel time offset in ps |

### Example Usage

```bash
# Basic extraction with SVD unwrapped output
python -m jti_extract.cli.extract \
  --ttbin "path/to/data.ttbin" \
  --raw-ch-a-id 1 --raw-ch-b-id 3 \
  --binwidth-ps 50 --dimensions 128 \
  --fine-bins 5 --k-values 1 \
  --scan-frame-origin --svd-unwrapped \
  --out "path/to/output"

# Multiple k values and fine bins
python -m jti_extract.cli.extract \
  --ttbin "path/to/data.ttbin" \
  --binwidth-ps 20 --dimensions 64 \
  --fine-bins 1,2,5 --k-values 1,2,3 \
  --scan-frame-origin \
  --out "path/to/output"
```

### Output Files

For each k value, the tool generates:

- `cv_fine{N}ps_k{K}.csv` - CV histogram (CSV)
- `cv_fine{N}ps_k{K}.png` - CV histogram (PNG)
- `cv_fine{N}ps_k{K}.meta.json` - CV metadata
- `dv_k{K}_bw{BW}ps_dim{D}.csv` - DV matrix (CSV)
- `dv_k{K}_bw{BW}ps_dim{D}.png` - DV matrix (PNG)
- `dv_k{K}_bw{BW}ps_dim{D}.meta.json` - DV metadata
- `svd_jti_unwrapped_guarded_k{K}_bw{BW}ps_dim{D}.csv` - SVD matrix (CSV)
- `svd_jti_unwrapped_guarded_k{K}_bw{BW}ps_dim{D}.png` - SVD matrix (PNG)
- `svd_jti_unwrapped_guarded_k{K}_bw{BW}ps_dim{D}.meta.json` - SVD metadata
- `frame_origin_scan_k{K}.csv` - Frame origin scan results
- `summary_k_scan.csv` - Summary of all k values
- `extraction_summary.json` - Overall summary

## Coincidence Timeline Diagnostic

The standalone timeline script analyzes coincidence midpoint timestamps over the full acquisition time.

```bash
python scripts/analyze_ttbin_coincidence_timeline.py \
  --input "<data.ttbin>" \
  --channels 1 3 \
  --coinc-window-ps 200 \
  --pairing-mode all_pairs \
  --time-bin-s 0.01 \
  --output-dir results/coincidence_timeline
```
