"""Development shim for running src-layout modules without installation."""

from __future__ import annotations

from pathlib import Path

_SRC_PACKAGE = Path(__file__).resolve().parent.parent / "src" / "jti_extract"
if _SRC_PACKAGE.exists():
    __path__.insert(0, str(_SRC_PACKAGE))  # type: ignore[name-defined]

try:
    from ._version import __version__  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - only when the src tree is missing
    __version__ = "0.1.0"
