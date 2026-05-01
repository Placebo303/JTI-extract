"""All-candidate coincidence iterator for fixed-lattice G2-like JTI.

Chunked over *t_a* using a fixed physical *coincidence_window_ps*.
Chunking must not change the total set of candidates.
"""

from typing import Iterable, Tuple

import numpy as np


def _candidates_one_chunk(
    t_a_chunk: np.ndarray,
    t_b: np.ndarray,
    coincidence_window_ps: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return all (t_a, t_b, delta_ps) candidates for one *t_a_chunk*.

    Parameters
    ----------
    t_a_chunk : np.ndarray
        Sorted 1-D array of a subset of t_a timestamps (ps).
    t_b : np.ndarray
        Fully sorted 1-D array of t_b timestamps (ps).
    coincidence_window_ps : int
        Fixed physical coincidence window (ps).

    Returns
    -------
    t_a_out : np.ndarray
        t_a timestamps of candidates.
    t_b_out : np.ndarray
        Corresponding t_b timestamps.
    delta_out : np.ndarray
        delta = t_b - t_a (ps).
    """
    w = int(coincidence_window_ps)
    left = np.searchsorted(t_b, t_a_chunk - w, side="left")
    right = np.searchsorted(t_b, t_a_chunk + w, side="right")
    total = int(np.sum(right - left))
    if total <= 0:
        return (
            np.array([], dtype=np.int64),
            np.array([], dtype=np.int64),
            np.array([], dtype=np.int64),
        )
    out_a = np.empty(total, dtype=np.int64)
    out_b = np.empty(total, dtype=np.int64)
    out_d = np.empty(total, dtype=np.int64)
    pos = 0
    for av, lo, hi in zip(t_a_chunk, left, right):
        n = int(hi - lo)
        if n:
            bv = t_b[lo:hi]
            out_a[pos : pos + n] = int(av)
            out_b[pos : pos + n] = bv
            out_d[pos : pos + n] = bv - int(av)
            pos += n
    return out_a, out_b, out_d


def iter_all_candidates(
    t_a: np.ndarray,
    t_b: np.ndarray,
    coincidence_window_ps: int,
    chunk_events: int = 200_000,
) -> Iterable[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Yield all (t_a, t_b, delta_ps) candidate arrays in chunks.

    All *t_a* and *t_b* must be pre-sorted ascending.

    Parameters
    ----------
    t_a : np.ndarray
        Sorted 1-D array of channel A timestamps (ps).
    t_b : np.ndarray
        Sorted 1-D array of channel B timestamps (ps).
    coincidence_window_ps : int
        Fixed physical coincidence window (ps).
    chunk_events : int
        Number of *t_a* events per chunk (default 200 000).
        Must be positive.

    Raises
    ------
    ValueError
        If *chunk_events* <= 0.

    Yields
    ------
    t_a_out : np.ndarray
    t_b_out : np.ndarray
    delta_out : np.ndarray
    """
    chunk_events = int(chunk_events)
    if chunk_events <= 0:
        raise ValueError(
            f"chunk_events must be positive, got {chunk_events}"
        )
    t_a = np.asarray(t_a, dtype=np.int64)
    t_b = np.asarray(t_b, dtype=np.int64)
    for start in range(0, int(t_a.size), chunk_events):
        chunk = t_a[start : start + chunk_events]
        yield _candidates_one_chunk(chunk, t_b, coincidence_window_ps)


def all_candidates(
    t_a: np.ndarray,
    t_b: np.ndarray,
    coincidence_window_ps: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return all (t_a, t_b, delta_ps) candidates as a single concatenated array.

    Convenience wrapper that concatenates all chunks.

    Parameters
    ----------
    t_a : np.ndarray
        Sorted 1-D array of channel A timestamps (ps).
    t_b : np.ndarray
        Sorted 1-D array of channel B timestamps (ps).
    coincidence_window_ps : int
        Fixed physical coincidence window (ps).

    Returns
    -------
    t_a_out : np.ndarray
    t_b_out : np.ndarray
    delta_out : np.ndarray
    """
    parts_a: list[np.ndarray] = []
    parts_b: list[np.ndarray] = []
    parts_d: list[np.ndarray] = []
    for ca, cb, cd in iter_all_candidates(t_a, t_b, coincidence_window_ps):
        if ca.size:
            parts_a.append(ca)
            parts_b.append(cb)
            parts_d.append(cd)
    if not parts_a:
        return (
            np.array([], dtype=np.int64),
            np.array([], dtype=np.int64),
            np.array([], dtype=np.int64),
        )
    return (
        np.concatenate(parts_a),
        np.concatenate(parts_b),
        np.concatenate(parts_d),
    )
