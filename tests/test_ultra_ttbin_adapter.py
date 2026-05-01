"""Tests for jti_extract.ultra.ttbin_adapter."""

from __future__ import annotations

import types
from pathlib import Path

import numpy as np

from jti_extract.ultra.ttbin_adapter import load_channels_from_ttbin


class _FakeData:
    def __init__(self, channels, timestamps, event_types):
        self._channels = channels
        self._timestamps = timestamps
        self._event_types = event_types

    def getChannels(self):
        return self._channels

    def getTimestamps(self):
        return self._timestamps

    def getEventTypes(self):
        return self._event_types


class _FakeReader:
    def __init__(self, data_batches):
        self._data_batches = list(data_batches)

    def hasData(self):
        return bool(self._data_batches)

    def getData(self, n):
        return self._data_batches.pop(0)


class _FakeTimeTagger:
    def __init__(self):
        self.file_reader_paths = []

    def FileReader(self, path):
        self.file_reader_paths.append(path)
        return _FakeReader(
            [
                _FakeData(
                    channels=[1, 1, 3, 3],
                    timestamps=[10, 20, 30, 40],
                    event_types=[0, 1, 0, 0],
                )
            ]
        )


def test_ttbin_adapter_uses_file_reader_and_filters_valid_events(monkeypatch) -> None:
    fake_tagger = _FakeTimeTagger()
    fake_module = types.SimpleNamespace(TimeTagger=fake_tagger)
    monkeypatch.setitem(
        __import__("sys").modules,
        "Swabian",
        fake_module,
    )

    t_a, t_b, meta = load_channels_from_ttbin("/tmp/fake.ttbin", ch_a=1, ch_b=3)

    assert fake_tagger.file_reader_paths == ["/tmp/fake.ttbin"]
    assert np.array_equal(t_a, np.array([10], dtype=np.int64))
    assert np.array_equal(t_b, np.array([30, 40], dtype=np.int64))
    assert meta["n_events_read"] == 4
    assert meta["n_ch_a"] == 1
    assert meta["n_ch_b"] == 2

