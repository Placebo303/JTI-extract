from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np

from jti_extract.cli.extract import _read_npz_timebins, run_extract
from jti_extract.io.json import json_default


def test_npz_fixture_contract_and_json_default() -> None:
    raw = _read_npz_timebins(__import__("pathlib").Path("tests/fixtures/tiny_timebins.npz"))

    assert raw.Ch.tolist() == [0.0, 1.0, 0.0, 1.0]
    assert raw.TimeTag.tolist() == [10, 20, 110, 120]
    assert json.dumps({"x": np.asarray([1, 2]), "n": np.int64(3)}, default=json_default)


def test_run_extract_writes_csv_json_fields_from_npz() -> None:
    work = Path("tests/_work/io_contract")
    if work.exists():
        shutil.rmtree(work)
    data_dir = work / "data"
    data_dir.mkdir(parents=True)
    np.savez(
        data_dir / "parsed_timebin_data.npz",
        Ch=np.asarray([0.0, 1.0, 0.0, 1.0], dtype=float),
        TimeTag=np.asarray([10, 20, 110, 120], dtype=np.int64),
    )

    summary = run_extract(
        data_dir=data_dir,
        ttbin=None,
        binwidth_ps=[50],
        dimensions=[4],
        frame_origin_ps=0.0,
        scan_frame_origin=True,
        frame_origin_start_ps=0.0,
        frame_origin_stop_ps=50.0,
        frame_origin_step_ps=25.0,
        out_dir=work / "out",
        quiet=True,
        max_events=None,
        raw_ch_a_id=1,
        raw_ch_b_id=2,
        logical_ch_a=0,
        logical_ch_b=1,
        prefer_ttbin=False,
        background_subtract=False,
        peak_align=False,
        align_mode="roll",
        normalize="none",
        save_csv=True,
        save_npz=False,
        plot=False,
        prefix="",
    )

    output = summary["outputs"][0]
    assert output["dimension"] == 4
    assert output["bin_width_ps"] == 50
    assert (work / "out" / "jti_dim4_bw50ps.counts.csv").exists()
    assert (work / "out" / "jti_dim4_bw50ps.meta.json").exists()
    assert (work / "out" / "jti_dim4_bw50ps.frame_origin_scan.csv").exists()
    assert (work / "out" / "jti_dim4_bw50ps.frame_origin_scan_best.json").exists()
