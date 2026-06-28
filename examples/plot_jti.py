#!/usr/bin/env python3
"""
Plot JTI results: Publication-quality visualizations.

This example demonstrates how to create publication-quality plots from JTI extraction results.

Usage:
    python examples/plot_jti.py --input examples/output/minimal_jti.csv --output figures/
"""

import argparse
import numpy as np
from pathlib import Path

# Add src to path for local development
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

try:
    import matplotlib.pyplot as plt
    import matplotlib.colors as colors
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("Warning: matplotlib not installed. Install with: pip install matplotlib")


def plot_jti_heatmap(ax, jti, binwidth_ps=40, cmap='viridis', log_scale=False):
    """
    Plot JTI matrix as heatmap.
    
    Args:
        ax: matplotlib axes object
        jti: JTI matrix (2D array)
        binwidth_ps: Bin width in picoseconds
        cmap: Colormap name
        log_scale: Use logarithmic scale
    """
    dimensions = jti.shape[0]
    
    # Create time axes
    time_A = np.arange(dimensions) * binwidth_ps
    time_B = np.arange(dimensions) * binwidth_ps
    
    # Apply log scale if requested
    if log_scale:
        jti_plot = np.log10(jti + 1)
        label = 'log₁₀(counts + 1)'
    else:
        jti_plot = jti
        label = 'Counts'
    
    # Plot heatmap
    im = ax.pcolormesh(time_A, time_B, jti_plot, cmap=cmap, shading='auto')
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, label=label)
    
    # Labels
    ax.set_xlabel('Time A (ps)')
    ax.set_ylabel('Time B (ps)')
    ax.set_title('Joint Time-Intensity Distribution')
    
    # Equal aspect ratio
    ax.set_aspect('equal')
    
    return im


def plot_svd_spectrum(ax, jti):
    """
    Plot singular value spectrum.
    
    Args:
        ax: matplotlib axes object
        jti: JTI matrix (2D array)
    """
    # Compute SVD
    U, S, Vt = np.linalg.svd(jti)
    
    # Normalize
    S_norm = S / S.sum()
    
    # Plot
    ax.semilogy(S_norm, 'b.-', linewidth=2, markersize=8)
    ax.set_xlabel('Singular Value Index')
    ax.set_ylabel('Normalized Singular Value')
    ax.set_title('SVD Spectrum')
    ax.grid(True, alpha=0.3)
    
    # Add Schmidt number annotation
    K = 1.0 / np.sum(S_norm**2)
    ax.text(0.95, 0.95, f'K = {K:.2f}', 
            transform=ax.transAxes, ha='right', va='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    return S_norm


def plot_diagonal_profile(ax, jti, binwidth_ps=40):
    """
    Plot diagonal profile of JTI matrix.
    
    Args:
        ax: matplotlib axes object
        jti: JTI matrix (2D array)
        binwidth_ps: Bin width in picoseconds
    """
    dimensions = jti.shape[0]
    
    # Extract diagonal
    diagonal = np.diag(jti)
    
    # Create time axis
    time = np.arange(dimensions) * binwidth_ps
    
    # Plot
    ax.plot(time, diagonal, 'b-', linewidth=2)
    ax.fill_between(time, diagonal, alpha=0.3)
    ax.set_xlabel('Time (ps)')
    ax.set_ylabel('Counts')
    ax.set_title('Diagonal Profile')
    ax.grid(True, alpha=0.3)


def plot_anti_diagonal_profile(ax, jti, binwidth_ps=40):
    """
    Plot anti-diagonal profile of JTI matrix.
    
    Args:
        ax: matplotlib axes object
        jti: JTI matrix (2D array)
        binwidth_ps: Bin width in picoseconds
    """
    dimensions = jti.shape[0]
    
    # Extract anti-diagonal
    anti_diag = np.diag(np.fliplr(jti))
    
    # Create time axis
    time = np.arange(dimensions) * binwidth_ps
    
    # Plot
    ax.plot(time, anti_diag, 'r-', linewidth=2)
    ax.fill_between(time, anti_diag, alpha=0.3, color='red')
    ax.set_xlabel('Time (ps)')
    ax.set_ylabel('Counts')
    ax.set_title('Anti-Diagonal Profile')
    ax.grid(True, alpha=0.3)


def main():
    parser = argparse.ArgumentParser(description='Plot JTI results')
    parser.add_argument('--input', type=str, required=True,
                        help='Input JTI matrix (CSV or NPZ)')
    parser.add_argument('--output', type=str, default='figures',
                        help='Output directory (default: figures)')
    parser.add_argument('--binwidth-ps', type=int, default=40,
                        help='Bin width in picoseconds (default: 40)')
    parser.add_argument('--format', type=str, default='png', choices=['png', 'pdf', 'svg'],
                        help='Output format (default: png)')
    parser.add_argument('--dpi', type=int, default=300,
                        help='Resolution in DPI (default: 300)')
    parser.add_argument('--log-scale', action='store_true',
                        help='Use logarithmic scale for heatmap')
    
    args = parser.parse_args()
    
    if not HAS_MATPLOTLIB:
        print("Error: matplotlib is required for plotting.")
        print("Install with: pip install matplotlib")
        return
    
    # Load JTI matrix
    print(f"Loading JTI matrix from {args.input}...")
    input_path = Path(args.input)
    
    if input_path.suffix == '.npz':
        data = np.load(input_path)
        jti = data['jti']
    elif input_path.suffix == '.csv':
        jti = np.loadtxt(input_path, delimiter=',')
    else:
        print(f"Error: Unsupported file format: {input_path.suffix}")
        return
    
    print(f"  JTI matrix shape: {jti.shape}")
    print(f"  Total counts: {jti.sum()}")
    
    # Create output directory
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Create figure with subplots
    print("Creating plots...")
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    
    # Plot 1: JTI Heatmap
    print("  [1/4] JTI heatmap...")
    plot_jti_heatmap(axes[0, 0], jti, args.binwidth_ps, log_scale=args.log_scale)
    
    # Plot 2: SVD Spectrum
    print("  [2/4] SVD spectrum...")
    plot_svd_spectrum(axes[0, 1], jti)
    
    # Plot 3: Diagonal Profile
    print("  [3/4] Diagonal profile...")
    plot_diagonal_profile(axes[1, 0], jti, args.binwidth_ps)
    
    # Plot 4: Anti-Diagonal Profile
    print("  [4/4] Anti-diagonal profile...")
    plot_anti_diagonal_profile(axes[1, 1], jti, args.binwidth_ps)
    
    # Add overall title
    fig.suptitle('JTI Analysis Results', fontsize=16, fontweight='bold')
    
    # Adjust layout
    plt.tight_layout()
    
    # Save figure
    output_path = out_dir / f'jti_analysis.{args.format}'
    plt.savefig(output_path, dpi=args.dpi, bbox_inches='tight')
    print(f"  Saved: {output_path}")
    
    # Create individual plots
    print("\nCreating individual plots...")
    
    # Individual heatmap
    fig_heat, ax_heat = plt.subplots(figsize=(8, 6))
    plot_jti_heatmap(ax_heat, jti, args.binwidth_ps, log_scale=args.log_scale)
    plt.tight_layout()
    heat_path = out_dir / f'jti_heatmap.{args.format}'
    plt.savefig(heat_path, dpi=args.dpi, bbox_inches='tight')
    print(f"  Saved: {heat_path}")
    
    # Individual SVD spectrum
    fig_svd, ax_svd = plt.subplots(figsize=(8, 6))
    plot_svd_spectrum(ax_svd, jti)
    plt.tight_layout()
    svd_path = out_dir / f'jti_svd_spectrum.{args.format}'
    plt.savefig(svd_path, dpi=args.dpi, bbox_inches='tight')
    print(f"  Saved: {svd_path}")
    
    print(f"\nDone! Plots saved to {out_dir}")


if __name__ == '__main__':
    main()
