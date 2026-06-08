"""CLI smoke tests for JTI extraction modules."""
from __future__ import annotations

import subprocess
import sys


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=False)


def test_module_help_entrypoints() -> None:
    """Verify that all CLI modules can show help."""
    modules = [
        "jti_extract.cli.extract",
        "jti_extract.cli.schmidt",
        "jti_extract.cli.tdc_residue",
        "jti_extract.cli.tdc_layer_scan",
    ]
    for module in modules:
        result = _run([sys.executable, "-m", module, "--help"])
        assert result.returncode == 0, f"{module} --help failed: {result.stderr}"
        assert "usage:" in result.stdout.lower()


def test_extract_cli_has_new_arguments() -> None:
    """Verify that extract CLI has the new CV/DV/SVD arguments."""
    result = _run([sys.executable, "-m", "jti_extract.cli.extract", "--help"])
    assert result.returncode == 0
    assert "--svd-unwrapped" in result.stdout
    assert "--guard-bins" in result.stdout
    assert "--tau0-ps" in result.stdout
    assert "--fine-bins" in result.stdout
    assert "--k-values" in result.stdout
