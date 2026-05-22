# Schmidt Analysis

The Schmidt workflow reads nonnegative JTI counts, normalizes them to a probability matrix, forms `JTA = sqrt(probability)`, computes singular values, converts them to normalized weights, and reports:

- `purity = sum(lambda_k^2)`
- `schmidt_number = 1 / purity`
- `largest_weight`
- `n_singular_values`

Negative counts are rejected. Background subtraction or clipping must be explicit upstream.
