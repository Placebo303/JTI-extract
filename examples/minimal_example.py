#!/usr/bin/env python3
"""
Minimal example: Extract JTI matrix from simulated data.

This example demonstrates the basic usage of jti-extract with simulated data.
No hardware or real data required.

Usage:
    python examples/minimal_example.py
"""

import numpy as np
from pathlib import Path

# Add src to path for local development
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from jti_extract.cli.extract import _time_tags_to_bins, _jti_from_pairs
from jti_extract.cli.schmidt import compute_schmidt_number_from_jti


def main():
    print("=" * 60)
    print("JTI-extract: Minimal Example")
    print("=" * 60)
    
    # Step 1: Generate simulated data
    print("\n[1/4] Generating simulated data...")
    
    # Create synthetic timestamps with correlation
    n_events = 50000
    dimensions = 40
    binwidth_ps = 40
    
    # Generate correlated timestamps (simulates entangled photon pairs)
    timestamps_A = np.random.uniform(0, dimensions * binwidth_ps, n_events)
    # B is correlated with A (diagonal correlation)
    noise = np.random.normal(0, binwidth_ps * 2, n_events)
    timestamps_B = timestamps_A + noise
    
    print(f"  Generated {n_events} events")
    print(f"  Dimensions: {dimensions}")
    print(f"  Bin width: {binwidth_ps} ps")
    
    # Step 2: Bin timestamps into JTI matrix
    print("\n[2/4] Binning timestamps into JTI matrix...")
    
    # Convert timestamps to bin indices
    bins_A = _time_tags_to_bins(timestamps_A, bin_width_ps=binwidth_ps, frame_origin_ps=0)
    bins_B = _time_tags_to_bins(timestamps_B, bin_width_ps=binwidth_ps, frame_origin_ps=0)
    
    # Create pairs array
    pairs = np.column_stack([bins_A, bins_B])
    
    # Create JTI matrix
    jti = _jti_from_pairs(pairs, n_bins=dimensions)
    
    print(f"  JTI matrix shape: {jti.shape}")
    print(f"  Total counts: {jti.sum()}")
    print(f"  Non-zero bins: {np.count_nonzero(jti)}")
    
    # Step 3: Compute Schmidt number
    print("\n[3/4] Computing Schmidt number...")
    
    result = compute_schmidt_number_from_jti(jti)
    
    print(f"  Schmidt number (K): {result['schmidt_number']:.3f}")
    print(f"  Purity: {result['purity']:.6f}")
    print(f"  Singular values: {result['n_singular_values']}")
    
    # Step 4: Save results
    print("\n[4/4] Saving results...")
    
    out_dir = Path('examples/output')
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Save JTI matrix
    np.savetxt(out_dir / 'minimal_jti.csv', jti, delimiter=',', fmt='%d')
    print(f"  Saved: {out_dir / 'minimal_jti.csv'}")
    
    # Save summary
    with open(out_dir / 'minimal_summary.txt', 'w') as f:
        f.write("JTI-extract Minimal Example Results\n")
        f.write("=" * 40 + "\n\n")
        f.write(f"Dimensions: {dimensions}\n")
        f.write(f"Bin width: {binwidth_ps} ps\n")
        f.write(f"Total counts: {jti.sum()}\n")
        f.write(f"Non-zero bins: {np.count_nonzero(jti)}\n\n")
        f.write(f"Schmidt number (K): {result['schmidt_number']:.3f}\n")
        f.write(f"Purity: {result['purity']:.6f}\n")
        f.write(f"Singular values: {result['n_singular_values']}\n")
    print(f"  Saved: {out_dir / 'minimal_summary.txt'}")
    
    print("\n" + "=" * 60)
    print("Done! Results saved to examples/output/")
    print("=" * 60)


if __name__ == '__main__':
    main()
