#!/usr/bin/env python3
"""
Generate simulated JTI data for testing and examples.

This script creates synthetic time-tag data with known properties:
- Controllable Schmidt number (K)
- Adjustable noise level
- Known diagonal correlation structure

Usage:
    python examples/generate_simulated_data.py --out examples/data/
"""

import argparse
import numpy as np
from pathlib import Path


def generate_jti_matrix(dimensions: int = 80, schmidt_number: float = 2.0, 
                        noise_level: float = 0.1, total_counts: int = 100000) -> np.ndarray:
    """
    Generate a synthetic JTI matrix with known Schmidt number.
    
    Args:
        dimensions: Size of the JTI matrix (dimensions x dimensions)
        schmidt_number: Target Schmidt number (1 = product state, n = maximally entangled)
        noise_level: Fraction of uniform noise to add (0 = pure state, 1 = all noise)
        total_counts: Total number of coincidence counts
    
    Returns:
        JTI matrix with shape (dimensions, dimensions)
    """
    # Create base correlation structure
    # Diagonal correlation for entangled state
    jti = np.zeros((dimensions, dimensions))
    
    # Add diagonal correlation (simulates time-frequency entanglement)
    for i in range(dimensions):
        for j in range(dimensions):
            # Correlation strength decreases with distance from diagonal
            distance = abs(i - j)
            correlation = np.exp(-distance**2 / (2 * (schmidt_number * 5)**2))
            jti[i, j] = correlation
    
    # Add anti-diagonal correlation (simulates energy-time entanglement)
    for i in range(dimensions):
        for j in range(dimensions):
            distance = abs(i + j - dimensions + 1)
            correlation = np.exp(-distance**2 / (2 * (schmidt_number * 3)**2))
            jti[i, j] += correlation * 0.5
    
    # Add uniform noise
    noise = np.random.uniform(0, 1, (dimensions, dimensions))
    jti = (1 - noise_level) * jti + noise_level * noise
    
    # Normalize to total counts
    jti = jti / jti.sum() * total_counts
    
    # Add Poisson noise
    jti = np.random.poisson(jti).astype(float)
    
    return jti


def generate_time_tags(jti_matrix: np.ndarray, binwidth_ps: int = 40) -> dict:
    """
    Generate time-tag data from JTI matrix.
    
    Args:
        jti_matrix: JTI coincidence matrix
        binwidth_ps: Bin width in picoseconds
    
    Returns:
        Dictionary with timestamps_A and timestamps_B arrays
    """
    dimensions = jti_matrix.shape[0]
    
    # Generate timestamps from JTI matrix
    timestamps_A = []
    timestamps_B = []
    
    for i in range(dimensions):
        for j in range(dimensions):
            count = int(jti_matrix[i, j])
            if count > 0:
                # Generate timestamps within each bin
                t_A = i * binwidth_ps + np.random.uniform(0, binwidth_ps, count)
                t_B = j * binwidth_ps + np.random.uniform(0, binwidth_ps, count)
                timestamps_A.extend(t_A)
                timestamps_B.extend(t_B)
    
    return {
        'timestamps_A': np.array(timestamps_A),
        'timestamps_B': np.array(timestamps_B)
    }


def main():
    parser = argparse.ArgumentParser(description='Generate simulated JTI data')
    parser.add_argument('--dimensions', type=int, default=80,
                        help='JTI matrix dimensions (default: 80)')
    parser.add_argument('--binwidth-ps', type=int, default=40,
                        help='Bin width in picoseconds (default: 40)')
    parser.add_argument('--schmidt-number', type=float, default=2.0,
                        help='Target Schmidt number (default: 2.0)')
    parser.add_argument('--noise-level', type=float, default=0.1,
                        help='Noise level 0-1 (default: 0.1)')
    parser.add_argument('--total-counts', type=int, default=100000,
                        help='Total coincidence counts (default: 100000)')
    parser.add_argument('--out', type=str, default='examples/data',
                        help='Output directory (default: examples/data)')
    
    args = parser.parse_args()
    
    # Create output directory
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Generating simulated JTI data...")
    print(f"  Dimensions: {args.dimensions}")
    print(f"  Bin width: {args.binwidth_ps} ps")
    print(f"  Target Schmidt number: {args.schmidt_number}")
    print(f"  Noise level: {args.noise_level}")
    print(f"  Total counts: {args.total_counts}")
    
    # Generate JTI matrix
    jti = generate_jti_matrix(
        dimensions=args.dimensions,
        schmidt_number=args.schmidt_number,
        noise_level=args.noise_level,
        total_counts=args.total_counts
    )
    
    # Save JTI matrix as CSV
    jti_csv_path = out_dir / 'simulated_jti.csv'
    np.savetxt(jti_csv_path, jti, delimiter=',', fmt='%d')
    print(f"  Saved JTI matrix: {jti_csv_path}")
    
    # Save JTI matrix as NPZ
    jti_npz_path = out_dir / 'simulated_jti.npz'
    np.savez(jti_npz_path, jti=jti, 
             dimensions=args.dimensions,
             binwidth_ps=args.binwidth_ps,
             schmidt_number=args.schmidt_number,
             noise_level=args.noise_level)
    print(f"  Saved JTI matrix: {jti_npz_path}")
    
    # Compute actual Schmidt number
    U, S, Vt = np.linalg.svd(jti)
    S_norm = S / S.sum()
    actual_k = 1.0 / np.sum(S_norm**2)
    purity = np.sum(S_norm**2)
    
    print(f"\nActual properties:")
    print(f"  Schmidt number: {actual_k:.3f}")
    print(f"  Purity: {purity:.6f}")
    print(f"  Singular values: {len(S)}")
    
    # Save summary
    summary_path = out_dir / 'simulated_summary.csv'
    with open(summary_path, 'w') as f:
        f.write("parameter,value\n")
        f.write(f"dimensions,{args.dimensions}\n")
        f.write(f"binwidth_ps,{args.binwidth_ps}\n")
        f.write(f"target_schmidt_number,{args.schmidt_number}\n")
        f.write(f"actual_schmidt_number,{actual_k:.6f}\n")
        f.write(f"purity,{purity:.6f}\n")
        f.write(f"noise_level,{args.noise_level}\n")
        f.write(f"total_counts,{args.total_counts}\n")
    print(f"  Saved summary: {summary_path}")
    
    print(f"\nDone! Files saved to {out_dir}")


if __name__ == '__main__':
    main()
