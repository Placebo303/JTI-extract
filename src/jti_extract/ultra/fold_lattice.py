"""Fixed global frame lattice helpers for ultra-high-dimensional G2-like JTI.

All functions use a fixed global origin.  No per-pair origin is allowed.
"""

import numpy as np


def frame_length_ps(n_bins: int, bin_width_ps: int) -> int:
    """Total frame length in picoseconds.

    Parameters
    ----------
    n_bins : int
        Number of bins (N) per frame dimension.
    bin_width_ps : int
        Width of each time bin in picoseconds.

    Returns
    -------
    int
        Frame length = n_bins * bin_width_ps.
    """
    return int(n_bins) * int(bin_width_ps)


def phase_in_frame(
    times_ps: np.ndarray,
    frame_origin_ps: float,
    frame_length_ps: int,
) -> np.ndarray:
    """Phase (time offset within a frame) for each timestamp.

    Computes ``(times_ps - frame_origin_ps) % frame_length_ps``.

    Parameters
    ----------
    times_ps : np.ndarray
        1-D array of timestamps (ps).
    frame_origin_ps : float
        Global frame origin (ps).
    frame_length_ps : int
        Frame length (ps).

    Returns
    -------
    np.ndarray
        Phase values in [0, frame_length_ps).
    """
    shifted = np.asarray(times_ps, dtype=np.float64) - float(frame_origin_ps)
    return np.mod(shifted, float(frame_length_ps))


def bin_indices(
    times_ps: np.ndarray,
    frame_origin_ps: float,
    bin_width_ps: int,
    n_bins: int,
) -> np.ndarray:
    """Frame-local bin indices for each timestamp.

    Computes ``floor((times_ps - frame_origin_ps) / bin_width_ps) % n_bins``.

    Parameters
    ----------
    times_ps : np.ndarray
        1-D array of timestamps (ps).
    frame_origin_ps : float
        Global frame origin (ps).
    bin_width_ps : int
        Bin width (ps).
    n_bins : int
        Number of bins per frame dimension.

    Returns
    -------
    np.ndarray
        Bin indices in [0, n_bins).
    """
    bw = float(int(bin_width_ps))
    shifted = np.asarray(times_ps, dtype=np.float64) - float(frame_origin_ps)
    raw = np.floor(shifted / bw)
    return np.mod(raw, float(int(n_bins))).astype(np.int64, copy=False)


def edge_guard_mask(
    times_ps: np.ndarray,
    frame_origin_ps: float,
    frame_length_ps: int,
    edge_guard_ps: int,
) -> np.ndarray:
    """Mask selecting events whose phase is safely away from frame boundaries.

    An event is *kept* (True) when its phase is >= *edge_guard_ps* and
    <= *frame_length_ps - edge_guard_ps*.

    Parameters
    ----------
    times_ps : np.ndarray
        1-D array of timestamps (ps).
    frame_origin_ps : float
        Global frame origin (ps).
    frame_length_ps : int
        Frame length (ps).
    edge_guard_ps : int
        Edge-guard margin (ps).  Events closer than this to a frame
        boundary are rejected.

    Returns
    -------
    np.ndarray
        Boolean mask, same shape as *times_ps*.
    """
    phase = phase_in_frame(times_ps, frame_origin_ps, frame_length_ps)
    eg = float(int(edge_guard_ps))
    fl = float(int(frame_length_ps))
    return (phase >= eg) & (phase <= fl - eg)
