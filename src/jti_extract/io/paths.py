"""Path normalization helpers."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def normalize_path(raw: str) -> Path:
    """Accept native paths and Windows drive paths when running under WSL/Linux."""
    s = str(raw).strip().strip('"')
    is_windows_abs = len(s) >= 3 and s[1] == ":" and (s[2] == "\\" or s[2] == "/")
    if not is_windows_abs:
        return Path(s)
    if os.name == "nt":
        return Path(s)
    try:
        out = subprocess.check_output(["wslpath", "-a", s], text=True).strip()
        if out:
            return Path(out)
    except Exception:
        drive = s[0].lower()
        rest = s[2:].replace("\\", "/").lstrip("/")
        return Path(f"/mnt/{drive}/{rest}")
    return Path(s)
