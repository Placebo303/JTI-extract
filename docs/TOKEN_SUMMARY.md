# Token Summary

Purpose: extract JTI counts from timetag data, diagnose TDC 40ps residue, and compute Schmidt-number summaries.

Primary code:

- `src/jti_extract/cli/extract.py`
- `src/jti_extract/cli/schmidt.py`
- `src/jti_extract/cli/tdc_residue.py`
- `src/jti_extract/cli/tdc_layer_scan.py`
- `scripts/analyze_ttbin_coincidence_timeline.py`

Legacy wrappers remain at repo root and only call the new CLI modules.

Data contract: timestamps are picoseconds; NPZ requires `Ch` and `TimeTag`; TTBIN requires Swabian TimeTagger bindings. JTI extraction supports strict single-hit frames and coincidence-window pairing modes (`nearest_window`, `greedy_unique_window`, `all_pairs_window`).

Main commands:

- `python extract_jti.py --help`
- `python compute_jti_schmidt.py --help`
- `python tdc_residue_diagnostics.py --help`
- `python tdc_layer_scan.py --help`
- `python scripts/analyze_ttbin_coincidence_timeline.py --help`
- `pytest -q`

Accepted Type0ppln finding: channels `1,3`, `coincidence_window_ps=200`, `all_pairs_window`/`all_pairs` produces `646811` coincidences. The JTI is a narrow main diagonal; `--plot-diagonal-profile` is the clearest JTI view. Absolute acquisition-time coincidence timeline at 10 ms bins was stable (`std_counts_over_poisson` about 1.0007). Folded checks over 3-40 us did not show a microsecond-scale concentration/decay envelope.

Do not read `results/` by default. It contains generated outputs and large caches. External generated Type0ppln outputs under `D:\Data\Raw Data\Type0ppln JTI` are also analysis artifacts, not source. Read `docs/`, `tests/`, and the relevant `src/jti_extract/cli/` or `scripts/` module first.
