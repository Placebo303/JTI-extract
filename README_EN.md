# JTI Extraction (`extract_jti.py`)

Extract delay-delay JTI (Joint Temporal Intensity) matrices from Swabian Instruments Time Tagger ToA timetag data, and export results as CSV / NPZ / PNG (optional).

Main entry point: `extract_jti.py`

## Features

- Two input modes: `parsed_timebin_data.npz` or raw `*.ttbin`
- Batch export with multiple settings (for example `--binwidth-ps 50,100 --dimensions 16,32`)
- Optional background subtraction, peak alignment, normalization, and PNG heatmap output
- Works with Windows-style paths and WSL/Linux path conversion

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

### Mode A: Use `parsed_timebin_data.npz` (recommended)

The script searches `--data` for:

- `parsed_timebin_data.npz`
- `01_raw_parsing/parsed_timebin_data.npz`
- `results/01_raw_parsing/parsed_timebin_data.npz`

Run:

```bash
python extract_jti.py --data "E:\Data\YourDataset"
```

Export NPZ + PNG:

```bash
python extract_jti.py \
  --data "E:\Data\YourDataset" \
  --out "E:\Data\YourDataset\jti_out" \
  --npz --plot
```

### Mode B: Read `*.ttbin` directly

Requires Swabian `TimeTagger` Python bindings.

```bash
python extract_jti.py \
  --data "E:\Data\YourDataset" \
  --ttbin "E:\Data\YourDataset\file.ttbin" \
  --binwidth-ps 100 --dimensions 16 \
  --out "E:\Data\YourDataset\jti_out" \
  --plot
```

If both NPZ and TTBIN exist and you want to force TTBIN input, add `--prefer-ttbin`.

## Output Files

For each `(dimension, binwidth_ps)` pair, stem:

`{prefix}jti_dim{dim}_bw{bw}ps`

Default outputs:

- `{stem}.counts.csv`
- `{stem}.normalized.csv`
- `{stem}.meta.json`

Optional outputs:

- `{stem}.npz` (with `--npz`)
- `{stem}.png` (with `--plot`)

Run summary:

- `{prefix}jti_summary.json`

## Notes

- `--raw-ch-a-id` and `--raw-ch-b-id` are hardware raw channel IDs for TTBIN parsing (default `1/2`)
- `--ch-a` and `--ch-b` are logical labels after mapping (default `0/1`)
- Do not confuse raw channel IDs with logical labels

## Troubleshooting

- `numpy is missing ...`: install numpy in the same Python environment
- `matplotlib is required for --plot`: install matplotlib or remove `--plot`
- `cannot import TimeTagger` while reading `*.ttbin`: install Swabian software and matching Python bindings, or use Mode A

