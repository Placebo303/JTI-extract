"""IO helpers for ultra JTI sweep output.

Supports in-memory dict → CSV/JSON/YAML serialisation for the
ultra pipeline output schema.

Stage F status: implemented.  Does not yet handle NPZ output.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np


# ---------------------------------------------------------------------------
#  Output schema field definitions
# ---------------------------------------------------------------------------

# Fields that every sweep-point summary dict must contain.
SWEEP_SUMMARY_FIELDS: List[str] = [
    # frame lattice
    "n_bins",
    "bin_width_ps",
    "frame_origin_ps",
    "frame_length_ps",
    "coincidence_window_ps",
    "edge_guard_ps",
    "coarse_n_bins",
    # candidate counts
    "n_candidates_total",
    "n_candidates_after_edge_guard",
    "edge_rejection_ratio",
    # method comparison
    "n_candidates_all",
    "n_nearest_pairs",
    "n_greedy_unique_pairs",
    "all_vs_nearest_ratio",
    "all_vs_greedy_ratio",
    # strict retention
    "n_events_ch_a",
    "n_events_ch_b",
    "n_strict_pairs",
    "single_hit_retention_ratio_a",
    "single_hit_retention_ratio_b",
    # SVD (coarse JTI)
    "K_coarse",
    "svd_purity",
    "svd_largest_weight",
    "svd_n_singular_values",
    "svd_nonzero_bins",
]

# Truncated SVD fields (optional).
TRUNCATED_SVD_FIELDS: List[str] = [
    "K_truncated_r",
    "r_truncated",
    "captured_frobenius_energy_r",
]

# Bootstrap fields (optional).
BOOTSTRAP_FIELDS: List[str] = [
    "bootstrap_K_mean",
    "bootstrap_K_std",
    "bootstrap_K_relative_std",
    "bootstrap_n_success",
]


# ---------------------------------------------------------------------------
#  Output directory creation
# ---------------------------------------------------------------------------


def make_output_dir(base_dir: str, prefix: str = "") -> str:
    """Create a timestamped output directory.

    Parameters
    ----------
    base_dir : str
        Parent directory.
    prefix : str
        Optional prefix.

    Returns
    -------
    str
        Path to the created directory.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dirname = f"{prefix}ultra_jti_sweep_{ts}" if prefix else f"ultra_jti_sweep_{ts}"
    path = os.path.join(base_dir, dirname)
    os.makedirs(path, exist_ok=False)  # fail if already exists
    return path


# ---------------------------------------------------------------------------
#  Summary CSV writing
# ---------------------------------------------------------------------------


def write_summary_csv(
    path: str,
    rows: List[Dict[str, Any]],
    fields: Optional[List[str]] = None,
) -> None:
    """Write sweep-point summary rows to CSV.

    Parameters
    ----------
    path : str
        Output CSV path.
    rows : list of dict
        Each dict should contain the same keys.
    fields : list of str, optional
        Column order.  Defaults to SWEEP_SUMMARY_FIELDS.
    """
    if fields is None:
        fields = SWEEP_SUMMARY_FIELDS
    # Determine all columns present across all rows
    all_keys: list[str] = list(fields) if fields else []
    if not fields:
        seen: set[str] = set()
        for row in rows:
            for k in row:
                if k not in seen:
                    seen.add(k)
                    all_keys.append(k)
    import csv
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            clean = {k: v for k, v in row.items() if k in all_keys}
            writer.writerow(clean)


# ---------------------------------------------------------------------------
#  JSON writing
# ---------------------------------------------------------------------------


def write_json(path: str, data: Any, indent: int = 2) -> None:
    """Write data to a JSON file.

    Parameters
    ----------
    path : str
        Output JSON path.
    data : Any
        JSON-serialisable data.
    indent : int
        JSON indent (default 2).
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False, cls=_NumpyEncoder)


class _NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles NumPy types."""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        return super().default(obj)
