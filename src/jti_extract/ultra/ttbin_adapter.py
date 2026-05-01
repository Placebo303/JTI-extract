"""Adapter to read sorted timestamp arrays from TimeTagger TTBIN files
for consumption by the ultra pipeline.

This module wraps the Swabian TimeTagger FileReader offline event stream
to extract channel timestamps and produce numpy arrays suitable for
``g2_accumulate.all_candidates()`` and the rest of the ultra pipeline.

Stage F status: implemented.  Requires Swabian-TimeTagger in the Python
environment.
"""

from typing import Optional, Tuple

import numpy as np


def load_channels_from_ttbin(
    ttbin_path: str,
    ch_a: int,
    ch_b: int,
    max_events: Optional[int] = None,
) -> Tuple[np.ndarray, np.ndarray, dict]:
    """Load sorted channel A and B timestamps from a TTBIN file.

    Parameters
    ----------
    ttbin_path : str
        Path to the ``.ttbin`` file.
    ch_a : int
        Logical channel ID for channel A.
    ch_b : int
        Logical channel ID for channel B.
    max_events : int, optional
        Maximum number of events to read in total from the file stream.

    Returns
    -------
    t_a : np.ndarray
        Sorted 1-D array of channel A timestamps (ps, int64).
    t_b : np.ndarray
        Sorted 1-D array of channel B timestamps (ps, int64).
    meta : dict
        Metadata: ``n_events_read``, ``n_ch_a``, ``n_ch_b``, ``span_ps``.
    """
    try:
        from Swabian import TimeTagger
    except ImportError:
        raise ImportError(
            "Swabian-TimeTagger is required to read .ttbin files. "
            "Install with: pip install Swabian-TimeTagger, or use "
            "the TimeTagger virtual environment."
        )

    reader = TimeTagger.FileReader(str(ttbin_path))

    chunks_a: list[np.ndarray] = []
    chunks_b: list[np.ndarray] = []
    total = 0
    ch_a_int = int(ch_a)
    ch_b_int = int(ch_b)

    while reader.hasData():
        n = 1_000_000
        if max_events is not None:
            remaining = int(max_events) - total
            if remaining <= 0:
                break
            n = max(1, min(n, remaining))
        data = reader.getData(n)
        channels = np.asarray(data.getChannels(), dtype=np.int64)
        timestamps = np.asarray(data.getTimestamps(), dtype=np.int64)
        event_types = np.asarray(data.getEventTypes(), dtype=np.int64)
        total += int(timestamps.size)

        valid = event_types == 0
        chunks_a.append(timestamps[np.logical_and(valid, channels == ch_a_int)])
        chunks_b.append(timestamps[np.logical_and(valid, channels == ch_b_int)])

        if max_events is not None and total >= int(max_events):
            break

    t_a = np.sort(np.concatenate(chunks_a)) if chunks_a else np.array([], dtype=np.int64)
    t_b = np.sort(np.concatenate(chunks_b)) if chunks_b else np.array([], dtype=np.int64)

    span_ps = 0
    if t_a.size and t_b.size:
        span_ps = int(max(t_a[-1], t_b[-1]) - min(t_a[0], t_b[0]))

    meta = {
        "n_events_read": int(total),
        "n_ch_a": int(t_a.size),
        "n_ch_b": int(t_b.size),
        "span_ps": int(span_ps),
        "ch_a": ch_a_int,
        "ch_b": ch_b_int,
        "source": str(ttbin_path),
    }

    return t_a, t_b, meta
