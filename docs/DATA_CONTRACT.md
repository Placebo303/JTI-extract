# Data Contract

## Time Unit

All `TimeTag` and timestamp values are treated as picoseconds by project convention.

## Channel Semantics

For parsed NPZ input, `Ch` stores logical channel labels. The JTI extractor defaults to `--ch-a 0` and `--ch-b 1`. For TTBIN input, `--raw-ch-a-id` and `--raw-ch-b-id` select hardware channels, then the reader maps them to logical labels.

## NPZ Requirements

Required fields:

- `Ch`: channel array
- `TimeTag`: timestamp array in ps

Optional fields:

- `overflow_types`
- `missed_events`

## TTBIN Requirements

TTBIN reading requires Swabian Instruments TimeTagger Python bindings. The project does not install these from PyPI. If TimeTagger is unavailable, NPZ and CSV workflows still work.

## Binning Definitions

- `bin_width_ps`: width of one time bin in ps
- `dimensions`: number of bins per frame and output matrix axis
- `frame_width_ps`: `bin_width_ps * dimensions`
- `frame_origin_ps`: shared time origin used before floor division into bins

## Tau Coordinate System

- `delay_ps` in peaks_csv: always `raw_tau = t_B - t_A`
- `tau_align_ps`: B channel alignment correction. `t_B_corr = t_B - tau_align_ps`
- `residual_tau = t_B_corr - t_A = delay_ps - tau_align_ps`
- `pair_center_ps`: pairing window center offset. Pair selection: `|t_B - t_A - pair_center_ps| <= window_ps`

## Pairing Methods

- `all_pairs`: all cross-channel deltas inside the coincidence window
- `nearest`: nearest event in channel B for each event in channel A within the window
- `greedy_unique`: sorted candidate pairs by absolute delay, then greedily keeps one-to-one assignments
- `peak_aware_greedy_unique`: for BFC/FPC, each peak has its own ROI; global greedy ensures each A/B used at most once

## Output Stability

Existing CLI parameter names and output field meanings are treated as compatibility surface. Schema additions should be additive.
