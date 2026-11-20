# CLI 参考

## jti-raw-aligned（主程序）

Raw-aligned JTI 提取，唯一推荐的提取入口。只做全局坐标校准：全局 B 通道延时补偿 + 全局
residual-delay window 配对 + 非循环、edge-guarded 分箱。不做 per-tooth ROI 筛选、不分配 peak_id、
不做 comb line 重排、不做背景扣除。

调用方式（等价）：

```bash
jti-raw-aligned --ttbin data.1.ttbin --out results/            # 安装后
python -m jti_extract.cli.raw_aligned --ttbin data.1.ttbin --out results/   # 模块方式
```

> 未 `pip install -e .` 时，模块方式必须在**仓库根目录**执行（根目录 `jti_extract/__init__.py` 是 dev shim）。

### 必需参数

| 参数 | 说明 |
|---|---|
| `--ttbin` | `.1.ttbin` 数据分片路径（不要指向 0 字节的 `.ttbin` 占位文件） |
| `--out` | 输出目录（不存在会自动创建） |

### 延时校准参数（决定 `tau_align_ps`）

`tau_align_ps` 是全局 B 通道延时补偿量：`t_B_corr = t_B - tau_align_ps`。
解析优先级（`resolve_tau_align_ps`）：

1. `--tau-align-ps` 显式值 → `tau_align_source = "explicit"`；
2. `--tau-auto`，**或没有给 `--peaks-csv`** → 用 `.ttbin` 时间标签互相关自动估计 →
   `tau_align_source = "auto_correlation"`；
3. 否则读 `--peaks-csv` 的**最亮峰** → `tau_align_source = "brightest_peak"`。

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--peaks-csv` | 无（可选） | 峰表 CSV，必须含 `delay_ps`、`counts` 两列；只用于“最亮峰”定 tau |
| `--tau-align-ps` | 无 | 显式 `tau_align_ps`（ps），优先级最高 |
| `--tau-auto` | 关闭 | 即使给了 `--peaks-csv` 也强制用互相关估计 |
| `--tau-search-window-ps` | 25000 | 互相关搜索半窗（ps），即只看 `|t_B - t_A| <= W` 的配对 |
| `--tau-coarse-bin-ps` | 20 | 粗测直方图分箱（ps） |
| `--tau-smooth-ps` | 300 | 粗测 boxcar 平滑宽度（ps），约取一个梳齿簇 / FP 腔 FSR 尺度 |
| `--tau-refine` / `--no-tau-refine` | 开 | 是否做细分箱质心精修（2 ps bin） |
| `--tau-refine-window-ps` | 300 | 精修质心窗口半宽（ps） |
| `--tau-refine-bin-ps` | 2 | 精修分箱（ps） |

自动估计（`method = "auto_correlation"`）的过程：

1. 对 `|t_B - t_A| <= tau_search_window_ps` 的所有 A-B 配对做 `Δt = t_B - t_A` 直方图
   （`tau_coarse_bin_ps` 分箱）。这就是两路时间标签流的加窗互相关，不需要外部峰表。
2. 按 `tau_smooth_ps` 做 boxcar 平滑，取最亮峰作为粗测。boxcar 会把窄峰抹成平顶，
   代码用“平顶取中心”消除该偏差；单 bin 极大值再用抛物线插值到亚 bin。
3. 精修：以粗测峰为中心 ±`tau_refine_window_ps` 内改用 `tau_refine_bin_ps` 细分箱，
   扣掉环带背景后取该符合簇的质心，得到 `tau_align_ps_exact`（ps，可为小数）。
4. 应用 `t_B_corr = t_B - round(tau_align_ps_exact)`。

诊断量：显著性 `S = (peak - background) * k / sqrt(background * k)`（k = 平滑 bin 数）；
精修显著性 < 5σ 时退回粗测值（meta 里 `refine_used = false`）；峰落在搜索窗边缘
（距边界不足一个平滑核）时 `at_search_edge = true` 并打印告警。

另外两个可靠性提示：

- **接近等高簇**：粗测直方图里若有多个平滑峰高度 ≥ 最大值的 98%，会打印
  `note: N near-equal correlation clusters ...`，并把候选峰位写进 meta 的
  `tau_auto.coarse.near_equal_candidates` / `n_near_equal`（梳齿/多模数据的“延时应取哪一簇”是模式选择，
  跨样本比较时建议固定 `--tau-align-ps`）。
- **配对不足**：搜索窗内 A-B 配对数 < 5000（`TAU_AUTO_MIN_TRUSTED_PAIRS`）时打印 WARNING，
  说明自动值可能锁到背景涨落上。

`--auto-delay-range` 的可信性门槛：残余峰由互相关实测，但要求配对数 ≥ 5000 且显著性 ≥ 5σ；
不满足时不挪窗、打印 WARNING 并保持 0 ps 中心。

### 帧几何参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--frame-origin-ps` | 0 | 帧原点（ps） |
| `--binwidth-ps` | 20 | JTI bin 宽度（ps） |
| `--dimensions` | 128 | JTI 维度 N；`frame_period_ps = N * binwidth_ps` |
| `--guard-bins` | 2 | 帧边缘保护 bin 数（`guard_ps = guard_bins * binwidth_ps`） |

### Delay Range（residual 延时窗）

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--delay-min-ps` | 自动 | residual 窗下界（ps） |
| `--delay-max-ps` | 自动 | residual 窗上界（ps） |
| `--delay-window-ps` | 无 | 半宽简写：`delay_min = -W, delay_max = +W`；配 `--auto-delay-range` 时为 `center ± W` |
| `--auto-delay-range` | 关闭 | 窗中心取“实测残余峰”（互相关峰 − 已用 tau），而不是 0 ps；实测峰不可信（配对数 < 5000 或 < 5σ）时退回 0 ps 并告警 |

优先级：`--delay-min-ps` / `--delay-max-ps` > `--delay-window-ps` > 默认半宽。

默认半宽 = `dimensions * binwidth_ps // 2 - guard_bins * binwidth_ps`。
`delay_span_ps >= frame_period_ps` 时会 `warnings.warn` 并在终端打印 WARNING
（跨帧剔除会变多），meta 里记录 `delay_span_exceeds_frame_period`。

### TimeTagger 通道

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--raw-ch-a-id` | 2 | 逻辑通道 A |
| `--raw-ch-b-id` | 3 | 逻辑通道 B |

必须与数据一致（FP #1 / FP #2 的 DF776.348 数据是 1/3）。选错时的报错会列出该文件里
实际存在的通道号。

### 性能与可选计算

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--max-events` | 无（全部） | 最多读取的原始事件数（试跑用） |
| `--chunk-size` | 50000 | JTI 流式配对块大小 |
| `--compute-svd` | 关闭 | 计算 Schmidt-like K 并写 `summary.csv` |

### 示例

```bash
# 1) 只给 ttbin：自动定延时
jti-raw-aligned --ttbin data.1.ttbin --raw-ch-a-id 1 --raw-ch-b-id 3 \
  --binwidth-ps 40 --dimensions 80 --guard-bins 2 --compute-svd --out results/

# 2) 用 peaks CSV 的最亮峰定延时（兼容旧流程）
jti-raw-aligned --ttbin data.1.ttbin --peaks-csv pminus_peaks.csv \
  --raw-ch-a-id 1 --raw-ch-b-id 3 --binwidth-ps 40 --dimensions 80 --out results_peaks/

# 3) 显式指定延时（复现历史结果）
jti-raw-aligned --ttbin data.1.ttbin --tau-align-ps -130 \
  --raw-ch-a-id 1 --raw-ch-b-id 3 --binwidth-ps 40 --dimensions 80 --out results_tau130/

# 4) 给了 peaks CSV 但仍想用互相关（对比）
jti-raw-aligned --ttbin data.1.ttbin --peaks-csv pminus_peaks.csv --tau-auto --out results_auto/

# 5) 只用一个窄窗 + 自动居中
jti-raw-aligned --ttbin data.1.ttbin --auto-delay-range --delay-window-ps 900 --out results_win/

# 6) 只做粗测（不平滑精修）
jti-raw-aligned --ttbin data.1.ttbin --no-tau-refine --out results_coarse/
```

### 输出文件

| 文件 | 说明 |
|---|---|
| `H_raw_aligned.csv` | JTI 矩阵（CSV，第一行/第一列为 bin 索引） |
| `H_raw_aligned.npz` | JTI 矩阵 + 元信息（`jti_counts`、`dimension`、`bin_width_ps`、`frame_origin_ps`、`tau_align_ps`、`delay_min_ps`、`delay_max_ps`、`guard_bins`） |
| `H_raw_aligned.png` | 热图（viridis） |
| `residual_tau_histogram.csv` | 配对后的 residual delay 直方图（`residual_tau_ps`、`counts`） |
| `residual_tau_histogram.png` | 同上，含 `residual_tau = 0` 竖线与 tau 标注 |
| `raw_aligned_meta.json` | 完整 metadata（见下） |
| `summary.csv` | 仅 `--compute-svd` 时写出（见 [OUTPUTS.md](OUTPUTS.md)） |
| `_tag_cache/tags_cache_ch{A}_ch{B}.npz` | A/B 时间标签缓存（几十 MB）；复用可免重新解析 ttbin |

### Metadata 字段（`raw_aligned_meta.json`）

基本字段：

- `analysis_mode` = `"raw_aligned_fpc_jti"`；`pairing_mode` = `"global_residual_delay_window"`
- `tau_align_ps`、`tau_align_source`（`explicit` / `auto_correlation` / `brightest_peak`）
- `frame_origin_ps`、`binwidth_ps`、`dimension`、`frame_period_ps`、`guard_bins`
- `delay_min_ps`、`delay_max_ps`、`delay_span_ps`、`delay_span_exceeds_frame_period`、`delay_span_warning`
- `delay_window_center_ps`、`delay_range_auto_centered`
- 约束标记：`background_subtracted`、`tooth_roi_filtered`、`line_rearranged`、`peak_id_assigned`、
  `per_tooth_matrix_generated`、`raw_noise_preserved`
- 计数：`accepted_pairs_input`、`retained_in_jti`、`cross_frame_rejected`、`edge_rejected`、
  `invalid_bin`、`count_balance_error`（应为 0）
- 对角线诊断：`weighted_mean_diag_offset_bins/ps`、`weighted_std_diag_offset_bins/ps`、
  `max_diag_offset_bins/ps`

`tau_auto`（自动估计诊断；未用自动估计时为 `null`）：

```json
{
  "method": "auto_correlation",
  "search_window_ps": 25000,
  "coarse_bin_ps": 20,
  "smooth_ps": 300,
  "n_pairs": 32998,
  "coarse": {
    "peak_ps": -126.2, "peak_bin": 1245,
    "peak_smoothed_counts": 34.87, "background_smoothed_counts": 10.87,
    "significance": 28.2, "at_search_edge": false,
    "smooth_bins": 15, "bin_ps": 20.0,
    "n_near_equal": 4,
    "near_equal_candidates": [
      {"peak_ps": -124.9, "smoothed_counts": 34.87},
      {"peak_ps": 445.2, "smoothed_counts": 34.2},
      {"peak_ps": 1921.6, "smoothed_counts": 33.9},
      {"peak_ps": 148.0, "smoothed_counts": 33.7}
    ]
  },
  "refine": {
    "method": "local_centroid", "peak_ps": -118.9,
    "half_window_ps": 300, "background_margin_ps": 300, "bin_ps": 2,
    "n_pairs": 3111, "background_per_bin": 1.0,
    "excess_counts": 2044.0, "significance": 39.8
  },
  "refine_used": true,
  "tau_align_ps_exact": -118.9,
  "tau_align_ps": -119
}
```

`--compute-svd` 时追加：`K_raw_aligned`、`purity`、`n_singular_values`、`singular_values`、
`lambda_weights`、`lambda1`、`lambda2`、`lambda3`、`lambda5_cumsum`、`lambda10_cumsum`
（算法见 [SCHMIDT_ANALYSIS.md](SCHMIDT_ANALYSIS.md)）。
