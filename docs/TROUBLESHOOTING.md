# Troubleshooting

## Installation

- `numpy is missing`: install with `python -m pip install -e .`
- `matplotlib is required`: install with `python -m pip install -e ".[plotting]"`
- `cannot import TimeTagger`: install Swabian TimeTagger software and matching Python bindings, or use `parsed_timebin_data.npz`

## Mode A: Single-line JTI

- `Must provide --tau0-ps or --pair-center-ps`: specify pairing window center via `--pair-center-ps` or `--tau0-ps`
- `Must provide --tau0-ps or --tau-align-ps`: specify B channel alignment via `--tau-align-ps` or `--tau0-ps`
- Low kept_fraction: check if `--pair-center-ps` matches the actual peak delay
- High cross_frame_fraction: the peak delay may span frame boundaries; try larger `--binwidth-ps` or `--dimensions`

## Mode B: BFC/FPC Multi-line

- `No peaks found in peaks_csv`: verify the CSV file has a `delay_ps` column
- `Must provide --tau-align-ps, valid peaks_csv, or --tau0-ps`: specify tau alignment
- `sum(H_full_window) < sum(H_comb)`: this should not happen; report as a bug
- Some teeth have `low_count_warning: true`: those teeth have very few pairs; they are excluded from included summary statistics

## Tau Coordinate System

- `peaks_csv.delay_ps` is always `raw_tau = t_B - t_A`
- `tau_align_ps` shifts B channel: `t_B_corr = t_B - tau_align_ps`
- `residual_tau = t_B_corr - t_A = delay_ps - tau_align_ps`
- For the main peak at `delay_ps = 830`, use `--tau-align-ps 830` to center it at residual tau = 0

## General

- `data dir not found`: verify path and Windows/WSL path translation
- `--ttbin is required`: provide explicit ttbin path
- Missing NPZ fields: ensure `Ch` and `TimeTag` are present
