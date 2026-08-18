# 输出格式

single 模式将下列输出写入 `--out`。多峰 `auto`/`selected` 模式写入根目录的 `peak_catalog.csv`，并把同名的一套单峰输出写到 `peaks/peak_XXX/`；所有矩阵均为绝对计数，默认不合并峰。

## peak_catalog.csv（多峰模式）

峰目录至少记录残差峰中心、逐峰 residual window、目录编号与原始/保留 counts。峰编号按 residual delay 升序；它用于可复算的选择，不是背景扣除或物理模式标签。

## H_raw_aligned.csv

矩阵 CSV，行/列为 bin index。第一行为列标题（空 + 0, 1, 2, ...），每行以行索引开头。

```
,0,1,2,...,127
0,0.0,0.0,1.0,...
1,0.0,0.0,0.0,...
...
```

## H_raw_aligned.npz

```python
np.load("H_raw_aligned.npz")["jti_counts"]  # (dim, dim) float64
np.load("H_raw_aligned.npz")["dimension"]    # int
np.load("H_raw_aligned.npz")["bin_width_ps"] # int
np.load("H_raw_aligned.npz")["frame_origin_ps"] # float
np.load("H_raw_aligned.npz")["tau_align_ps"] # float
np.load("H_raw_aligned.npz")["delay_min_ps"] # int
np.load("H_raw_aligned.npz")["delay_max_ps"] # int
np.load("H_raw_aligned.npz")["guard_bins"]   # int
```

## H_raw_aligned.png

viridis 热图，lower origin，x/y 轴为 bin index，colorbar label = "Counts"。

## raw_aligned_meta.json

完整 metadata，见 [CLI.md](CLI.md#metadata-字段)。`pairing_mode` 固定为在 inclusive residual-delay window 内的全部有序 A-B 对；`normalization` 固定为 `none`，因此 `H_raw_aligned` 和 residual histogram 都是绝对对数。`input` 记录 .ttbin 路径、通道、读入事件数与时间跨度（ps/s）。

关键字段：
- `count_balance_error`：`accepted_pairs - retained - cross_frame - edge - invalid`，必须为 0
- `delay_span_exceeds_frame_period`：boolean，delay range 是否超过 frame period
- `weighted_mean_diag_offset_ps`：加权平均对角线偏移（ps）
- `weighted_std_diag_offset_ps`：加权标准差对角线偏移（ps）
- `K_raw_aligned`：Schmidt-like K（`--compute-svd` 时）
- `purity`：`1/K`（`--compute-svd` 时）
- `frame_period_ps`：当前分析 frame，固定为 `dimension * binwidth_ps`；多峰正式支持域限于同一分析 frame

## residual_tau_histogram.csv

| 列 | 说明 |
|---|---|
| `residual_tau_ps` | 残差延时 bin 中心（ps） |
| `counts` | 该 bin 的事件对数 |

## residual_tau_histogram.png

线图，x 轴 = residual tau (ps)，y 轴 = counts。标注 `residual_tau = 0 ps` 竖线。
title 中写入 `tau_align_ps` 值。

## summary.csv（`--compute-svd` 时）

| 列 | 说明 |
|---|---|
| `binwidth_ps` | Bin width (ps) |
| `dimension` | JTI dimension |
| `frame_period_ps` | `dim * binwidth_ps` |
| `guard_bins` | Edge guard bins |
| `guard_ps` | `guard_bins * binwidth_ps` |
| `delay_min_ps` | Delay window lower bound |
| `delay_max_ps` | Delay window upper bound |
| `accepted_pairs_input` | 总配对数 |
| `retained_in_jti` | 矩阵内保留数 |
| `retained_fraction` | `retained / accepted` |
| `cross_frame_rejected` | 跨帧剔除数 |
| `edge_rejected` | 边缘保护剔除数 |
| `invalid_bin` | 无效 bin 数 |
| `count_balance_error` | 计数平衡误差（必须为 0） |
| `weighted_mean_diag_offset_ps` | 加权平均对角线偏移 |
| `weighted_std_diag_offset_ps` | 加权标准差对角线偏移 |
| `K_raw_aligned` | Schmidt-like K |
| `purity` | `1/K` |
| `n_singular_values` | 非零奇异值数 |
| `lambda1` | 第一主成分权重 |
| `lambda2` | 第二主成分权重 |
| `lambda3` | 第三主成分权重 |
| `lambda5_cumsum` | 前 5 主成分累积权重 |
| `lambda10_cumsum` | 前 10 主成分累积权重 |
