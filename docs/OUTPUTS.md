# Outputs

## JTI Counts CSV

`*.counts.csv` is a square matrix. The first row and first column are bin indices. Matrix cell `(i, j)` is the number of accepted pairs where channel A maps to bin `i` and channel B maps to bin `j`.

The accepted-pair semantics are recorded in `*.meta.json`:

- `strict_single_hit_per_frame`: only frames with exactly one hit in each channel.
- `nearest_window`, `greedy_unique_window`, `all_pairs_window`: coincidence-window pairs folded into frame-local bins.

## JTI Meta JSON

`*.meta.json` records input source, dimensions, bin width, frame origin, pairing mode, coincidence window, pair counts, diagnostics, and optional analysis settings. Optional background subtraction, peak alignment, and normalization do not modify `*.counts.csv`.

## Diagonal Profile CSV/PNG

When `--plot-diagonal-profile` is used, `jti-extract` writes:

- `*.diagonal_profile.csv`
- `*.diagonal_profile.png`

The profile sums counts along the main-diagonal direction over `|j-i| <= --diagonal-profile-band-bins`. This is the recommended view when the JTI is a very narrow diagonal line.

## JTI Summary JSON

`*jti_summary.json` lists run-level input/output paths, selected bin widths, dimensions, frame origin, scan flag, and generated files.

## Schmidt Summary CSV

Fields include `file`, matrix shape, total counts, nonzero bins, `schmidt_number`, `purity`, `largest_weight`, `n_singular_values`, threshold, normalized sum, status, and error message.

## Residue Summary JSON

`tdc_residue` summaries include selected channels, residue modulus, coincidence window, event counts, uniformity statistics, optional live calibration probe status, and TTBIN configuration.

## TDC Layer Scan Summary JSON

Layer scan summaries include tag metadata, singles period scan, pairing layer summaries, surrogate shift/block shuffle summaries, time split stability, folding row count, interpretation, and notes.

## Coincidence Timeline Outputs

`scripts/analyze_ttbin_coincidence_timeline.py` writes:

- `coincidence_timeline.csv`: acquisition-time bins with coincidence counts and rate.
- `coincidence_timeline.png`: coincidence rate versus acquisition time.
- `coincidence_timeline_summary.json`: input parameters, event counts, pair counts, histogram statistics, and Poisson comparison.
