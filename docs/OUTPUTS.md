# 输出格式

自动延时（`tau_auto` 等）只增加 metadata 字段，**CSV / NPZ 的 schema 与 0.3.0 完全一致**。

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
np.load("H_raw_aligned.npz")["jti_counts"]      # (dim, dim) float64
np.load("H_raw_aligned.npz")["dimension"]       # int
np.load("H_raw_aligned.npz")["bin_width_ps"]    # int
np.load("H_raw_aligned.npz")["frame_origin_ps"] # float
np.load("H_raw_aligned.npz")["tau_align_ps"]    # float（实际应用的整数 ps）
np.load("H_raw_aligned.npz")["delay_min_ps"]    # int
np.load("H_raw_aligned.npz")["delay_max_ps"]    # int
np.load("H_raw_aligned.npz")["guard_bins"]      # int
```

键集合未变；`jti_counts[i, j]` 中 `i` = A 侧 bin、`j` = B 侧 bin。

## H_raw_aligned.png

viridis 热图，lower origin，x/y 轴为 bin index，colorbar label = "Counts"。
需要 matplotlib（属于可选 extra `[plotting]`）。

## raw_aligned_meta.json

完整 metadata。自动延时相关的新增字段：

| 字段 | 说明 |
|---|---|
| `tau_align_ps` | 实际应用的全局 B 通道延时（整数 ps；显式 / peaks CSV 时可能是浮点原值） |
| `tau_align_source` | `explicit` / `auto_correlation` / `brightest_peak` |
| `tau_auto` | 自动估计诊断对象；显式 tau 或 peaks CSV 时为 `null`（结构见 [CLI.md](CLI.md#metadata-字段)）。其中 `coarse.near_equal_candidates` / `coarse.n_near_equal` 记录接近等高的候选簇，`refine_used` 表示精修结果是否被采用 |
| `delay_window_center_ps` | residual 延时窗实际中心（ps），通常 0；`--auto-delay-range` 时为实测残余峰 |
| `delay_range_auto_centered` | 是否由 `--auto-delay-range` 自动居中（bool） |

其余关键字段：

- `count_balance_error`：`accepted_pairs - retained - cross_frame - edge - invalid`，必须为 0
- `delay_span_exceeds_frame_period`：boolean，delay range 是否超过 frame period
- `weighted_mean_diag_offset_ps` / `weighted_std_diag_offset_ps`：加权平均 / 标准差对角线偏移（ps）
- `max_diag_offset_ps` / `max_diag_offset_bins`：最大对角线偏移
- `K_raw_aligned`：Schmidt-like K（`--compute-svd` 时）
- `purity`：`1/K`（`--compute-svd` 时）
- `--compute-svd` 时还会追加 `singular_values`、`lambda_weights` 数组

完整字段表见 [CLI.md](CLI.md#metadata-字段)。

## residual_tau_histogram.csv

| 列 | 说明 |
|---|---|
| `residual_tau_ps` | 残差延时 bin 中心（ps） |
| `counts` | 该 bin 的事件对数 |

bin 数 = `floor((delay_max - delay_min) / binwidth) + 1`；当 span 不是 binwidth 整数倍时，
最后一个 bin 只被 `delay_max` 截掉一部分（实际只统计到 `delay_max`，因此该 bin 计数偏低）。列 schema 未变。

## residual_tau_histogram.png

线图，x 轴 = residual tau (ps)，y 轴 = counts。标注 `residual_tau = 0 ps` 竖线。
title 中写入 `tau_align_ps` 值。

## _tag_cache/tags_cache_ch{A}_ch{B}.npz

从 `.ttbin` 解析出的 A/B 时间标签缓存（`<out>/_tag_cache/` 下，约几十 MB，取决于事件数）。
它的作用是让同一数据反复试参数时不必重新解析 ttbin。

| key | 内容 |
|---|---|
| `t_a` | A 通道时间标签（int64，升序） |
| `t_b` | B 通道时间标签（int64，升序） |
| `meta_json` | JSON 字符串：ttbin 绝对路径、大小、mtime、通道号、`max_events`、读取事件数、各通道计数、event type 计数、文件 configuration 等 |

缓存 key = ttbin 绝对路径 + 文件大小 + mtime + 通道号 + `--max-events`：

- 换 `--out`（缓存目录在 out 下）、换通道号、改 `--max-events`、`.ttbin` 被覆盖或改名 → 重新解析 ttbin；
- 改 `--tau-*` / `--delay-*` / `--binwidth-ps` 等参数**不会**失效，可以复用；
- 缓存是可删的中间产物，删除后下次运行会重新写。

## summary.csv（`--compute-svd` 时）

| 列 | 说明 |
|---|---|
| `tau_align_ps` | 实际使用的全局延时（ps） |
| `tau_align_source` | `explicit` / `auto_correlation` / `brightest_peak` |
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
