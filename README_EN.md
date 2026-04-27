# JTI Counts Extraction (`extract_jti.py`)

Extract a discrete joint time-bin coincidence matrix in the arrival-time basis from pre-aligned timetag data.

Main entry point: `extract_jti.py`

## What This Tool Produces

The primary result is a discrete joint time-bin counts matrix (`counts.csv`).

- Input timetags are assumed to be pre-aligned between the two channels.
- `frame_origin_ps` controls the shared time origin / frame phase used for discrete binning.
- The current implementation applies `strict_single_hit_per_frame` post-selection by default.
- Therefore, the output is not an unconditional 2D histogram of all events. It is a filtered discrete JTI counts table under that post-selection rule.

## Features

- Read either `parsed_timebin_data.npz` or raw `*.ttbin`
- Export the primary discrete JTI counts table as CSV
- Support an explicit `--frame-origin-ps` for time-bin mapping
- Scan candidate frame origins with `--scan-frame-origin` and diagnose main / secondary diagonals
- Optionally export NPZ and PNG
- Keep legacy background subtraction / peak alignment / normalization only as optional analysis steps; they do not modify `counts.csv`

## Requirements

- Python 3
- Required: `numpy`
- Optional for plotting (`--plot`): `matplotlib`
- Optional for direct `*.ttbin` parsing: Swabian `TimeTagger` Python bindings

Install basic dependencies:

```bash
python -m pip install -U numpy
python -m pip install -U matplotlib  # only needed for --plot
```

## Quick Start

Show CLI help:

```bash
python extract_jti.py --help
```

### Minimal Extraction

```bash
python extract_jti.py \
  --data "E:\Data\YourDataset" \
  --binwidth-ps 200 \
  --dimensions 32 \
  --frame-origin-ps 0 \
  --out "E:\Data\YourDataset\jti_out"
```

### Frame-Origin Scan

Use this when you see a stable nearest-neighbor secondary diagonal and want to test whether it depends on the chosen shared time origin `t0`.

```bash
python extract_jti.py \
  --data "E:\Data\YourDataset" \
  --binwidth-ps 200 \
  --dimensions 32 \
  --scan-frame-origin \
  --frame-origin-start-ps 0 \
  --frame-origin-stop-ps 200 \
  --frame-origin-step-ps 5 \
  --out "E:\Data\YourDataset\jti_out"
```

### Input Modes

Mode A: use `parsed_timebin_data.npz` (recommended)

The script searches `--data` for:

- `parsed_timebin_data.npz`
- `01_raw_parsing/parsed_timebin_data.npz`
- `results/01_raw_parsing/parsed_timebin_data.npz`

Mode B: read `*.ttbin` directly

Requires Swabian `TimeTagger` Python bindings.

```bash
python extract_jti.py \
  --data "E:\Data\YourDataset" \
  --ttbin "E:\Data\YourDataset\file.ttbin" \
  --binwidth-ps 200 \
  --dimensions 32 \
  --frame-origin-ps 0 \
  --out "E:\Data\YourDataset\jti_out"
```

If both NPZ and TTBIN exist and you want to force TTBIN input, add `--prefer-ttbin`.

## Output Files

For each `(dimension, binwidth_ps)` pair, the filename stem is:

`{prefix}jti_dim{dim}_bw{bw}ps`

Primary outputs:

- `{stem}.counts.csv`
- `{stem}.meta.json`

Optional outputs:

- `{stem}.npz` with `jti_counts` and optional analysis arrays
- `{stem}.png` raw-count heatmap

Scan outputs when `--scan-frame-origin` is enabled:

- `{stem}.frame_origin_scan.csv`
- `{stem}.frame_origin_scan_best.json`

Run summary:

- `{prefix}jti_summary.json`

## Diagnostics

The frame-origin scan computes:

- `diag_main_sum`: sum of the main diagonal
- `diag_pm1_sum`: sum of the first upper and lower diagonals without wrap
- `total_sum`: total matrix counts
- `diag_main_fraction`
- `diag_pm1_fraction`
- `diag_contrast = diag_main_fraction - diag_pm1_fraction`

The best frame origin is selected by:

1. Maximize `diag_main_fraction`
2. Minimize `diag_pm1_fraction`
3. Maximize `diag_contrast`
4. Choose the smallest `frame_origin_ps`

## Notes

- `TimeTag` values are treated as picoseconds by project convention.
- `frame_origin_ps` is a shared time origin for binning. It is not a two-channel relative delay compensation term.
- The scan mode requires exactly one `--binwidth-ps` and one `--dimensions` value.
- `--raw-ch-a-id` and `--raw-ch-b-id` are hardware raw channel IDs for TTBIN parsing.
- `--ch-a` and `--ch-b` are logical labels after mapping.

## Built-In Validation

Run the toy validation without external test frameworks:

```bash
python extract_jti.py --self-test
```

## Troubleshooting

- `numpy is missing ...`: install numpy in the same Python environment
- `matplotlib is required for --plot`: install matplotlib or remove `--plot`
- `cannot import TimeTagger` while reading `*.ttbin`: install Swabian software and matching Python bindings, or use the NPZ input mode
