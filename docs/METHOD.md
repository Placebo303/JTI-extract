# Method: JTI Extraction from Time-Tag Data

## 1. Introduction

Joint Time-Intensity (JTI) extraction is a technique for characterizing temporal correlations in quantum optics experiments. This document describes the mathematical formulation and algorithms implemented in the `jti-extract` toolkit.

## 2. Mathematical Formulation

### 2.1 JTI Matrix Definition

The JTI matrix $H(t_A, t_B)$ represents the joint probability distribution of photon detection times at two detectors A and B:

$$H(t_A, t_B) = \sum_{i} \delta(t - t_A^{(i)}) \delta(t - t_B^{(i)})$$

where $t_A^{(i)}$ and $t_B^{(i)}$ are the detection times of the $i$-th coincidence event.

In discrete form with bin width $\Delta t$:

$$H[m, n] = \#\{(t_A, t_B) : m\Delta t \leq t_A < (m+1)\Delta t, \ n\Delta t \leq t_B < (n+1)\Delta t\}$$

### 2.2 Raw-Aligned Coordinate Calibration

The raw-aligned algorithm performs coordinate calibration without mode selection or structural rearrangement:

1. **Peak Detection**: Identify the brightest peak in the residual delay histogram from `pminus_peaks.csv`
2. **Alignment Offset**: Calculate alignment offset $\tau_{\text{align}}$ from the peak position
3. **Global B-Channel Correction**: Apply correction to all B-channel timestamps:
   $$t_B^{\text{corr}} = t_B - \tau_{\text{align}}$$
4. **Residual Delay Filtering**: Select events within the specified delay window:
   $$\text{delay\_min} \leq (t_B^{\text{corr}} - t_A) \leq \text{delay\_max}$$
5. **Frame Binning**: Apply frame coordinates + edge guard + binning to produce $H_{\text{raw\_aligned}}$

### 2.3 SVD/K Schmidt Number Computation

The Schmidt number $K$ quantifies the effective dimensionality of the JTI matrix:

1. **Singular Value Decomposition**: Compute SVD of the JTI matrix:
   $$H = U \Sigma V^T$$
   where $\Sigma = \text{diag}(\sigma_1, \sigma_2, \ldots, \sigma_n)$

2. **Normalized Singular Values**: 
   $$\tilde{\sigma}_i = \frac{\sigma_i}{\sum_j \sigma_j}$$

3. **Schmidt Number**:
   $$K = \frac{1}{\sum_i \tilde{\sigma}_i^2}$$

4. **Purity**:
   $$P = \sum_i \tilde{\sigma}_i^2 = \frac{1}{K}$$

The Schmidt number $K$ ranges from 1 (product state) to $n$ (maximally entangled state).

## 3. TDC 40ps Residue Diagnostics

### 3.1 Residue Detection

The Time-to-Digital Converter (TDC) exhibits a periodic residue pattern with period 40ps. This is a hardware limitation that manifests as:

- Peaks in the residual delay histogram at multiples of 40ps
- Artifacts in the JTI matrix diagonal structure
- Periodic modulation in the arrival-time distribution

### 3.2 Layer-by-Layer Analysis

The diagnostics tool performs layer-by-layer analysis:

1. **Singles Distribution**: Analyze individual channel arrival times
2. **Pair dt Distribution**: Analyze time differences between paired detections
3. **Residue Quantification**: Measure residue amplitude and periodicity
4. **Layer Scan**: Scan through TDC layers to identify optimal operating point

## 4. Implementation Details

### 4.1 Data Loading

The toolkit supports three input formats:

| Format | Loader | Description |
|--------|--------|-------------|
| `.ttbin` | `TimeTagger` API | Swabian binary format |
| `.npz` | `numpy.load` | NumPy compressed arrays |
| `.csv` | `pandas.read_csv` | Time-tag CSV |

### 4.2 Binning Algorithm

The binning algorithm converts continuous timestamps to discrete bins:

```python
def bin_timestamps(timestamps_ps, binwidth_ps, dimensions, frame_origin_ps=0):
    """Convert timestamps to bin indices."""
    # Relative to frame origin
    t_rel = timestamps_ps - frame_origin_ps
    
    # Bin index
    bin_idx = np.floor(t_rel / binwidth_ps).astype(int)
    
    # Filter valid bins
    valid = (bin_idx >= 0) & (bin_idx < dimensions)
    
    return bin_idx[valid]
```

### 4.3 Visualization

The plotting module provides publication-quality visualizations:

- **Heatmap**: 2D JTI matrix visualization with configurable colormap
- **SVD Spectrum**: Singular value distribution on log scale
- **Residual Histogram**: Time difference distribution with residue markers

## 5. Validation

### 5.1 Simulated Data Tests

The test suite includes simulated data with known properties:

- **Product State**: $K = 1$ (no correlations)
- **Maximally Entangled State**: $K = n$ (perfect correlations)
- **Noisy State**: $K < n$ with controllable noise level

### 5.2 Real Data Comparison

Validation against real experimental data:

- **SPDC Source**: Type-II spontaneous parametric down-conversion
- **TimeTagger**: Swabian TimeTagger Ultra with 40ps resolution
- **Expected Schmidt Number**: $K \approx 2$ for polarization-entangled pairs

## References

1. Horodecki, R., Horodecki, P., Horodecki, M., & Horodecki, K. (2009). Quantum entanglement. *Reviews of Modern Physics*, 81(2), 865.
2. Sackett, C. A., et al. (2000). Experimental entanglement of four particles. *Nature*, 404(6775), 256-259.
3. Pan, J. W., et al. (2012). Multiphoton entanglement and interferometry. *Reviews of Modern Physics*, 84(2), 777.
