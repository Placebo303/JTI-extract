# Outputs

## JTI Counts CSV

`*.counts.csv` is a square matrix. The first row and first column are bin indices. Matrix cell `(i, j)` is the number of strict single-hit frame pairs where channel A maps to bin `i` and channel B maps to bin `j`.

## JTI Meta JSON

`*.meta.json` records input source, dimensions, bin width, frame origin, pair counts, diagnostics, and optional analysis settings. Optional background subtraction, peak alignment, and normalization do not modify `*.counts.csv`.

## JTI Summary JSON

`*jti_summary.json` lists run-level input/output paths, selected bin widths, dimensions, frame origin, scan flag, and generated files.

## Schmidt Summary CSV

Fields include `file`, matrix shape, total counts, nonzero bins, `schmidt_number`, `purity`, `largest_weight`, `n_singular_values`, threshold, normalized sum, status, and error message.

## Residue Summary JSON

`tdc_residue` summaries include selected channels, residue modulus, coincidence window, event counts, uniformity statistics, optional live calibration probe status, and TTBIN configuration.

## TDC Layer Scan Summary JSON

Layer scan summaries include tag metadata, singles period scan, pairing layer summaries, surrogate shift/block shuffle summaries, time split stability, folding row count, interpretation, and notes.
