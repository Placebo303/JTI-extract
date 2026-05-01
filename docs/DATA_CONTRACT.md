# Data Contract

## Time Unit

All `TimeTag` and timestamp values are treated as picoseconds by project convention.

## Channel Semantics

For parsed NPZ input, `Ch` stores logical channel labels. The JTI extractor defaults to `--ch-a 0` and `--ch-b 1`. For TTBIN input, `--raw-ch-a-id` and `--raw-ch-b-id` select hardware channels, then the reader maps them to logical labels.

## NPZ Requirements

Required fields:

- `Ch`: channel array.
- `TimeTag`: timestamp array in ps.

Optional fields:

- `overflow_types`
- `missed_events`

The extractor searches `--data` for `parsed_timebin_data.npz`, `01_raw_parsing/parsed_timebin_data.npz`, and `results/01_raw_parsing/parsed_timebin_data.npz`.

## TTBIN Requirements

TTBIN reading requires Swabian Instruments TimeTagger Python bindings. The project does not install these from PyPI. If TimeTagger is unavailable, NPZ and CSV workflows still work.

## Binning Definitions

- `bin_width_ps`: width of one time bin in ps.
- `dimensions`: number of bins per frame and output matrix axis.
- `frame_width_ps`: `bin_width_ps * dimensions`.
- `frame_origin_ps`: shared time origin used before floor division into bins. It is not a two-channel delay compensation term.

## Strict Single-Hit Per Frame

For each logical channel, events are grouped by frame. Frames with exactly one event survive. Frames with zero or multiple events are excluded. Pairs are formed only for frames present exactly once in both channels.

## Pairing Methods

- `all_pairs`: all cross-channel deltas inside the coincidence window, accumulated as streaming statistics.
- `nearest`: nearest event in channel B for each event in channel A within the window.
- `greedy_unique`: sorted candidate pairs by absolute delay, then greedily keeps one-to-one channel A/B assignments.

Ultra-high-dimensional JTI planning note: `nearest` and `greedy_unique` are diagnostics for pairing sensitivity, not main physical pair-recovery algorithms. The ultra route uses fixed-global-lattice raw `g2_all_candidates` accumulation with a fixed physical `coincidence_window_ps`, edge guard, origin sensitivity checks, and method sensitivity diagnostics. As of 2026-04-29, the route does not default to background subtraction.

## Output Stability

Existing CLI parameter names, defaults except removed unsafe hard-coded `tdc_layer_scan` input path, and output field meanings are treated as compatibility surface. Schema additions should be additive.
