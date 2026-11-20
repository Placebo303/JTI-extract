# 方法（Method）

本文档给出 `jti-raw-aligned` 的坐标定义、延时校准、矩阵累加与 Schmidt-like K 公式。
本仓库只负责 **JTI 产出**：不做多峰拆分、不做 per-tooth ROI、不分配 peak_id、不做背景扣除。

## 1. 记号

| 记号 | 含义 |
|---|---|
| `t_A`, `t_B` | A / B 两个逻辑通道的原始时间标签（整数 ps，来自 `.ttbin`） |
| `N`（`dimensions`） | JTI 维度 |
| `w`（`binwidth_ps`） | bin 宽度（ps） |
| `T = N w` | frame period（ps） |
| `t_0`（`frame_origin_ps`） | 帧原点（ps） |
| `g`（`guard_bins`） | 帧边缘保护 bin 数，`guard_ps = g w` |
| `τ_align`（`tau_align_ps`） | 全局 B 通道延时补偿（整数 ps） |

## 2. 全局延时校准 `τ_align`

`t_B_corr = t_B − τ_align`。`τ_align` 的来源按优先级取第一个可用的：

1. `--tau-align-ps`（显式给出）；
2. `.ttbin` 时间标签互相关（`--tau-auto`，或没有给 `--peaks-csv`）；
3. `--peaks-csv` 中 `counts` 最大那一行的 `delay_ps`。

### 2.1 互相关自动估计

对满足 `|t_B − t_A| ≤ W`（`W = --tau-search-window-ps`，默认 25 ns）的所有有序 A-B 配对，
统计 `Δτ = t_B − t_A` 的直方图：

$$C(\Delta\tau) = \#\{(t_A, t_B) : \Delta\tau - w_0/2 \le t_B - t_A < \Delta\tau + w_0/2\}$$

其中 `w_0 = --tau-coarse-bin-ps`（默认 20 ps）。这就是两路时间标签流的（加窗）互相关，
不需要任何外部峰表。然后：

1. **粗测**：对 `C` 做宽度 `s = --tau-smooth-ps`（默认 300 ps，约一个 FP 腔 FSR / 梳齿簇尺度）
   的 boxcar 平滑，取内区（去掉一个平滑核宽度）的最大值。boxcar 会把窄峰抹成平顶，
   故取平顶中心作为峰位；若只有一个 bin 达极大值，再用抛物线插值到亚 bin。
2. **精修**（默认开，`--no-tau-refine` 可关）：以粗测峰为中心 ±`--tau-refine-window-ps`（默认 300 ps）
   内改用 `--tau-refine-bin-ps`（默认 2 ps）细分箱，取环带（窗口外 300 ps 内）背景中位数，
   扣除背景后计算该簇的质心，得到 `τ_exact`（可带小数）。
3. **应用**：`τ_align = round(τ_exact)`。

可靠性判定（都写进 `raw_aligned_meta.json` 的 `tau_auto`）：

- 显著性 $S = (h_{peak} - b)\,k / \sqrt{b\,k}$，其中 `h` 为平滑峰高、`b` 为平滑背景中位数、
  `k` 为平滑 bin 数；`S < 5` 时告警，精修 `S < 5` 时退回粗测值（`refine_used = false`）。
- 平滑峰距搜索窗边界不足一个平滑核时 `at_search_edge = true` 并告警。
- 高度 ≥ 最大值 98% 的其它平滑峰作为候选簇列入 `near_equal_candidates`（梳齿 / 多模数据的
  “延时应取哪一簇”是模式选择，不是唯一解）。
- 搜索窗内配对数 < 5000（`TAU_AUTO_MIN_TRUSTED_PAIRS`）时告警：小样本容易锁到背景涨落。

## 3. Residual delay 窗口

只保留满足下式的有序 A-B 配对（不去重、不分配配对编号）：

$$\text{delay\_min} \le t_B^{\text{corr}} - t_A \le \text{delay\_max}$$

窗口来源：`--delay-min-ps`/`--delay-max-ps` > `--delay-window-ps`（半宽）> 默认半宽
`T/2 - guard_ps`。`--auto-delay-range` 时窗口中心取实测残余峰而不是 0 ps
（实测峰不可信时保持 0 ps 并告警）。

## 4. 帧坐标与 edge guard

对 `t ∈ {t_A, t_B_corr}`：

$$u = t - t_0,\qquad f = \lfloor u / T \rfloor,\qquad x = u - f T$$

- 只保留 **同一帧** 的配对：`f_A = f_B`；
- 帧内位置必须满足 `guard_ps ≤ x < T - guard_ps`；
- 其余配对分别计入 `cross_frame_rejected`、`edge_rejected`。

## 5. 矩阵累加

对通过筛选的每个配对：

$$i = \lfloor x_A / w \rfloor,\qquad j = \lfloor x_B / w \rfloor,\qquad H[i, j] \mathrel{+}= 1$$

`H` 是**绝对计数**矩阵（`normalization = none`，不做背景扣除）。计数守恒必须满足

$$\text{accepted} = \text{retained} + \text{cross\_frame} + \text{edge} + \text{invalid},\qquad
\text{count\_balance\_error} = 0$$

## 6. Schmidt-like K（`--compute-svd`）

代码实现（`_compute_svd_k`）：

$$P = H / \sum_{ij} H_{ij},\qquad A = \sqrt{P},\qquad A = U \Sigma V^T$$

取 `s_i = Σ_ii > 1e-12`，权重与 K：

$$\lambda_i = \frac{s_i^2}{\sum_j s_j^2},\qquad \text{purity} = \sum_i \lambda_i^2,\qquad K = \frac{1}{\text{purity}}$$

`summary.csv` 与 meta 里另外给出 `n_singular_values`、`singular_values`、`lambda_weights`、
`lambda1/2/3`、`lambda5_cumsum`、`lambda10_cumsum`。

注意：`K` 依赖 `w` 与 `N`，不同 frame period 之间的 K 不可直接比较；
`w` 低于探测器 jitter 时属于过采样。

## 7. 实现与输入

- **输入只支持 `.ttbin`**：通过 Swabian `TimeTagger.FileReader` 读取，只取 `event type = 0`，
  按通道号拆成 A / B 两路并排序；缓存到 `<out>/_tag_cache/tags_cache_ch{A}_ch{B}.npz`。
- 配对与分箱是**分块流式**的：每个 A 块用 `searchsorted` 找候选 B，再直接累加 `H` 与 residual 直方图，
  不展开保存全量配对，内存有界。
- 输出：`H_raw_aligned.csv/npz/png`、`residual_tau_histogram.csv/png`、`raw_aligned_meta.json`，
  `--compute-svd` 时另有 `summary.csv`。

## 8. 验证

- 单元测试：`python -m pytest -q` → 26 passed，其中 16 个覆盖自动延时
  （已知延时的合成时间标签、峰值定位、优先级、候选簇、低统计量降级）。
- 真实数据（FP #1 set1，`ii-DF776.348-1_2026-08-07_161354.1.ttbin`，ch1/ch3，
  全量 3,540,005 A / 2,959,183 B 事件）：自动估计 `τ_align ≈ −119 ps`
  （粗测 −126.2 ps / 28.2σ；精修 −118.9 ps / 39.8σ），`count_balance_error = 0`。
  历史“peaks CSV + 300 ps 平滑峰”流程给 −130 ps，两者差约 10 ps（< 一个 40 ps bin）；
  需要复现历史值时显式 `--tau-align-ps -130`。
