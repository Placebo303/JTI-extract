# CLI Reference

Complete command-line interface documentation for JTI-extract.

## Console Scripts

After installation (`pip install -e .`), the following commands are available:

### `jti-extract`

Extract Joint Time-Intensity matrix from time-tag data.

```bash
jti-extract --data <path> --binwidth-ps <int> --dimensions <int> [options]
```

**Required Arguments:**

| Argument | Type | Description |
|----------|------|-------------|
| `--data` | path | Path to input data file (.ttbin, .npz, or .csv) |
| `--binwidth-ps` | int | Bin width in picoseconds |
| `--dimensions` | int | Number of JTI dimensions |

**Optional Arguments:**

| Argument | Default | Description |
|----------|---------|-------------|
| `--guard-bins` | 2 | Edge guard bins to exclude |
| `--delay-min-ps` | -1500 | Minimum residual delay (ps) |
| `--delay-max-ps` | 300 | Maximum residual delay (ps) |
| `--frame-origin-ps` | 0 | Frame origin offset (ps) |
| `--peaks-csv` | None | Path to peak detection CSV |
| `--compute-svd` | False | Enable SVD/K computation |
| `--out` | `results/` | Output directory |

**Example:**

```bash
jti-extract \
  --data "experiment.ttbin" \
  --binwidth-ps 40 \
  --dimensions 80 \
  --guard-bins 2 \
  --delay-min-ps -1000 \
  --delay-max-ps 200 \
  --compute-svd \
  --out results/my_experiment
```

---

### `jti-schmidt`

Compute Schmidt number and purity from JTI matrix.

```bash
jti-schmidt --input <path> [options]
```

**Required Arguments:**

| Argument | Type | Description |
|----------|------|-------------|
| `--input` | path | Path to JTI output directory (from `jti-extract`) |

**Optional Arguments:**

| Argument | Default | Description |
|----------|---------|-------------|
| `--out` | input dir | Output directory (defaults to input directory) |

**Example:**

```bash
jti-schmidt --input results/my_experiment
```

**Output:**

- `*_summary.csv`: Schmidt number, purity, singular values
- `*_svd_spectrum.png`: Singular value spectrum plot

---

### `jti-tdc-residue`

Analyze TDC 40ps residue pattern in time-tag data.

```bash
jti-tdc-residue --ttbin <path> [options]
```

**Required Arguments:**

| Argument | Type | Description |
|----------|------|-------------|
| `--ttbin` | path | Path to .ttbin file |

**Optional Arguments:**

| Argument | Default | Description |
|----------|---------|-------------|
| `--out` | `results/` | Output directory |

**Example:**

```bash
jti-tdc-residue --ttbin "experiment.ttbin" --out results/tdc_analysis
```

**Output:**

- `*_residual_tau.csv`: Residual delay histogram
- `*_residual_tau.png`: Histogram visualization
- `*_singles_distribution.csv`: Singles distribution
- `*_pair_dt.csv`: Pair time difference distribution

---

### `jti-tdc-layer-scan`

Scan through TDC layers to identify optimal operating point.

```bash
jti-tdc-layer-scan --ttbin <path> [options]
```

**Required Arguments:**

| Argument | Type | Description |
|----------|------|-------------|
| `--ttbin` | path | Path to .ttbin file |

**Optional Arguments:**

| Argument | Default | Description |
|----------|---------|-------------|
| `--out` | `results/` | Output directory |

**Example:**

```bash
jti-tdc-layer-scan --ttbin "experiment.ttbin" --out results/layer_scan
```

**Output:**

- `*_layer_scan.csv`: Layer-by-layer residue analysis
- `*_layer_scan.png`: Visualization of layer scan results

---

## Module Entry Points

Alternative invocation using Python modules:

```bash
python -m jti_extract.cli.extract --data ... --binwidth-ps ... --dimensions ...
python -m jti_extract.cli.schmidt --input ...
python -m jti_extract.cli.tdc_residue --ttbin ...
python -m jti_extract.cli.tdc_layer_scan --ttbin ...
```

## Legacy Wrappers

For backward compatibility, legacy script entry points are preserved:

```bash
python extract_jti.py --data ... --binwidth-ps ... --dimensions ...
python compute_jti_schmidt.py --input ...
python tdc_residue_diagnostics.py --ttbin ...
python tdc_layer_scan.py --ttbin ...
```

## Python API

### Extract JTI

```python
from jti_extract.cli.extract import main

# Programmatic invocation
main([
    "--data", "experiment.ttbin",
    "--binwidth-ps", "40",
    "--dimensions", "80",
    "--out", "results/"
])
```

### Compute Schmidt Number

```python
from jti_extract.cli.schmidt import main

main(["--input", "results/my_experiment"])
```

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | Invalid arguments |
| 2 | Input file not found |
| 3 | Invalid data format |
| 4 | Processing error |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `JTI_EXTRACT_LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `JTI_EXTRACT_CACHE_DIR` | Cache directory for intermediate results |
