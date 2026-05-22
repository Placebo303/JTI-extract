# JTI Extraction Toolkit

This repository extracts discrete joint time-bin coincidence matrices from timetag data, diagnoses 40 ps Time Tagger residue structure, and computes Schmidt-number summaries from JTI counts.

## Quick Start

```bash
python -m pip install -e .
python -m pip install -e ".[plotting,dev]"
python extract_jti.py --help
python compute_jti_schmidt.py --help
```

Legacy scripts remain available:

- `extract_jti.py`
- `compute_jti_schmidt.py`
- `tdc_residue_diagnostics.py`
- `tdc_layer_scan.py`

Installed console scripts:

- `jti-extract`
- `jti-schmidt`
- `jti-tdc-residue`
- `jti-tdc-layer-scan`

See `docs/` for data contracts, output schemas, workflows, diagnostics, and troubleshooting.
