# Token Summary

Purpose: extract JTI counts from timetag data, diagnose TDC 40ps residue, and compute Schmidt-number summaries.

Primary code:

- `src/jti_extract/cli/extract.py`
- `src/jti_extract/cli/schmidt.py`
- `src/jti_extract/cli/tdc_residue.py`
- `src/jti_extract/cli/tdc_layer_scan.py`

Legacy wrappers remain at repo root and only call the new CLI modules.

Data contract: timestamps are picoseconds; NPZ requires `Ch` and `TimeTag`; TTBIN requires Swabian TimeTagger bindings; strict single-hit keeps only frames with exactly one event in both channels.

Main commands:

- `python extract_jti.py --help`
- `python compute_jti_schmidt.py --help`
- `python tdc_residue_diagnostics.py --help`
- `python tdc_layer_scan.py --help`
- `pytest -q`

Do not read `results/` by default. It contains generated outputs and large caches. Read `docs/`, `tests/`, and the relevant `src/jti_extract/cli/` module first.
