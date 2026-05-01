"""CLI entry point for the ultra JTI sweep pipeline.

Stage F status: implemented.  Registered as ``jti-ultra-sweep`` console
script in ``pyproject.toml``.
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

import numpy as np

from jti_extract.ultra.accumulators import FixedLatticeAccumulator
from jti_extract.ultra.aperture_select import select_apertures
from jti_extract.ultra.contrast_profiles import (
    build_contrast_profile,
    select_contrast_candidates,
)
from jti_extract.ultra.surrogate_controls import phase_shuffle_multi
from jti_extract.ultra.diagnostics_pairing import (
    method_comparison_summary,
    strict_retention_meta,
)
from jti_extract.ultra.g2_accumulate import all_candidates
from jti_extract.ultra.io_ultra import (
    SWEEP_SUMMARY_FIELDS,
    make_output_dir,
    write_json,
    write_summary_csv,
)
from jti_extract.ultra.svd_estimators import (
    block_bootstrap_coarse_jti,
    svd_coarse_jti,
    truncated_schmidt_summary,
)
from jti_extract.ultra.sweep_ultra_jti import (
    edge_guard_sensitivity_summary,
    method_comparison_sweep,
    origin_sensitivity_summary,
    run_synthetic_sweep_point,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for ``jti-ultra-sweep``."""
    parser = argparse.ArgumentParser(
        prog="jti-ultra-sweep",
        description="Ultra-high-dimensional fixed-lattice G2-like JTI sweep",
    )

    # Data source — --ttbin is mutually exclusive with the pre-loaded array mode.
    # Pre-loaded array mode requires both --t-a and --t-b (validated in _load_timestamps).
    parser.add_argument(
        "--ttbin", type=str, default=None,
        help="TimeTagger binary file path",
    )
    npy = parser.add_argument_group("pre-loaded array mode")
    npy.add_argument(
        "--t-a", "--t_a", type=str, dest="t_a_path", default=None,
        help="Pre-sorted channel A timestamps (npy file) [requires --t-b]",
    )
    npy.add_argument(
        "--t-b", "--t_b", type=str, dest="t_b_path", default=None,
        help="Pre-sorted channel B timestamps (npy file) [requires --t-a]",
    )

    # TTBIN channel selection
    parser.add_argument(
        "--ch-a", "--ch_a", type=int, dest="ch_a", default=1,
        help="Logical channel ID for channel A (default: 1)",
    )
    parser.add_argument(
        "--ch-b", "--ch_b", type=int, dest="ch_b", default=3,
        help="Logical channel ID for channel B (default: 3)",
    )

    # Maximum events
    parser.add_argument(
        "--max-events", "--max_events", type=int, dest="max_events",
        default=None, help="Maximum events to read per channel",
    )

    # Frame lattice
    parser.add_argument(
        "--n-bins", "--n_bins", type=int, dest="n_bins", default=1024,
        help="Number of bins per frame dimension (default: 1024)",
    )
    parser.add_argument(
        "--binwidth-ps", "--binwidth_ps", type=int, dest="bin_width_ps",
        default=100, help="Bin width in ps (default: 100)",
    )
    parser.add_argument(
        "--frame-origin-ps", "--frame_origin_ps", type=float,
        dest="frame_origin_ps", default=0.0,
        help="Global frame origin in ps (default: 0)",
    )

    # Coincidence and edge guard
    parser.add_argument(
        "--coincidence-window-ps", "--coincidence_window_ps", type=int,
        dest="coincidence_window_ps", default=200,
        help="Fixed physical coincidence window in ps (default: 200)",
    )
    parser.add_argument(
        "--edge-guard-ps", "--edge_guard_ps", type=int,
        dest="edge_guard_ps", default=200,
        help="Edge-guard margin in ps (default: 200)",
    )

    # Coarse JTI
    parser.add_argument(
        "--coarse-n-bins", "--coarse_n_bins", type=int,
        dest="coarse_n_bins", default=64,
        help="Coarse JTI dimension (default: 64, 0=skip)",
    )

    # Diagnostics
    parser.add_argument(
        "--origin-sensitivity", "--origin_sensitivity", type=float,
        nargs="*", dest="origin_sensitivity", default=None,
        help="Additional origins for sensitivity check (ps)",
    )
    parser.add_argument(
        "--edge-guard-sensitivity", "--edge_guard_sensitivity", type=int,
        nargs="*", dest="edge_guard_sensitivity", default=None,
        help="Additional edge guards for sensitivity check (ps)",
    )

    # Truncated SVD
    parser.add_argument(
        "--truncated-rank", "--truncated_rank", type=int,
        dest="truncated_rank", default=0,
        help="Truncated SVD rank (default: 0=skip)",
    )

    # Profile-only mode
    parser.add_argument(
        "--profile-only", action="store_true", dest="profile_only",
        help="Profile-only mode: skip coarse JTI accumulation, SVD, and bootstrap",
    )

    # Contrast profile (Stage 20)
    parser.add_argument(
        "--contrast-profile", action="store_true", dest="contrast_profile",
        help="Enable contrast profile: per-segment on-diag vs sideband density",
    )
    parser.add_argument(
        "--contrast-window-ps", "--contrast_window_ps", type=int,
        dest="contrast_window_ps", default=3000,
        help="Expanded coincidence window for contrast diagnostics (ps, default: 3000)",
    )
    parser.add_argument(
        "--on-diag-band-bins", "--on_diag_band_bins", type=int,
        dest="on_diag_band_bins", default=2,
        help="On-diagonal band width in bins (default: 2)",
    )
    parser.add_argument(
        "--bg-inner-bins", "--bg_inner_bins", type=int,
        dest="bg_inner_bins", default=10,
        help="Inner offset for sideband (bins, default: 10)",
    )
    parser.add_argument(
        "--bg-outer-bins", "--bg_outer_bins", type=int,
        dest="bg_outer_bins", default=30,
        help="Outer offset for sideband (bins, default: 30)",
    )
    parser.add_argument(
        "--center-coarse-bins", "--center_coarse_bins", type=int,
        nargs="*", dest="center_coarse_bins", default=[512, 1024],
        help="Number of coarse segments M (default: 512 1024)",
    )

    # Aperture selection (Stage 21)
    parser.add_argument(
        "--select-aperture", action="store_true", dest="select_aperture",
        help="Enable effective temporal aperture selection from contrast profile",
    )
    parser.add_argument(
        "--aperture-threshold", type=str, dest="aperture_threshold",
        default="snr3",
        help="Aperture threshold: snr3, snr5, contrast2, contrast5 (default: snr3)",
    )
    parser.add_argument(
        "--aperture-min-run-segments", type=int, dest="aperture_min_run_segments",
        default=3, help="Minimum consecutive segments for an aperture (default: 3)",
    )
    parser.add_argument(
        "--aperture-max-gap-segments", type=int, dest="aperture_max_gap_segments",
        default=1, help="Maximum gap within an aperture (default: 1)",
    )
    parser.add_argument(
        "--aperture-require-sideband", action="store_true",
        dest="aperture_require_sideband",
        help="Exclude sideband_zero segments from aperture scoring",
    )

    # Phase-shuffle multi (Stage 25C)
    parser.add_argument(
        "--phase-shuffle-n", type=int, dest="phase_shuffle_n",
        default=0, help="Number of phase-shuffle resamples (0=skip, default: 0)",
    )

    # Bootstrap
    parser.add_argument(
        "--bootstrap-n", "--bootstrap_n", type=int,
        dest="bootstrap_n", default=0,
        help="Number of bootstrap resamples (default: 0=skip)",
    )
    parser.add_argument(
        "--bootstrap-block-ps", "--bootstrap_block_ps", type=int,
        dest="bootstrap_block_ps", default=None,
        help="Bootstrap block size in ps",
    )
    parser.add_argument(
        "--bootstrap-seed", "--bootstrap_seed", type=int,
        dest="bootstrap_seed", default=None,
        help="Bootstrap random seed",
    )

    # Output
    parser.add_argument(
        "--out", type=str, default=None,
        help="Output directory (default: auto-generate timestamped dir)",
    )
    parser.add_argument(
        "--prefix", type=str, default="",
        help="Output filename prefix",
    )
    parser.add_argument(
        "--no-csv", action="store_true", dest="no_csv",
        help="Skip CSV output",
    )
    parser.add_argument(
        "--no-json", action="store_true", dest="no_json",
        help="Skip JSON output",
    )
    parser.add_argument(
        "--overwrite", action="store_true", dest="overwrite",
        help="Allow overwriting existing output directory",
    )

    # Execution
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress progress output",
    )
    parser.add_argument(
        "--dry-run", action="store_true", dest="dry_run",
        help="Validate config without processing data",
    )
    parser.add_argument(
        "--self-test", action="store_true", dest="self_test",
        help="Run self-test and exit",
    )

    return parser


# ---------------------------------------------------------------------------
#  Self-test
# ---------------------------------------------------------------------------


def _self_test() -> int:
    """Run a tiny synthetic self-test of the full pipeline."""
    t_a = np.array([100, 200, 300, 1000, 1100], dtype=np.int64)
    t_b = np.array([150, 250, 350, 1050, 1150], dtype=np.int64)
    try:
        result = run_synthetic_sweep_point(
            t_a, t_b,
            n_bins=1024, bin_width_ps=100, frame_origin_ps=0.0,
            coincidence_window_ps=200, edge_guard_ps=0, coarse_n_bins=16,
        )
        # Check that key fields are present
        for key in ("n_candidates_total", "K_coarse", "n_strict_pairs"):
            if key not in result:
                print(f"SELF-TEST FAIL: missing key '{key}'")
                return 1
        print("SELF-TEST PASSED")
        return 0
    except Exception as e:
        print(f"SELF-TEST FAIL: {e}")
        return 1


# ---------------------------------------------------------------------------
#  Main entry point
# ---------------------------------------------------------------------------


def _load_timestamps(args: argparse.Namespace) -> tuple[np.ndarray, np.ndarray, dict]:
    """Load timestamps from the configured data source.

    Validates that pre-loaded array mode provides both channels.
    """
    if args.ttbin is not None:
        if args.t_a_path is not None or args.t_b_path is not None:
            raise ValueError(
                "--ttbin and --t-a/--t-b are mutually exclusive; "
                "choose one data source only."
            )
        from jti_extract.ultra.ttbin_adapter import load_channels_from_ttbin
        t_a, t_b, meta = load_channels_from_ttbin(
            args.ttbin, args.ch_a, args.ch_b, args.max_events,
        )
        return t_a, t_b, meta
    elif args.t_a_path is not None:
        if args.t_b_path is None:
            raise ValueError(
                "--t-a was provided but --t-b is missing; "
                "pre-loaded array mode requires both channels."
            )
        t_a = np.load(args.t_a_path)
        t_b = np.load(args.t_b_path)
        meta: dict = {
            "source": args.t_a_path,
            "n_ch_a": int(t_a.size),
            "n_ch_b": int(t_b.size),
        }
        return t_a, t_b, meta
    elif args.t_b_path is not None:
        raise ValueError(
            "--t-b was provided but --t-a is missing; "
            "pre-loaded array mode requires both channels."
        )
    else:
        raise ValueError("No data source specified")


def _run(args: argparse.Namespace) -> int:
    """Run the ultra sweep."""
    # Load data
    t_a, t_b, src_meta = _load_timestamps(args)

    if not args.quiet:
        print(f"Loaded {t_a.size} events on ch A, {t_b.size} events on ch B")

    # Prepare output directory
    out_dir: Optional[str] = None
    if not args.no_csv or not args.no_json:
        if args.out:
            out_dir = args.out
            # Fail if directory already exists to prevent silent overwrite
            if os.path.exists(out_dir) and not args.overwrite:
                # Allow if it's a timestamped auto-dir (contains ultra_jti_sweep_)
                if not os.path.isdir(out_dir):
                    raise FileExistsError(f"--out path exists and is not a directory: {out_dir}")
                # Check if directory is empty
                if os.listdir(out_dir):
                    raise FileExistsError(
                        f"--out directory already exists and is not empty: {out_dir}. "
                        "Use --overwrite to allow overwriting, or use a unique directory name."
                    )
            os.makedirs(out_dir, exist_ok=True)
        else:
            out_dir = make_output_dir(".", args.prefix)
        if not args.quiet:
            print(f"Output directory: {out_dir}")

    rows: List[Dict[str, Any]] = []

    # Effective coarse_n_bins: if --profile-only, skip coarse JTI
    effective_coarse_n_bins = args.coarse_n_bins if not args.profile_only else 0

    # Main sweep point
    if not args.quiet:
        print("Running main sweep point...")
    main_result = run_synthetic_sweep_point(
        t_a, t_b,
        n_bins=args.n_bins,
        bin_width_ps=args.bin_width_ps,
        frame_origin_ps=args.frame_origin_ps,
        coincidence_window_ps=args.coincidence_window_ps,
        edge_guard_ps=args.edge_guard_ps,
        coarse_n_bins=effective_coarse_n_bins,
    )

    # Contrast profile (Stage 20)
    contrast_cands = None  # cache: (ca, cb, delta) computed once
    if args.contrast_profile:
        if not args.quiet:
            print("Building contrast profile...")
        frame_length_ps = args.n_bins * args.bin_width_ps
        # Compute candidates once, reuse for all M
        ca, cb, delta = select_contrast_candidates(
            t_a, t_b, args.contrast_window_ps
        )
        contrast_cands = (ca, cb, delta)
        for M in args.center_coarse_bins:
            if not args.quiet:
                print(f"  center_coarse_bins = {M}")
            cprof = build_contrast_profile(
                ca, cb, delta,
                n_bins=args.n_bins,
                bin_width_ps=args.bin_width_ps,
                frame_origin_ps=args.frame_origin_ps,
                frame_length_ps=frame_length_ps,
                on_diag_band_bins=args.on_diag_band_bins,
                bg_inner_bins=args.bg_inner_bins,
                bg_outer_bins=args.bg_outer_bins,
                center_coarse_bins=M,
            )
            if out_dir:
                csv_path = os.path.join(
                    out_dir,
                    f"{args.prefix}diag_contrast_profile_{args.n_bins}_M{M}.csv"
                )
                if "segments" in cprof:
                    import csv
                    with open(csv_path, "w", newline="") as f:
                        if cprof["segments"]:
                            writer = csv.DictWriter(f, fieldnames=cprof["segments"][0].keys())
                            writer.writeheader()
                            writer.writerows(cprof["segments"])
                    if not args.quiet:
                        print(f"  Wrote {csv_path}")
                json_path = os.path.join(
                    out_dir,
                    f"{args.prefix}diag_contrast_profile_{args.n_bins}_M{M}.json"
                )
                write_json(json_path, cprof)

    # Stage 21: aperture selection (all thresholds, all M)
    if args.select_aperture and args.contrast_profile:
        if not args.quiet:
            print("Selecting apertures...")
        thresholds = ["snr3", "snr5", "contrast2", "contrast5"]
        all_apertures = {}
        for M in args.center_coarse_bins:
            json_path = os.path.join(
                out_dir, f"{args.prefix}diag_contrast_profile_{args.n_bins}_M{M}.json"
            )
            with open(json_path) as f:
                cprof = json.load(f)
            for thr in thresholds:
                apertures = select_apertures(
                    cprof,
                    threshold=thr,
                    min_run_segments=args.aperture_min_run_segments,
                    max_gap_segments=args.aperture_max_gap_segments,
                    require_sideband=args.aperture_require_sideband,
                )
                key = f"M{M}_{thr}"
                all_apertures[key] = apertures
                if not args.quiet:
                    print(f"  M={M}, {thr}: {len(apertures)} apertures")
        if out_dir:
            # Write per-threshold CSV
            import csv
            for key, apertures in all_apertures.items():
                apertures_csv = [{k: v for k, v in ap.items() if k != "segment_indices"} for ap in apertures]
                csv_path = os.path.join(out_dir, f"{args.prefix}aperture_{key}.csv")
                if apertures_csv:
                    with open(csv_path, "w", newline="") as f:
                        writer = csv.DictWriter(f, fieldnames=apertures_csv[0].keys())
                        writer.writeheader()
                        writer.writerows(apertures_csv)
                    if not args.quiet:
                        print(f"  Wrote {csv_path}")
            # Write combined JSON
            json_path = os.path.join(out_dir, f"{args.prefix}effective_aperture_summary.json")
            write_json(json_path, all_apertures)

    # Stage 25C: phase-shuffle multi
    if args.phase_shuffle_n > 0 and args.contrast_profile:
        if not args.quiet:
            print(f"Running phase-shuffle {args.phase_shuffle_n}x...")
        frame_length_ps = args.n_bins * args.bin_width_ps
        ps_result = phase_shuffle_multi(
            t_a, t_b,
            n_shuffles=args.phase_shuffle_n,
            contrast_window_ps=args.contrast_window_ps,
            n_bins=args.n_bins,
            bin_width_ps=args.bin_width_ps,
            frame_origin_ps=args.frame_origin_ps,
            frame_length_ps=frame_length_ps,
            on_diag_band_bins=args.on_diag_band_bins,
            bg_inner_bins=args.bg_inner_bins,
            bg_outer_bins=args.bg_outer_bins,
            center_coarse_bins=args.center_coarse_bins[0],
        )
        if not args.quiet:
            print(f"  true_max_snr={ps_result['true_max_snr']:.2f}")
            print(f"  shuffle_mean={ps_result['phase_shuffle_max_snr_mean']:.2f} ± {ps_result['phase_shuffle_max_snr_std']:.2f}")
            print(f"  zscore={ps_result['true_zscore_vs_shuffle']:.2f}, percentile={ps_result['true_percentile_vs_shuffle']:.1f}%")
        if out_dir:
            json_path = os.path.join(out_dir, f"{args.prefix}phase_shuffle_multi.json")
            write_json(json_path, ps_result)

    # Add truncated SVD if requested
    if args.truncated_rank > 0 and args.coarse_n_bins > 0 and not args.profile_only:
        ca, cb, _ = all_candidates(t_a, t_b, args.coincidence_window_ps)
        acc = FixedLatticeAccumulator(
            n_bins=args.n_bins, bin_width_ps=args.bin_width_ps,
            frame_origin_ps=args.frame_origin_ps,
            coincidence_window_ps=args.coincidence_window_ps,
            edge_guard_ps=args.edge_guard_ps,
            coarse_n_bins=args.coarse_n_bins,
        )
        acc.add_candidates(ca, cb)
        cjti = acc.coarse_jti
        if cjti is not None and np.sum(cjti) > 0:
            try:
                tsvd = truncated_schmidt_summary(cjti, r=args.truncated_rank)
                main_result.update(tsvd)
            except (ValueError, np.linalg.LinAlgError):
                pass

    # Add bootstrap if requested
    if args.bootstrap_n > 0 and args.coarse_n_bins > 0 and not args.profile_only:
        ca, cb, _ = all_candidates(t_a, t_b, args.coincidence_window_ps)
        bresults = block_bootstrap_coarse_jti(
            candidates_t_a=ca, candidates_t_b=cb,
            n_bins=args.n_bins, bin_width_ps=args.bin_width_ps,
            frame_origin_ps=args.frame_origin_ps,
            coincidence_window_ps=args.coincidence_window_ps,
            edge_guard_ps=args.edge_guard_ps,
            coarse_n_bins=args.coarse_n_bins,
            n_resamples=args.bootstrap_n,
            block_size=args.bootstrap_block_ps,
            seed=args.bootstrap_seed,
        )
        if bresults:
            k_vals = [r["schmidt_number"] for r in bresults]
            main_result["bootstrap_K_mean"] = float(np.mean(k_vals))
            main_result["bootstrap_K_std"] = float(np.std(k_vals))
            main_result["bootstrap_K_relative_std"] = (
                float(np.std(k_vals)) / float(np.mean(k_vals))
                if np.mean(k_vals) > 0 else 0.0
            )
            main_result["bootstrap_n_success"] = float(len(bresults))

    main_result.update(src_meta)
    rows.append(main_result)

    # Origin sensitivity
    origins: List[float] = [args.frame_origin_ps]
    if args.origin_sensitivity:
        origins.extend(args.origin_sensitivity)
    if len(origins) > 1:
        if not args.quiet:
            print(f"Running origin sensitivity ({len(origins)} origins)...")
        for r in origin_sensitivity_summary(
            t_a, t_b,
            origins_ps=origins[1:],
            n_bins=args.n_bins, bin_width_ps=args.bin_width_ps,
            coincidence_window_ps=args.coincidence_window_ps,
            edge_guard_ps=args.edge_guard_ps,
            coarse_n_bins=effective_coarse_n_bins,
        ):
            r.update(src_meta)
            rows.append(r)

    # Edge-guard sensitivity
    edge_guards: List[int] = [args.edge_guard_ps]
    if args.edge_guard_sensitivity:
        edge_guards.extend(args.edge_guard_sensitivity)
    if len(edge_guards) > 1:
        if not args.quiet:
            print(f"Running edge-guard sensitivity ({len(edge_guards)} values)...")
        for r in edge_guard_sensitivity_summary(
            t_a, t_b,
            edge_guards_ps=edge_guards[1:],
            n_bins=args.n_bins, bin_width_ps=args.bin_width_ps,
            frame_origin_ps=args.frame_origin_ps,
            coincidence_window_ps=args.coincidence_window_ps,
            coarse_n_bins=effective_coarse_n_bins,
        ):
            r.update(src_meta)
            rows.append(r)

    # Write output
    if out_dir:
        if not args.no_csv:
            csv_path = os.path.join(out_dir, f"{args.prefix}ultra_summary.csv")
            write_summary_csv(csv_path, rows)
            if not args.quiet:
                print(f"Wrote {csv_path}")
        if not args.no_json:
            json_path = os.path.join(out_dir, f"{args.prefix}ultra_summary.json")
            write_json(json_path, rows)
            if not args.quiet:
                print(f"Wrote {json_path}")

    return 0


def main() -> int:
    """Main entry point for ``jti-ultra-sweep``."""
    parser = build_parser()
    args = parser.parse_args()

    if args.self_test:
        return _self_test()

    if args.dry_run:
        print("DRY RUN: config validated, no data processed")
        return 0

    return _run(args)


if __name__ == "__main__":
    sys.exit(main())
