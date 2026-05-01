from __future__ import annotations

import numpy as np

from jti_extract.cli.tdc_layer_scan import greedy_unique_pairs, nearest_pairs


def test_nearest_pairs_current_behavior() -> None:
    t_a = np.asarray([100, 200, 1000], dtype=np.int64)
    t_b = np.asarray([95, 205, 400], dtype=np.int64)

    pa, pb, dt = nearest_pairs(t_a, t_b, window_ps=20)

    assert pa.tolist() == [100, 200]
    assert pb.tolist() == [95, 205]
    assert dt.tolist() == [-5, 5]


def test_greedy_unique_pairs_current_behavior() -> None:
    t_a = np.asarray([100, 102, 200], dtype=np.int64)
    t_b = np.asarray([101, 201], dtype=np.int64)

    pa, pb, dt = greedy_unique_pairs(t_a, t_b, window_ps=5)

    assert pa.tolist() == [100, 200]
    assert pb.tolist() == [101, 201]
    assert dt.tolist() == [1, 1]
