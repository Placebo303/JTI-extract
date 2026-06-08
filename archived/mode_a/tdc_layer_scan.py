#!/usr/bin/env python3
"""Legacy wrapper for the TDC layer-scan diagnostics CLI."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from jti_extract.cli.tdc_layer_scan import main


if __name__ == "__main__":
    raise SystemExit(main())
