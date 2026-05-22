# Workflows

## Workflow 1: Extract JTI From NPZ

```bash
python extract_jti.py --data "<path/to/dataset>" --binwidth-ps 200 --dimensions 32 --frame-origin-ps 0 --out results/jti_npz
```

## Workflow 2: Extract JTI From TTBIN

```bash
python extract_jti.py --data "<path/to/dataset>" --ttbin "<path/to/data.ttbin>" --prefer-ttbin --binwidth-ps 200 --dimensions 32 --frame-origin-ps 0 --out results/jti_ttbin
```

For dense JTI extraction from coincidence-window pairs instead of strict single-hit frames:

```bash
python extract_jti.py --data "<path/to/dataset>" --ttbin "<path/to/data.ttbin>" --raw-ch-a-id 1 --raw-ch-b-id 3 --pairing-mode all_pairs_window --coincidence-window-ps 200 --binwidth-ps 400 --dimensions 4500 --frame-origin-ps 0 --npz --plot-diagonal-profile --out results/jti_window
```

## Workflow 3: Compute Schmidt Number

```bash
python compute_jti_schmidt.py --input results/jti_npz --recursive --pattern "*.counts.csv"
```

## Workflow 4: Diagnose 40ps Residue

```bash
python tdc_residue_diagnostics.py --ttbin "<path/to/data.ttbin>" --ch1 1 --ch3 3 --out results/tdc_residue
```

## Workflow 5: Layer Scan Diagnostics

```bash
python tdc_layer_scan.py --ttbin "<path/to/data.ttbin>" --ch-a 1 --ch-b 3 --window-ps 1000 --out results/tdc_layer_scan
```

## Workflow 6: Coincidence Timeline Stability

```bash
python scripts/analyze_ttbin_coincidence_timeline.py --input "<path/to/data.ttbin>" --channels 1 3 --coinc-window-ps 200 --pairing-mode all_pairs --time-bin-s 0.01 --output-dir results/coincidence_timeline
```

This diagnostic plots coincidence midpoint rate versus absolute acquisition time. It is intended for stability, drift, burst-noise, and rate-modulation checks, not frame-folded JTI generation.
