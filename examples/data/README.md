# Example Data

This directory contains example data files for testing and demonstration.

## Files

| File | Description | Source |
|------|-------------|--------|
| `simulated_jti.csv` | Simulated JTI matrix | `generate_simulated_data.py` |
| `simulated_jti.npz` | Simulated JTI matrix (NumPy format) | `generate_simulated_data.py` |
| `simulated_summary.csv` | Simulation parameters and results | `generate_simulated_data.py` |

## Generating Example Data

To regenerate the example data:

```bash
python examples/generate_simulated_data.py --out examples/data/
```

### Custom Parameters

```bash
python examples/generate_simulated_data.py \
  --dimensions 100 \
  --binwidth-ps 20 \
  --schmidt-number 3.0 \
  --noise-level 0.05 \
  --total-counts 500000 \
  --out examples/data/
```

## Data Format

### JTI Matrix (CSV)

Square matrix where cell (i, j) represents the number of coincidence events in bin (i, j).

```
0,1,2,3,...
1,45,67,23,...
2,67,89,34,...
3,23,34,56,...
...
```

### JTI Matrix (NPZ)

NumPy compressed format with metadata:

```python
data = np.load('simulated_jti.npz')
jti = data['jti']  # JTI matrix
dimensions = data['dimensions']  # Matrix dimensions
binwidth_ps = data['binwidth_ps']  # Bin width
schmidt_number = data['schmidt_number']  # Target Schmidt number
noise_level = data['noise_level']  # Noise level
```

### Summary CSV

```csv
parameter,value
dimensions,80
binwidth_ps,40
target_schmidt_number,2.0
actual_schmidt_number,1.876543
purity,0.532987
noise_level,0.1
total_counts,100000
```

## Using Real Data

For real experimental data, use the following formats:

1. **Swabian TimeTagger (.ttbin)**: Direct from hardware
2. **NumPy (.npz)**: Pre-processed time-tag arrays
3. **CSV**: Time-tag data with columns `timestamp_ps`, `channel`

See [docs/DATA_CONTRACT.md](../docs/DATA_CONTRACT.md) for detailed format specifications.
