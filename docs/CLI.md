# CLI

Legacy wrappers:

- `python extract_jti.py`
- `python compute_jti_schmidt.py`
- `python tdc_residue_diagnostics.py`
- `python tdc_layer_scan.py`

Module entry points:

- `python -m jti_extract.cli.extract`
- `python -m jti_extract.cli.schmidt`
- `python -m jti_extract.cli.tdc_residue`
- `python -m jti_extract.cli.tdc_layer_scan`

Console scripts after installation:

- `jti-extract`
- `jti-schmidt`
- `jti-tdc-residue`
- `jti-tdc-layer-scan`

Standalone diagnostic scripts:

- `python scripts/analyze_ttbin_coincidence_timeline.py`

## JTI pairing modes

`jti-extract` supports multiple pairing modes:

- `strict_single_hit_per_frame`: conservative default; keep only frames with exactly one hit in each channel.
- `nearest_window`: pair each channel-A event to its nearest channel-B event inside `--coincidence-window-ps`.
- `greedy_unique_window`: one-to-one greedy pairing inside `--coincidence-window-ps`.
- `all_pairs_window`: accumulate all channel-A/channel-B pairs inside `--coincidence-window-ps`.

Example:

```bash
python extract_jti.py --data "<dataset>" --ttbin "<data.ttbin>" --raw-ch-a-id 1 --raw-ch-b-id 3 --pairing-mode all_pairs_window --coincidence-window-ps 200 --binwidth-ps 400 --dimensions 4500 --npz --out results/jti_window
```

Use `--plot-diagonal-profile` to also write `*.diagonal_profile.csv` and `*.diagonal_profile.png`, which show coincidence counts along the main-diagonal direction.

## Coincidence timeline diagnostic

The standalone timeline script analyzes coincidence midpoint timestamps over the full acquisition time. It does not fold events into JTI frames by default.

```bash
python scripts/analyze_ttbin_coincidence_timeline.py --input "<data.ttbin>" --channels 1 3 --coinc-window-ps 200 --pairing-mode all_pairs --time-bin-s 0.01 --output-dir results/coincidence_timeline
```
