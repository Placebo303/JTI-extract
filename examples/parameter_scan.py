#!/usr/bin/env python3
"""
Parameter scan example: Explore JTI extraction parameters.

This example demonstrates how different parameters affect JTI extraction results.
Useful for optimizing binwidth, dimensions, and other settings.

Usage:
    python examples/parameter_scan.py
"""

import numpy as np
from pathlib import Path
import itertools

# Add src to path for local development
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from jti_extract.cli.extract import _time_tags_to_bins, _jti_from_pairs
from jti_extract.cli.schmidt import compute_schmidt_number_from_jti


def generate_correlated_timestamps(n_events: int, correlation_strength: float = 0.8):
    """Generate correlated timestamp pairs."""
    timestamps_A = np.random.uniform(0, 10000, n_events)
    noise = np.random.normal(0, 1000 * (1 - correlation_strength), n_events)
    timestamps_B = timestamps_A + noise
    return timestamps_A, timestamps_B


def extract_jti(timestamps_A, timestamps_B, binwidth_ps, dimensions):
    """Extract JTI matrix from timestamps."""
    bins_A = _time_tags_to_bins(timestamps_A, bin_width_ps=binwidth_ps, frame_origin_ps=0)
    bins_B = _time_tags_to_bins(timestamps_B, bin_width_ps=binwidth_ps, frame_origin_ps=0)
    
    pairs = np.column_stack([bins_A, bins_B])
    jti = _jti_from_pairs(pairs, n_bins=dimensions)
    
    return jti


def main():
    print("=" * 60)
    print("JTI-extract: Parameter Scan Example")
    print("=" * 60)
    
    # Generate test data
    print("\n[1/3] Generating test data...")
    n_events = 100000
    timestamps_A, timestamps_B = generate_correlated_timestamps(n_events, 0.7)
    print(f"  Generated {n_events} events")
    
    # Define parameter ranges
    binwidth_values = [20, 40, 80, 160]
    dimensions_values = [40, 80, 120, 160]
    
    print(f"\n[2/3] Scanning parameters...")
    print(f"  Bin widths: {binwidth_values}")
    print(f"  Dimensions: {dimensions_values}")
    
    # Run parameter scan
    results = []
    total_combinations = len(binwidth_values) * len(dimensions_values)
    
    for i, (binwidth, dims) in enumerate(itertools.product(binwidth_values, dimensions_values)):
        print(f"\n  [{i+1}/{total_combinations}] binwidth={binwidth}ps, dimensions={dims}")
        
        # Extract JTI
        jti = extract_jti(timestamps_A, timestamps_B, binwidth, dims)
        
        # Compute Schmidt number
        result = compute_schmidt_number_from_jti(jti)
        
        # Store results
        results.append({
            'binwidth_ps': binwidth,
            'dimensions': dims,
            'total_counts': int(jti.sum()),
            'nonzero_bins': int(np.count_nonzero(jti)),
            'schmidt_number': result['schmidt_number'],
            'purity': result['purity'],
            'n_singular_values': result['n_singular_values']
        })
        
        print(f"    K={result['schmidt_number']:.3f}, purity={result['purity']:.6f}")
    
    # Save results
    print(f"\n[3/3] Saving results...")
    
    out_dir = Path('examples/output')
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Save as CSV
    csv_path = out_dir / 'parameter_scan_results.csv'
    with open(csv_path, 'w') as f:
        # Header
        f.write(','.join(results[0].keys()) + '\n')
        # Data
        for r in results:
            f.write(','.join(str(v) for v in r.values()) + '\n')
    
    print(f"  Saved: {csv_path}")
    
    # Print summary table
    print("\n" + "=" * 60)
    print("Parameter Scan Summary")
    print("=" * 60)
    print(f"{'Binwidth':>10} {'Dims':>8} {'K':>10} {'Purity':>12} {'Counts':>10}")
    print("-" * 60)
    for r in results:
        print(f"{r['binwidth_ps']:>10} {r['dimensions']:>8} {r['schmidt_number']:>10.3f} {r['purity']:>12.6f} {r['total_counts']:>10}")
    
    # Find optimal parameters
    best_k = max(results, key=lambda x: x['schmidt_number'])
    print(f"\nOptimal parameters (highest K):")
    print(f"  Binwidth: {best_k['binwidth_ps']} ps")
    print(f"  Dimensions: {best_k['dimensions']}")
    print(f"  Schmidt number: {best_k['schmidt_number']:.3f}")
    
    print(f"\nDone! Results saved to {out_dir}")


if __name__ == '__main__':
    main()
