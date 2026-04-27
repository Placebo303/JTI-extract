#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover
    np = None  # type: ignore[assignment]


def _normalize_path(raw: str) -> Path:
    """Accept either a native path or a Windows path like `E:\\Data\\...`."""
    s = str(raw).strip()

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


def _to_float(text: str) -> float:
    text = str(text).strip()
    if text == "":
        return math.nan
    return float(text)


def _looks_like_index(values: np.ndarray, expected_len: int) -> bool:
    if values.size != expected_len or expected_len <= 0:
        return False
    if not np.all(np.isfinite(values)):
        return False
    return bool(np.allclose(values, np.arange(expected_len, dtype=float)))


def read_jti_csv(path: Path) -> np.ndarray:
    rows: list[list[float]] = []
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for raw_row in reader:
            if not raw_row or all(str(cell).strip() == "" for cell in raw_row):
                continue
            try:
                rows.append([_to_float(cell) for cell in raw_row])
            except ValueError as exc:
                raise ValueError(f"{path} contains a non-numeric CSV cell: {exc}") from exc

    if not rows:
        raise ValueError(f"{path} is empty")

    width = max(len(row) for row in rows)
    padded = [row + [math.nan] * (width - len(row)) for row in rows]
    mat = np.asarray(padded, dtype=np.float64)

    # Project counts.csv format: first row is ["", 0, 1, ...], first column is 0, 1, ...
    if (
        mat.shape[0] >= 2
        and mat.shape[1] >= 2
        and math.isnan(float(mat[0, 0]))
        and _looks_like_index(mat[0, 1:], mat.shape[1] - 1)
        and _looks_like_index(mat[1:, 0], mat.shape[0] - 1)
    ):
        mat = mat[1:, 1:]

    if mat.ndim != 2 or mat.size == 0:
        raise ValueError(f"{path} did not contain a 2D matrix")
    if not np.all(np.isfinite(mat)):
        raise ValueError(f"{path} contains missing or non-finite values after header/index detection")
    return mat


def compute_schmidt_number_from_jti(jti_counts: np.ndarray, *, threshold: float = 1e-12) -> dict[str, float]:
    mat = np.asarray(jti_counts, dtype=np.float64)
    if mat.ndim != 2:
        raise ValueError("JTI must be a 2D matrix")
    negative_bins = int(np.count_nonzero(mat < 0))
    if negative_bins:
        raise ValueError("JTI contains negative values; subtract background before this step or clip explicitly")

    total = float(np.sum(mat))
    if not np.isfinite(total) or total <= 0.0:
        raise ValueError("JTI total sum must be positive")

    probability = mat / total
    jta = np.sqrt(probability)
    singular_vals = np.linalg.svd(jta, compute_uv=False)
    singular_vals = singular_vals[singular_vals > float(threshold)]
    if singular_vals.size == 0:
        raise ValueError("no singular values above threshold")

    weights = singular_vals**2
    weights = weights / np.sum(weights)
    purity = float(np.sum(weights**2))
    schmidt_number = float(1.0 / purity)

    return {
        "schmidt_number": schmidt_number,
        "purity": purity,
        "largest_weight": float(np.max(weights)),
        "n_singular_values": float(singular_vals.size),
        "singular_value_threshold": float(threshold),
        "total_counts": total,
        "normalized_sum": float(np.sum(probability)),
        "nonzero_bins": float(np.count_nonzero(mat)),
        "negative_bins": float(negative_bins),
    }


def _iter_csv_files(input_path: Path, *, pattern: str, recursive: bool) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if not input_path.is_dir():
        raise FileNotFoundError(f"input path not found: {input_path}")
    iterator: Iterable[Path] = input_path.rglob(pattern) if recursive else input_path.glob(pattern)
    return sorted(path for path in iterator if path.is_file())


def _parse_jti_metadata(path: Path) -> dict[str, object]:
    out: dict[str, object] = {
        "noise_level": "",
        "dimension": "",
        "bin_width_ps": "",
        "K_over_dimension": "",
    }

    match = re.search(r"(?:^|_)d(?P<dim>\d+)_bw(?P<bw>\d+)_jti\.csv$", path.name, re.IGNORECASE)
    if match:
        out["dimension"] = int(match.group("dim"))
        out["bin_width_ps"] = int(match.group("bw"))

    parts = path.parts
    for idx, part in enumerate(parts):
        if part.lower() == "asenoise_type0" and idx + 1 < len(parts):
            out["noise_level"] = parts[idx + 1]
            break
    if not out["noise_level"]:
        for part in reversed(parts):
            if re.fullmatch(r"\d+(?:\.\d+)?[kKmM]", part):
                out["noise_level"] = part
                break

    return out


def _sort_key(row: dict[str, object]) -> tuple[float, int, int, str]:
    noise = str(row.get("noise_level", ""))
    match = re.fullmatch(r"(?P<value>\d+(?:\.\d+)?)(?P<unit>[kKmM])", noise)
    if match:
        value = float(match.group("value"))
        unit = match.group("unit").lower()
        noise_value = value * (1_000_000.0 if unit == "m" else 1_000.0)
    else:
        noise_value = float("inf")

    def _int_or_max(value: object) -> int:
        try:
            if value == "":
                return 2**31 - 1
            return int(value)
        except Exception:
            return 2**31 - 1

    return (noise_value, _int_or_max(row.get("dimension", "")), _int_or_max(row.get("bin_width_ps", "")), str(row.get("file", "")))


def write_summary_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = [
        "noise_level",
        "dimension",
        "bin_width_ps",
        "file",
        "rows",
        "cols",
        "total_counts",
        "nonzero_bins",
        "schmidt_number",
        "K_over_dimension",
        "purity",
        "largest_weight",
        "n_singular_values",
        "singular_value_threshold",
        "normalized_sum",
        "status",
        "message",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def run_batch(input_path: Path, *, pattern: str, recursive: bool, output: Path | None, threshold: float) -> Path:
    files = _iter_csv_files(input_path, pattern=pattern, recursive=recursive)
    if not files:
        raise FileNotFoundError(f"no CSV files matched {pattern!r} under {input_path}")

    if output is None:
        output_dir = input_path.parent if input_path.is_file() else input_path
        output = output_dir / "jti_schmidt_summary.csv"

    rows: list[dict[str, object]] = []
    for path in files:
        row: dict[str, object] = {"file": str(path), "status": "ok", "message": "", **_parse_jti_metadata(path)}
        try:
            matrix = read_jti_csv(path)
            row["rows"] = int(matrix.shape[0])
            row["cols"] = int(matrix.shape[1])
            row.update(compute_schmidt_number_from_jti(matrix, threshold=threshold))
            if row.get("dimension") not in ("", None):
                row["K_over_dimension"] = float(row["schmidt_number"]) / float(row["dimension"])
        except Exception as exc:
            row["status"] = "error"
            row["message"] = str(exc)
        rows.append(row)

    rows.sort(key=_sort_key)
    write_summary_csv(output, rows)
    return output


def _self_test() -> None:
    assert np is not None
    eye = np.eye(4)
    res = compute_schmidt_number_from_jti(eye)
    assert abs(res["schmidt_number"] - 4.0) < 1e-10

    product = np.outer([1.0, 2.0, 3.0], [4.0, 5.0])
    res = compute_schmidt_number_from_jti(product)
    assert abs(res["schmidt_number"] - 1.0) < 1e-10

    tmp = Path(".schmidt_self_test_tmp")
    tmp.mkdir(exist_ok=True)
    try:
        p = tmp / "toy.counts.csv"
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["", 0, 1])
            w.writerow([0, 1, 0])
            w.writerow([1, 0, 1])
        mat = read_jti_csv(p)
        assert mat.shape == (2, 2)
        out = run_batch(tmp, pattern="*.counts.csv", recursive=False, output=None, threshold=1e-12)
        assert out.exists()
    finally:
        for path in [tmp / "toy.counts.csv", tmp / "jti_schmidt_summary.csv"]:
            if path.exists():
                path.unlink()
        if tmp.exists():
            tmp.rmdir()


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Compute Schmidt mode numbers from JTI CSV count matrices using "
            "JTA=sqrt(normalized JTI), SVD, and K=1/sum(lambda_k^2)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python compute_jti_schmidt.py --input results\\jti_run\n"
            "  python compute_jti_schmidt.py --input results --recursive --pattern \"*.counts.csv\"\n"
        ),
    )
    ap.add_argument("--input", required=False, help="A JTI CSV file or a directory containing JTI CSV files.")
    ap.add_argument("--pattern", default="*.counts.csv", help="Filename pattern when --input is a directory.")
    ap.add_argument("--recursive", action="store_true", help="Search input directory recursively.")
    ap.add_argument("--output", default=None, help="Summary CSV path. Default: jti_schmidt_summary.csv in the input directory.")
    ap.add_argument("--threshold", type=float, default=1e-12, help="Drop singular values at or below this threshold.")
    ap.add_argument("--self-test", action="store_true", help="Run toy validation and exit.")
    args = ap.parse_args()

    if np is None:  # pragma: no cover
        raise SystemExit(
            f"numpy is missing in this Python environment ({sys.executable}). "
            "Run with a Python that has numpy installed."
        )

    if args.self_test:
        _self_test()
        print("self-test passed")
        return 0

    if not args.input:
        raise SystemExit("--input is required unless --self-test is used.")

    input_path = _normalize_path(args.input)
    output = _normalize_path(args.output) if args.output else None
    out_path = run_batch(
        input_path,
        pattern=str(args.pattern),
        recursive=bool(args.recursive),
        output=output,
        threshold=float(args.threshold),
    )
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
