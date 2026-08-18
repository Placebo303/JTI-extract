# JTI extract handoff

## Current release work

- Working tree implements the `0.4.0` group-facing package release; it is not committed or pushed.
- `jti-raw-aligned` is the only recommended extraction command. `jti-extract` is legacy; `jti-tdc-residue` and `jti-tdc-layer-scan` are diagnostics.
- Microcavity multi-peak support is in `raw_aligned.py`: `--peak-mode auto|selected` writes a separate result directory per resolved residual-delay peak. It never silently merges peaks or subtracts background.

## Evidence boundary

- Passed: `python -m pytest tests/test_binning.py tests/test_raw_aligned_multipeak.py -q` (11 passed).
- Passed: `python -m jti_extract.cli.<raw_aligned|extract|tdc_residue|tdc_layer_scan> --help`.
- Known environment blocker: the full suite's `test_io_contract.py` can fail before analysis because Windows denies deletion of `tests/_work/io_contract/data/parsed_timebin_data.npz`. Do not delete this locked artifact without confirming its owner.
- Not yet verified on a real single-peak or microcavity multi-peak `.ttbin` acquisition. Do not claim experimental validation before preserving those two runs and their metadata.

## Method constraints

- Matrices are absolute all-ordered A-B pair counts inside an inclusive residual-delay window; `normalization=none` and `background_subtracted=false`.
- The analysis frame is `dimensions * binwidth_ps`; current multi-peak support only accepts resolved peaks within that same analysis frame.
- Use an explicit `--peak-window-ps` only when windows do not overlap. Auto mode constructs disjoint windows from resolved peak separations.

## Next work

1. Run and freeze one real single-peak and one real microcavity multi-peak example.
2. Check the chosen analysis frame against the experimental timing period.
3. Review the working-tree diff, commit intentionally, then push normally (no force push).
