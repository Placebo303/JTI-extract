# Troubleshooting

## 安装与依赖

- `numpy is missing`: install the project environment with `python -m pip install -e .`.
- `matplotlib is required`: install plotting extras with `python -m pip install -e ".[plotting]"`.
- `cannot import TimeTagger`: install Swabian TimeTagger software and matching Python bindings, or use `parsed_timebin_data.npz`.
- `.ttbin` offline replay failing with `createTimeTaggerVirtual()`: prefer `TimeTagger.FileReader()` for offline event-stream reads and filter `event_types == 0` before channel selection.

## 数据路径

- `data dir not found`: verify `--data` and Windows/WSL path translation.
- `--ttbin is required`: `tdc_layer_scan` no longer has a machine-specific default input file.
- Missing NPZ fields: ensure `Ch` and `TimeTag` are present.

## Dense JTI + Schmidt 分析的常见问题

> 超高维 / 超长 frame 场景下，不应默认使用 dense JTI + full SVD。优先参考 [`CURRENT_TASK.md`](../CURRENT_TASK.md) 与 [`WORKFLOWS.md`](WORKFLOWS.md) Workflow 7 的 fixed-lattice G2-like sweep。

### 内存不足（OOM）

**症状**: `MemoryError`、进程被 OOM killer 终止、系统卡死。

**原因**: Dense JTI 矩阵大小为 `N×N` float64 = `8×N²` 字节。SVD 需额外约 `3×8×N²` 字节临时内存。

| dimensions (N) | JTI 矩阵大小 | SVD 峰值估算（约） | 总峰值估算 |
|----------------|-------------|-------------------|-----------|
| 512            | 2 MB        | 6 MB              | ~8 MB     |
| 1024           | 8 MB        | 24 MB             | ~32 MB    |
| 2048           | 32 MB       | 96 MB             | ~128 MB   |
| 4096           | 128 MB      | 384 MB            | ~512 MB   |
| 8192           | 512 MB      | 1.5 GB            | ~2 GB     |

**对策**:
- 从 `N=1024` 起步，按需增大；不要直接使用 `N≥4096` 除非确认内存充裕。
- 监控内存使用：运行前用 `free -h` 检查可用内存。
- 若仅需 Schmidt 指标而不需完整 JTI 矩阵可视化，优先使用较小 `N` 配合较大 `bw` 来增大 `frame_length_ps`。

### SVD 计算耗时过长

**症状**: `jti-schmidt` 长时间无响应。

**原因**: Dense SVD 时间复杂度约 O(N³)。`N=1024` 通常在秒级完成，`N=4096` 可能需要分钟级。

**对策**:
- 避免不必要的过大 `N`。
- 先用小 `N` 快速扫描，确认参数范围后再用较大 `N` 精细分析。

### 大 binwidth_ps 导致时间分辨率下降

**症状**: JTI 热图中快速时间结构（如窄峰、精细振荡）被抹平或不可见。

**原因**: `binwidth_ps` 决定了 JTI 的时间分辨率。大 `bw`（如 10000 ps）将 10 ns 内的事件合并到一个 bin 中，任何亚-10 ns 的结构都会被平均掉。

**对策**:
- 理解覆盖范围与分辨率的权衡：大 `bw` 增大 `frame_length_ps`（覆盖更长时间相关结构），但降低分辨率。
- 若需同时覆盖长相关时间并保持高分辨率，考虑增大 `N`（但内存按平方增长）。
- 对比不同 `bw` 下的 Schmidt 指标：若大 `bw` 下 `schmidt_number` 收敛但小 `bw` 下更高，说明存在被大 `bw` 抹平的精细结构。

### frame_origin 对大 bw 的影响

**症状**: 不同 `--frame-origin-ps` 值下结果差异显著，且大 `bw` 时更敏感。

**原因**: `frame_origin_ps` 决定 JTI 帧的起始时间。大 `bw` 下每个 bin 覆盖更宽的时间窗口，帧起点偏移一个 `bw` 就可能将峰值从一个 bin 移到相邻 bin，显著改变分布。

**对策**:
- 默认 `--frame-origin-ps 0` 通常是最安全的选择。
- 对于关键参数组合，使用 `--scan-frame-origin` 或手动尝试不同 `frame_origin_ps` 值，确认结果对帧起点不敏感。
- 若结果高度依赖 `frame_origin_ps`，考虑减小 `bw` 或报告该敏感性。

### P_plus 误解为单光子相干时间

**症状**: 使用 `P_plus_central_95_width_ps` 作为单光子相干时间估计，得出不合理结论。

**原因**: `P_plus` 是 paired coincidence 对角 profile 的统计量，反映 coincidence 事件在对角线附近的集中程度和采集稳定性，**不是**单光子相干时间的直接测量。

**对策**:
- 不要将 `P_plus` 指标（`P_plus_central_95_width_ps`、`width_ratio_95` 等）等同于单光子相干时间。
- 小规模 dense validation 可使用 Schmidt 模式数随 `frame_length_ps` 的收敛判据（参见 [`WORKFLOWS.md`](WORKFLOWS.md) Workflow 6 和 [`SCHMIDT_ANALYSIS.md`](SCHMIDT_ANALYSIS.md)）。超高维 / 超长 frame 主线应使用 [`WORKFLOWS.md`](WORKFLOWS.md) Workflow 7 的 fixed-lattice G2-like sweep。
- `P_plus` 适合用于诊断采集稳定性、对角集中度和 auto-dim 决策，不适合作为相干时间判据。

### 数据覆盖风险

**症状**: 意外覆盖原始数据或已有分析结果。

**对策**:
- **禁止**覆盖 `*.ttbin` 原始数据文件。
- **禁止**覆盖 `results/` 目录下已有生成物。
- **禁止**覆盖时间戳命名的输出目录（如 `pplus_auto_dim_*`）。
- 每次运行 `jti-extract` 或 `jti-schmidt` 时使用新的输出目录或文件名。
- 运行前用 `git status` 和 `git diff` 检查工作区状态。
- 考虑将重要结果目录设为只读：`chmod -R a-w results/important_run/`。

## Ultra-high-dimensional fixed-lattice G2-like sweep 常见问题

### all-candidate G2 raw counts 的偶然符合解释风险

**症状**: raw candidate counts 随 singles rate 或 `coincidence_window_ps` 增大而快速增加，strict / nearest / greedy diagnostics 与 `g2_all_candidates` raw-count 主结果强分歧。

**原因**: `g2_all_candidates` 不强制唯一配对。高 singles rate 或过宽 `coincidence_window_ps` 会引入大量偶然符合。

**对策**:
- `coincidence_window_ps` 必须来自 measured coincidence peak、jitter、electronics，而不是跟随 frame length 变大。
- 当前共识是不扣除 background；不要默认输出 background-subtracted signed spectrum。
- 若偶然符合解释风险高，不要把 raw `K` 解释为 final dimension certification；应报告 method sensitivity、edge/origin sensitivity 与 coincidence-window 选择依据。

### strict single-hit selection bias

**症状**: frame length 增大后 `n_strict_pairs` 或 `single_hit_retention_ratio` 快速下降，strict 的 `K` 与 `g2_all_candidates` 趋势分歧。

**原因**: [`_pairs_from_timetags()`](../src/jti_extract/cli/extract.py:258) 要求每个 frame 每通道只有一次 hit。超长 frame 下多击帧会被大量剔除。

**对策**:
- strict 只作为 diagnostic baseline。
- 主结果使用 raw `g2_all_candidates`，并用 diagnostics 解释 selection bias；不默认扣除 background。
- 必须报告 `n_strict_pairs`、`single_hit_retention_ratio`、`multi_hit_rejected_ratio`。

### nearest / greedy_unique heuristic bias

**症状**: [`nearest_pairs()`](../src/jti_extract/cli/tdc_layer_scan.py:307) 或 [`greedy_unique_pairs()`](../src/jti_extract/cli/tdc_layer_scan.py:327) 给出更窄 diagonal profile、更小 timing spread 或与 G2-like 主结果不同的 `K` 趋势。

**原因**: nearest 偏向最小 `|dt|`，greedy_unique 依赖排序和 conflict resolution；二者都不是真实物理 pair recovery。

**对策**:
- nearest / greedy_unique 只用于 method sensitivity。
- 若这些 diagnostics 与 G2-like 分歧，应以 raw `g2_all_candidates` 主结果为准，并报告分歧。

### boundary tearing 与 edge guard

**症状**: diagonal profile 在 frame 边界附近异常，或不同 `frame_origin_ps` 下结果差异很大。

**原因**: 固定 global frame lattice 下，跨 frame 边界的近邻 coincidence 会被画到矩阵两端。

**对策**:
- 主 JTI 使用 `edge_guard_ps = max(coincidence_window_ps, 3 * jitter_ps)`。
- 输出 `edge_rejection_ratio` 和 edge diagnostics。
- 多 origins 只用于 sensitivity check，不能叠加为更多样本，也不能挑选最好看的 origin 作为主结果。

### background-subtracted matrix 被误引入或误称为 Schmidt number

**症状**: 对 background-subtracted signed matrix 直接套用 `JTA = sqrt(probability)` 或称为 Schmidt number。

**原因**: background subtraction 后矩阵可能有负值，已不再是 nonnegative probability counts。

**对策**:
- raw nonnegative counts 可使用 Schmidt-like effective K。
- Stage B 默认不实现 background subtraction，也不输出 background-subtracted signed matrix。
- 若未来另开任务引入 signed matrix，只能称为 `singular-spectrum effective rank` 或 `background_subtracted_singular_spectrum`。
- 不要直接使用 [`compute_schmidt_number_from_jti()`](../src/jti_extract/cli/schmidt.py:94) 处理负值矩阵。

### sparse sampling / shot-noise dominated regime

**症状**: `nonzero_fraction` 极低，`mean_counts_per_nonzero_bin` 接近 1，selected tiles 像随机散点，bootstrap `K` 方差大。

**原因**: 超高维下 bin 数远大于 coincidence candidates，effective-mode estimate 可能主要反映 shot noise。

**对策**:
- 增大 coarse rebin，降低 effective resolution。
- 增加采集时间或减少 `N`。
- 使用 block bootstrap，并报告 `bootstrap_K_relative_std`。
- 若 bootstrap 方差大，不要声称 K 收敛。
