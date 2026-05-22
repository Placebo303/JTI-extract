from __future__ import annotations

import subprocess
import sys


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=False)


def test_legacy_self_tests_do_not_require_timetagger() -> None:
    assert _run([sys.executable, "extract_jti.py", "--self-test"]).returncode == 0
    assert _run([sys.executable, "compute_jti_schmidt.py", "--self-test"]).returncode == 0


def test_module_help_entrypoints() -> None:
    modules = [
        "jti_extract.cli.extract",
        "jti_extract.cli.schmidt",
        "jti_extract.cli.tdc_residue",
        "jti_extract.cli.tdc_layer_scan",
    ]
    for module in modules:
        result = _run([sys.executable, "-m", module, "--help"])
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower()
    extract_help = _run([sys.executable, "-m", "jti_extract.cli.extract", "--help"])
    assert "--pairing-mode" in extract_help.stdout
    assert "--coincidence-window-ps" in extract_help.stdout
    assert "--plot-diagonal-profile" in extract_help.stdout
