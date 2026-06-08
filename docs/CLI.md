# CLI 参考

## jti-raw-aligned（主程序）

Raw-aligned FPC JTI 提取。只做全局坐标校准，不做 per-tooth ROI 筛选、peak_id 分配、comb line 重排。

### 必需参数

| 参数 | 说明 |
|------|------|
| `--ttbin` | Path to `.1.ttbin` 文件 |
| `--peaks-csv` | Path to `pminus_peaks.csv`（必须有 `delay_ps` 和 `counts` 列） |
| `--out` | 输出目录 |

### 可选参数 — 坐标校准

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--tau-align-ps` | 自动（最亮峰） | 显式指定 `tau_align_ps`（ps） |
| `--frame-origin-ps` | 0 | Frame origin（ps） |
| `--binwidth-ps` | 20 | Bin width（ps） |
| `--dimensions` | 128 | JTI 矩阵维度 |
| `--guard-bins` | 2 | Edge guard bins |

### 可选参数 — Delay Range

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--delay-min-ps` | 自动 | 全局 residual delay window 下界（ps） |
| `--delay-max-ps` | 自动 | 全局 residual delay window 上界（ps） |
| `--delay-window-ps` | 无 | 快捷方式：`delay_min=-W, delay_max=+W` |

优先级：`--delay-min/max-ps` > `--delay-window-ps` > `±(frame_period//2 - guard_ps)`

### 可选参数 — TimeTagger 通道

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--raw-ch-a-id` | 2 | TimeTagger channel A |
| `--raw-ch-b-id` | 3 | TimeTagger channel B |

### 可选参数 — 性能

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--max-events` | 无（全部） | 最大读取事件数 |
| `--chunk-size` | 50000 | Chunk streaming 配对大小 |

### 可选参数 — SVD

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--compute-svd` | false | 计算 SVD/K 并输出 `summary.csv` |

### 输出文件

| 文件 | 说明 |
|------|------|
| `H_raw_aligned.csv` | JTI 矩阵 CSV |
| `H_raw_aligned.npz` | JTI 矩阵 NPZ（含 metadata） |
| `H_raw_aligned.png` | JTI 热图（viridis） |
| `raw_aligned_meta.json` | 完整 metadata |
| `residual_tau_histogram.csv` | 残差延时直方图 |
| `residual_tau_histogram.png` | 残差延时直方图 |
| `summary.csv` | SVD/K 结果（`--compute-svd` 时） |

### 示例

```bash
# 基本用法（自动 delay range）
jti-raw-aligned \
  --ttbin data.1.ttbin \
  --peaks-csv pminus_peaks.csv \
  --out results/

# 指定 delay range + SVD
jti-raw-aligned \
  --ttbin data.1.ttbin \
  --peaks-csv pminus_peaks.csv \
  --tau-align-ps 830 \
  --binwidth-ps 40 --dimensions 80 --guard-bins 2 \
  --delay-min-ps -1500 --delay-max-ps 300 \
  --raw-ch-a-id 2 --raw-ch-b-id 3 \
  --compute-svd \
  --out results/

# 也可以用 module 方式调用
python -m jti_extract.cli.raw_aligned --ttbin ... --peaks-csv ... --out ...
```

### Metadata 字段

`raw_aligned_meta.json` 包含以下字段：

```json
{
  "analysis_mode": "raw_aligned_fpc_jti",
  "pairing_mode": "global_residual_delay_window",
  "tau_align_ps": 830.0,
  "tau_align_source": "brightest_peak",
  "frame_origin_ps": 0,
  "binwidth_ps": 40,
  "dimension": 80,
  "frame_period_ps": 3200,
  "guard_bins": 2,
  "delay_min_ps": -1500,
  "delay_max_ps": 300,
  "delay_span_ps": 1800,
  "delay_span_exceeds_frame_period": false,
  "delay_span_warning": null,
  "background_subtracted": false,
  "tooth_roi_filtered": false,
  "line_rearranged": false,
  "peak_id_assigned": false,
  "per_tooth_matrix_generated": false,
  "raw_noise_preserved": true,
  "accepted_pairs_input": 41947,
  "retained_in_jti": 36083,
  "cross_frame_rejected": 4050,
  "edge_rejected": 1814,
  "invalid_bin": 0,
  "count_balance_error": 0,
  "weighted_mean_diag_offset_ps": -319.64,
  "weighted_std_diag_offset_ps": 348.84,
  "max_diag_offset_bins": 75,
  "max_diag_offset_ps": 1500,
  "K_raw_aligned": 4.6299,
  "purity": 0.215989,
  "n_singular_values": 92,
  "lambda1": 0.358908,
  "lambda2": 0.248119,
  "lambda3": 0.136365,
  "lambda5_cumsum": 0.838533,
  "lambda10_cumsum": 0.925180
}
```
