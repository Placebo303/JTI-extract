"""JSON serialization helpers shared by CLIs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


def json_default(obj: Any) -> Any:
    """Serialize common scientific Python objects for JSON output."""
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return str(obj)
