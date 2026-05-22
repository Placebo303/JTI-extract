# Troubleshooting

- `numpy is missing`: install the project environment with `python -m pip install -e .`.
- `matplotlib is required`: install plotting extras with `python -m pip install -e ".[plotting]"`.
- `cannot import TimeTagger`: install Swabian TimeTagger software and matching Python bindings, or use `parsed_timebin_data.npz`.
- `data dir not found`: verify `--data` and Windows/WSL path translation.
- `--ttbin is required`: `tdc_layer_scan` no longer has a machine-specific default input file.
- Missing NPZ fields: ensure `Ch` and `TimeTag` are present.
