"""Tests for jti_extract.ultra.io_ultra."""

import os
import tempfile

from jti_extract.ultra.io_ultra import (
    SWEEP_SUMMARY_FIELDS,
    make_output_dir,
    write_json,
    write_summary_csv,
)


class TestMakeOutputDir:
    def test_creates_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = make_output_dir(tmp)
            assert os.path.isdir(path)
            assert path.startswith(tmp)

    def test_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = make_output_dir(tmp, prefix="mytest_")
            basename = os.path.basename(path)
            assert basename.startswith("mytest_")
            assert "ultra_jti_sweep_" in basename


class TestWriteSummaryCSV:
    def test_writes_csv(self) -> None:
        rows = [
            {"n_bins": 1024, "K_coarse": 4.2, "n_candidates_total": 100},
            {"n_bins": 2048, "K_coarse": 5.1, "n_candidates_total": 200},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.csv")
            write_summary_csv(path, rows)
            assert os.path.isfile(path)
            with open(path) as f:
                content = f.read()
            assert "n_bins" in content
            assert "K_coarse" in content
            assert "1024" in content

    def test_fields_param(self) -> None:
        rows = [
            {"n_bins": 1024, "K_coarse": 4.2, "extra": "ignored"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.csv")
            write_summary_csv(path, rows, fields=["n_bins"])
            with open(path) as f:
                content = f.read()
            assert "n_bins" in content
            assert "K_coarse" not in content

    def test_empty_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "empty.csv")
            write_summary_csv(path, [])
            assert os.path.isfile(path)


class TestWriteJSON:
    def test_writes_json(self) -> None:
        data = {"key": "value", "num": 42}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.json")
            write_json(path, data)
            assert os.path.isfile(path)
            import json
            with open(path) as f:
                loaded = json.load(f)
            assert loaded["key"] == "value"
            assert loaded["num"] == 42

    def test_numpy_types(self) -> None:
        import numpy as np
        data = {"int": np.int64(42), "float": np.float64(3.14)}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "numpy.json")
            write_json(path, data)
            import json
            with open(path) as f:
                loaded = json.load(f)
            assert loaded["int"] == 42
            assert loaded["float"] == 3.14


class TestSchemaFields:
    def test_swEEP_SUMMARY_FIELDS_defined(self) -> None:
        assert len(SWEEP_SUMMARY_FIELDS) > 10
        assert "n_bins" in SWEEP_SUMMARY_FIELDS
        assert "K_coarse" in SWEEP_SUMMARY_FIELDS
