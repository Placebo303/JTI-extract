# Schmidt Analysis

## 基本流程

The Schmidt workflow reads nonnegative JTI counts, normalizes them to a probability matrix, forms `JTA = sqrt(probability)`, computes singular values, converts them to normalized weights, and reports:

- `purity = sum(lambda_k^2)`
- `schmidt_number = 1 / purity`
- `largest_weight`
- `n_singular_values`

Negative counts are rejected. Background subtraction or clipping must be explicit upstream.

## Ultra-high-dimensional JTI 的 effective-mode 分层策略

### 当前推荐主线

对于超高维 / 超长 frame sweep，不应把完整 dense `N x N` JTI 与 full SVD 当作默认路径。当前推荐主线见 [`CURRENT_TASK.md`](../CURRENT_TASK.md)：

```text
timetags
→ fixed global frame lattice
→ G2-like all-candidate coincidence accumulation
→ diagnostics-only retention / method / origin / edge checks
→ coarse JTI / diagonal profile / marginals / selected tiles / sparse representation
→ exact/coarse/truncated effective-mode analysis
```

[`_pairs_from_timetags()`](../src/jti_extract/cli/extract.py:258) 的 `strict_single_hit_per_frame`、[`nearest_pairs()`](../src/jti_extract/cli/tdc_layer_scan.py:307)、[`greedy_unique_pairs()`](../src/jti_extract/cli/tdc_layer_scan.py:327) 只作为 diagnostics；主物理趋势不应基于这些 hard-pairing 结果。

### 三档 effective-mode 分析

| Level | 适用范围 | 输出 | 解释限制 |
|---|---|---|---|
| A: dense exact | `N=512,1024,2048,4096` 小规模 validation | full singular values, exact `schmidt_number` | 仅用于旧 pipeline 对齐与小规模参考 |
| B: coarse exact | 真实 `N` 很大，但 rebin 到 `coarse_N=1024,2048,4096` | `K_coarse_1024`, `K_coarse_2048`, `K_coarse_4096` | 若 `K` 随 `coarse_N` 仍增长，不得声称已收敛 |
| C: sparse/truncated | `N=32768` 到 `N=300000+` | `top_r_singular_values`, `K_truncated_r`, `captured_frobenius_energy_r` | captured energy 不足时不得声称 full Schmidt number |

### raw counts 是主结果；不默认扣除 background

2026-04-29 consensus: ultra fixed-lattice 路线不需要扣除 background。Stage B diagnostics-only prototype 保持 raw nonnegative JTI / G2 counts 为主结果，不默认生成 background-subtracted signed spectrum。

- **Raw nonnegative JTI / G2 counts**：可形成 `JTA = sqrt(probability)`，与现有 [`compute_schmidt_number_from_jti()`](../src/jti_extract/cli/schmidt.py:94) 语义相近。
- **Forbidden by default**：不要把 background-subtracted matrix 写成 ultra 主输出；不要对负值 signed matrix 套用 `JTA = sqrt(probability)` 或称为 Schmidt number。

### 必须同步报告的可信度指标

任何 ultra sweep 的 `K` 或 singular-spectrum 结果，必须同时报告：

- `edge_rejection_ratio`
- `strict_retention_ratio`
- `method_sensitivity_summary`
- `origin_sensitivity_K`
- `bootstrap_K_relative_std`
- `captured_frobenius_energy_r`
- `K vs coarse_N`
- `K vs truncated_rank`

若 edge rejection 高、origin sensitivity 高、strict/nearest/greedy diagnostics 与 raw `g2_all_candidates` 强分歧、bootstrap 方差大，或 captured energy 不足，则结果只能表述为 exploratory diagnostic，不能表述为 final dimension certification。

## 帧长覆盖判据：Schmidt 指标随 frame_length_ps 的收敛/饱和

> Status: legacy/small-scale dense validation. 本节适用于 `N<=4096` 左右的 dense JTI exact SVD 对齐；超高维 / 超长 frame 主线应使用上文的 fixed-lattice G2-like 分层策略。

### 背景

JTI 的帧长由 `frame_length_ps = dimensions × binwidth_ps` 决定。如果帧长不足以覆盖光子对的完整时间相关结构，dense exact Schmidt 分解结果可能低估模式数，无法反映真实的联合时间强度谱。

当光源线宽处于百 kHz 量级时，单光子相干时间为 µs 量级。需要使用较大的 `binwidth_ps` 与内存可承受的 dense 维度使 `frame_length_ps` 接近或覆盖该量级。

### 方法

1. 使用 [`jti-extract`](../src/jti_extract/cli/extract.py) 对同一数据集生成不同 `(binwidth_ps, dimensions)` 参数组合下的小规模 dense JTI counts CSV。
2. 使用 [`jti-schmidt`](../src/jti_extract/cli/schmidt.py) 对每组 CSV 计算 Schmidt 指标。
3. 绘制或比较 `schmidt_number`、`K_over_dimension`、`largest_weight` 随 `frame_length_ps` 的变化趋势。

### 收敛判据

| 指标 | 收敛含义 | 未收敛信号 |
|------|---------|-----------|
| `schmidt_number` | 随 `frame_length_ps` 增大趋于平稳 | 仍在近似线性或超线性增长 |
| `K_over_dimension` | 趋近稳定值（通常 < 1） | 持续上升 |
| `largest_weight` | 主导模式权重稳定 | 持续下降（更多模式被捕获） |

- **判断方法**: 若相邻两次 `frame_length_ps` 增量下 `schmidt_number` 的相对变化低于设定阈值（如 < 5%），可认为已收敛。
- **物理含义**: 收敛意味着帧长已覆盖主要时间相关结构；未收敛意味着需要更大的帧长。

### ⚠ P_plus 不适用作单光子相干时间判据

> `P_plus`（由 [`run_type0ppln_pplus_auto_dim.py`](../scripts/run_type0ppln_pplus_auto_dim.py) 计算）是对 paired coincidence 对角 profile 的统计量，更偏向采集稳定性与对角集中度诊断，**不应**用作单光子相干时间的判据。小规模 dense exact Schmidt 可作为 validation；超高维覆盖判断应使用 fixed-lattice raw G2-like sweep、coarse/truncated effective-mode、edge/origin sensitivity、method sensitivity 和 bootstrap stability 的综合判据；不默认扣除 background。

### 候选参数表

以下为安全候选参数组合（具体取值取决于内存容量与目标相干时间定义，**不要写死**）：

| dimensions (N) | binwidth_ps (bw) | frame_length_ps        | frame_length   | 备注                          |
|----------------|------------------|------------------------|----------------|-------------------------------|
| 1024           | 3000             | 3 072 000 ps           | ≈ 3.07 µs      | 约 8 MB dense 矩阵            |
| 1024           | 5000             | 5 120 000 ps           | ≈ 5.12 µs      | 约 8 MB dense 矩阵            |
| 1024           | 10000            | 10 240 000 ps          | ≈ 10.24 µs     | 约 8 MB dense 矩阵，分辨率较低 |
| 2048           | 3000             | 6 144 000 ps           | ≈ 6.14 µs      | 约 32 MB dense 矩阵           |
| 2048           | 5000             | 10 240 000 ps          | ≈ 10.24 µs     | 约 32 MB dense 矩阵           |

> **内存估算**: `N×N` float64 矩阵 ≈ `8×N²` 字节；SVD 额外需约 `3×8×N²` 字节。`N=1024` 总计约 32 MB，`N=2048` 约 128 MB，`N=4096` 约 512 MB。实际峰值内存取决于 NumPy/SciPy 内部实现。

### 操作示例

```bash
# 生成不同 bw 的 dense JTI
jti-extract --data "<path>" --binwidth-ps 3000 --dimensions 1024 --frame-origin-ps 0 --out results/schmidt_scan/bw3000_N1024
jti-extract --data "<path>" --binwidth-ps 5000 --dimensions 1024 --frame-origin-ps 0 --out results/schmidt_scan/bw5000_N1024
jti-extract --data "<path>" --binwidth-ps 10000 --dimensions 1024 --frame-origin-ps 0 --out results/schmidt_scan/bw10000_N1024

# 对各组运行 Schmidt 分析
jti-schmidt --input results/schmidt_scan/bw3000_N1024 --recursive --output results/schmidt_scan/summary_bw3000.csv
jti-schmidt --input results/schmidt_scan/bw5000_N1024 --recursive --output results/schmidt_scan/summary_bw5000.csv
jti-schmidt --input results/schmidt_scan/bw10000_N1024 --recursive --output results/schmidt_scan/summary_bw10000.csv

# 比较各组 schmidt_number 随 frame_length_ps 的收敛行为
```

### 风险与限制

- **内存/耗时**: 大维度 dense JTI 和 SVD 的内存/计算量按 N² 增长。参见 [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)。
- **时间分辨率**: 大 `binwidth_ps` 降低时间分辨率，可能抹平快速时间结构。
- **frame origin 敏感性**: 大 `bw` 下 `--frame-origin-ps` 偏移对结果影响更大。
- **strict single-hit selection bias**: 由 [`jti-extract`](../src/jti_extract/cli/extract.py) 生成的 dense counts 使用 strict single-hit-per-frame 语义；在超长 frame 下只能作为 diagnostic baseline。
- **数据保护**: 禁止覆盖原始数据和已有结果文件。
