from __future__ import annotations

import numpy as np

from jti_extract.cli.schmidt import compute_schmidt_number_from_jti, read_jti_csv


def test_schmidt_eye_and_product_golden_values() -> None:
    eye = compute_schmidt_number_from_jti(np.eye(4))
    product = compute_schmidt_number_from_jti(np.outer([1.0, 2.0, 3.0], [4.0, 5.0]))

    assert abs(eye["schmidt_number"] - 4.0) < 1e-10
    assert abs(eye["purity"] - 0.25) < 1e-10
    assert eye["n_singular_values"] == 4.0
    assert abs(product["schmidt_number"] - 1.0) < 1e-10
    assert abs(product["purity"] - 1.0) < 1e-10


def test_read_project_counts_csv_fixture() -> None:
    mat = read_jti_csv(__import__("pathlib").Path("tests/fixtures/tiny_counts.csv"))

    assert mat.shape == (2, 2)
    assert mat.tolist() == [[1.0, 0.0], [0.0, 1.0]]
