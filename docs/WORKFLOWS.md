# Workflows

## Workflow 1: Extract JTI From NPZ

```bash
python extract_jti.py --data "<path/to/dataset>" --binwidth-ps 200 --dimensions 32 --frame-origin-ps 0 --out results/jti_npz
```

## Workflow 2: Extract JTI From TTBIN

```bash
python extract_jti.py --data "<path/to/dataset>" --ttbin "<path/to/data.ttbin>" --prefer-ttbin --binwidth-ps 200 --dimensions 32 --frame-origin-ps 0 --out results/jti_ttbin
```

## Workflow 3: Compute Schmidt Number

```bash
python compute_jti_schmidt.py --input results/jti_npz --recursive --pattern "*.counts.csv"
```

## Workflow 4: Diagnose 40ps Residue

```bash
python tdc_residue_diagnostics.py --ttbin "<path/to/data.ttbin>" --ch1 1 --ch3 3 --out results/tdc_residue
```

## Workflow 5: Layer Scan Diagnostics

```bash
python tdc_layer_scan.py --ttbin "<path/to/data.ttbin>" --ch-a 1 --ch-b 3 --window-ps 1000 --out results/tdc_layer_scan
```

## Workflow 6: Dense JTI + Schmidt Frame-Length Coverage Scan

> Status: legacy/small-scale validation workflow. 超高维 / 超长 frame 主线应优先使用 Workflow 7 的 fixed-lattice G2-like sweep。Workflow 6 仍可用于 `N<=4096` 的 exact dense baseline 对齐。

### 目的

判断 JTI 帧长 `frame_length_ps = dimensions × binwidth_ps` 是否已覆盖光子对时间相关结构的全部尺度。当光源线宽处于百 kHz 量级时，单光子相干时间约为 µs 量级，需要较大的 `frame_length_ps` 才能捕获完整的联合时间强度信息。

### 核心思路

1. 使用较大的 `binwidth_ps`（数千 ps 量级）配合内存可承受的 dense JTI 维度（如 1024），使 `frame_length_ps` 达到 µs 量级。
2. 对同一数据集生成多组 `(binwidth_ps, dimensions)` 参数下的 dense JTI counts CSV。
3. 对每组 CSV 运行 Schmidt 分解，提取 `schmidt_number`、`K_over_dimension`、`largest_weight` 等指标。
4. 观察这些指标随 `frame_length_ps` 增大是否收敛/饱和——若已饱和，则帧长已覆盖时间相关结构。

### ⚠ P_plus 不适用作单光子相干时间判据

> **重要**: `P_plus`（由 [`run_type0ppln_pplus_auto_dim.py`](../scripts/run_type0ppln_pplus_auto_dim.py) 计算）反映的是 paired coincidence 的对角 profile 统计量，偏向采集稳定性与对角集中度诊断，**不应**直接用作单光子相干时间的判据。判断帧长是否覆盖时间相关结构，应使用本 Workflow 描述的 Schmidt 收敛判据。

### 示例参数组合

以下为安全候选参数（具体取值取决于内存容量与目标相干时间定义，**不要写死**）：

| dimensions (N) | binwidth_ps (bw) | frame_length_ps        | frame_length   |
|----------------|------------------|------------------------|----------------|
| 1024           | 3000             | 3 072 000 ps           | ≈ 3.07 µs      |
| 1024           | 5000             | 5 120 000 ps           | ≈ 5.12 µs      |
| 1024           | 10000            | 10 240 000 ps          | ≈ 10.24 µs     |

> 说明：百 kHz 线宽对应 ~µs 量级相干时间。上表从 ~3 µs 到 ~10 µs 覆盖了典型范围，但实际所需帧长取决于光源特性和实验条件。

### 操作步骤

```bash
# Step 1: 对不同 bw 生成 dense JTI counts CSV
# 注意：输出目录必须不同，禁止覆盖已有结果
jti-extract --data "<path/to/dataset>" \
  --binwidth-ps 3000 --dimensions 1024 --frame-origin-ps 0 \
  --out results/coverage_scan/bw3000_N1024

jti-extract --data "<path/to/dataset>" \
  --binwidth-ps 5000 --dimensions 1024 --frame-origin-ps 0 \
  --out results/coverage_scan/bw5000_N1024

jti-extract --data "<path/to/dataset>" \
  --binwidth-ps 10000 --dimensions 1024 --frame-origin-ps 0 \
  --out results/coverage_scan/bw10000_N1024

# Step 2: 对各组 CSV 运行 Schmidt 分析
jti-schmidt --input results/coverage_scan/bw3000_N1024 --recursive --output results/coverage_scan/schmidt_bw3000.csv
jti-schmidt --input results/coverage_scan/bw5000_N1024 --recursive --output results/coverage_scan/schmidt_bw5000.csv
jti-schmidt --input results/coverage_scan/bw10000_N1024 --recursive --output results/coverage_scan/schmidt_bw10000.csv

# Step 3: 比较 schmidt_number / K_over_dimension / largest_weight 随 frame_length_ps 的趋势
```

### 判据

- 若 `schmidt_number` 随 `frame_length_ps` 增大趋于平稳（变化率低于设定阈值），则帧长已基本覆盖时间相关结构。
- 若仍在快速增长，需进一步增大 `frame_length_ps`（增大 `bw` 或 `N`），但需评估内存风险（参见 [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)）。
- `K_over_dimension = schmidt_number / dimensions` 可辅助判断维度利用效率，收敛时通常趋近于小于 1 的稳定值。
- `largest_weight` 收敛意味着主导奇异模式的权重已稳定。

### 风险提醒

- **内存**: `N=1024` dense JTI 矩阵为 `1024×1024` float64 ≈ 8 MB；SVD 额外开销约同量级。更大 `N` 按平方增长。详见 [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)。
- **时间分辨率**: 大 `bw` 意味着时间分辨率下降，可能抹平快速时间结构。需在覆盖范围与分辨率之间权衡。
- **frame origin**: 大 `bw` 下 `--frame-origin-ps` 的精确对齐更困难，微小偏移可能影响结果。建议对关键参数组合尝试不同 `frame_origin_ps`。
- **数据保护**: 禁止覆盖原始 `*.ttbin` 数据和 `results/` 下已有结果。每次运行必须使用新的输出目录。

## Workflow 7: Ultra-high-dimensional fixed-lattice G2-like JTI sweep

### 目的

在超高维 / 超长 frame 场景下，避免完整 dense `N x N` JTI 和 full SVD 的内存瓶颈，并避免 strict single-hit、nearest、greedy hard-pairing 带来的 selection / pairing bias。当前主线以 fixed global frame lattice 上的 `g2_all_candidates` 统计相关量为主。

### 核心原则

1. 主结果基于 `g2_all_candidates`，不是 strict / nearest / greedy hard pairing。
2. [`_pairs_from_timetags()`](../src/jti_extract/cli/extract.py:258)、[`nearest_pairs()`](../src/jti_extract/cli/tdc_layer_scan.py:307)、[`greedy_unique_pairs()`](../src/jti_extract/cli/tdc_layer_scan.py:327) 只用于 diagnostics。
3. global JTI 必须使用固定全局 frame origin；禁止 per-pair origin。
4. 主 JTI 必须使用 edge guard，并输出 `edge_rejection_ratio`。
5. 多个 global origins 只用于 sensitivity check，不能叠加为更多样本。
6. 大维度默认输出 coarse JTI、diagonal profile、marginals、selected tiles、sparse COO 和 effective-mode summaries，不输出完整 dense CSV。
7. `P_plus` 只作为 acquisition stability / paired coincidence support 辅助证据。

### 推荐阶段

#### Stage 1: 小规模 exact 对齐

```text
N = 512, 1024
binwidth_ps = 100
method = g2_all_candidates, strict, folded_without_strict
origin = 0
edge_guard_ps = max(coincidence_window_ps, 3 * jitter_ps)
```

目标：先验证 fixed lattice、candidate iterator、edge guard、diag profile、coarse JTI 与 legacy dense baseline 是否一致。不要一开始就实现全部 SVD 和 bootstrap。

#### Stage 2: origin / edge / method sensitivity 基础诊断

```text
N = 8192, 16384
binwidth_ps = 100
origin = 0, T/4, T/2, 3T/4
coincidence_window_ps = physically fixed value
```

必须输出：

```text
n_candidates_total
n_candidates_after_edge_guard
edge_rejection_ratio
strict_retention_ratio
method_sensitivity_summary
row_marginal
col_marginal
diag_profile
coarse_JTI
```

2026-04-29 consensus: ultra 主结果保持 raw nonnegative `g2_all_candidates` counts；Stage B 只做 diagnostics-only，不默认扣除 background，也不输出 background-subtracted signed spectrum。

#### Stage 3: 中维度 coverage sweep

```text
N = 8192, 16384, 32768
binwidth_ps = 100
coarse_N = 1024, 2048, 4096
method = g2_all_candidates
```

目标：观察 diagonal profile、coarse JTI 和 `K_coarse` 是否随 `frame_length_ps` 与 `coarse_N` 稳定。

#### Stage 4: pump coherence horizon sweep

```text
frame_length_ps = 3e6, 1e7, 3e7
binwidth_ps = 100
N = 30000, 100000, 300000
method = g2_all_candidates
```

只允许 coarse / sparse / tiled / diagonal-profile 输出。若使用 truncated SVD，必须报告 `captured_frobenius_energy_r`；captured energy 不足时不得声称 full Schmidt number。

### 可信度停止条件

以下任一情况出现时，结果只能作为 exploratory diagnostic：

- `edge_rejection_ratio` 高或不同 origin 结论不一致。
- strict / nearest / greedy diagnostics 与 raw `g2_all_candidates` 主结果强分歧。
- `bootstrap_K_relative_std` 大。
- `K_coarse` 随 `coarse_N` 未稳定。
- `K_truncated_r` 随 rank 未稳定或 captured energy 不足。
- row/column marginals 显示强非平稳性。

### 当前实现状态

Ultra pipeline 已作为 `jti-ultra-sweep` CLI 实现（Stage E/F/G）。支持：

- **数据源**：`.ttbin` 文件、预排序 `.npy` 时间戳文件
- **帧晶格**：`--n-bins`、`--binwidth-ps`、`--frame-origin-ps`
- **符合**：`--coincidence-window-ps`、`--edge-guard-ps`
- **Coarse JTI**：`--coarse-n-bins`（可选 coarse SVD）
- **诊断**：`--origin-sensitivity`、`--edge-guard-sensitivity`（origin/edge sensitivity scan）
- **截断 SVD**：`--truncated-rank`（含 `captured_frobenius_energy_r`）
- **Bootstrap**：`--bootstrap-n`（候选重采样 bootstrap）
- **输出**：CSV (`.ultra_summary.csv`) + JSON (`.ultra_summary.json`) 到时间戳目录
- **验证**：`jti-ultra-sweep --self-test`（合成数据自检）

使用示例：

```bash
# 自检
jti-ultra-sweep --self-test

# 从 NPY 文件运行（合成数据验证）
jti-ultra-sweep --t-a tests/fixtures/t_a.npy --t-b tests/fixtures/t_b.npy \
  --n-bins 1024 --binwidth-ps 100 --coarse-n-bins 64 \
  --origin-sensitivity 50 100 --edge-guard-sensitivity 0 100 200 \
  --out results/ultra_sweep_test

# Dry-run（仅验证配置）
jti-ultra-sweep --t-a tests/fixtures/t_a.npy --t-b tests/fixtures/t_b.npy --dry-run
```

**限制**：
- CLI 使用 [`--self-test`](src/jti_extract/ultra/cli_ultra.py:199) 时不要求数据源参数
- TTBIN 支持需要 Swabian-TimeTagger 绑定
- Bootstrap 当前为简单 row-wise resampling（`--bootstrap-n`），非完整 block bootstrap
- Ultra 模块不修改 baseline `jti-extract`/`jti-schmidt` CLI 或 core 算法
- Coarse JTI 输出为唯一下游 dense matrix；超高维默认不输出完整 dense `N x N` 矩阵
