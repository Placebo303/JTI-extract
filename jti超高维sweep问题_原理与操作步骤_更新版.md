# JTI 超高维 / 超长 Frame Sweep 实现方案（二，更新版）：问题—原理与操作步骤

## 0. 文档定位

本文档用于从技术执行角度说明超高维 / 超长 frame JTI sweep 应如何落地。结构按照“问题—原理—操作步骤”展开，适合给 coding agent、Roo/Codex、实验数据处理人员或后续项目 handoff 使用。

本更新版引入两个关键技术约束：

1. `nearest` 和 `greedy_unique` 不是主物理配对算法，只能作为 pairing-bias diagnostics。
2. 主 JTI folding 必须使用固定全局 frame origin，并通过 edge guard 和 multi-origin sensitivity check 控制 frame boundary tearing。

目标不是直接替换现有 baseline，而是在不破坏原有 `_pairs_from_timetags()`、`_jti_from_pairs()`、`compute_schmidt_number_from_jti()` 科学语义的前提下，新增一套适合大维度 JTI 的外层分析路径。

---

## 1. 问题一：超高维 JTI 不能直接生成完整 dense matrix

### 原理

JTI 是一个二维 joint temporal intensity matrix。若时间 bin 数为 \(N\)，完整 JTI 的元素数为：

\[
N^2
\]

当 \(N\) 从几千提升到几万、几十万时，矩阵存储会迅速超过普通内存容量。对于 \(N=32768\)，已有约 \(1.07\times10^9\) 个元素；对于 \(N=318000\)，元素数约为 \(1.01\times10^{11}\)。

因此，完整 dense JTI 只适合小规模 validation，不适合作为超高维 sweep 的常规输出。

### 操作步骤

#### Step 1：保留小规模 dense validation

只在以下范围内生成 full dense JTI：

```text
N = 256, 512, 1024, 2048, 4096
```

用途：

```text
1. 验证新 accumulator 和旧 pipeline 一致；
2. 验证 folding 逻辑正确；
3. 作为 exact SVD / effective K 的参考基线。
```

#### Step 2：中高维默认输出 coarse JTI

无论真实 \(N\) 多大，都把全局 JTI rebin 到固定大小：

```text
coarse_N = 512, 1024, 2048, 4096
```

输出文件示例：

```text
coarse_jti/N32768_bw100ps_coarse1024.npz
coarse_jti/N32768_bw100ps_coarse2048.npz
```

该图用于观察：

```text
1. 主对角是否完整；
2. 是否存在边缘效应；
3. 是否存在长时间漂移；
4. 是否存在局部异常块；
5. 是否存在非对角背景。
```

#### Step 3：输出 diagonal profile

计算：

\[
D(k)=\sum_i \mathrm{JTI}(i,i+k)
\]

其中 \(k\) 是相对主对角偏移。

输出文件示例：

```text
diag_profiles/N32768_bw100ps_diag_profile.csv
```

该文件用于分析：

```text
1. coincidence 主峰宽度；
2. 背景水平；
3. 旁瓣结构；
4. 电子学周期性；
5. jitter / binwidth 是否主导对角宽度。
```

#### Step 4：输出 marginals

计算：

\[
R(i)=\sum_j \mathrm{JTI}(i,j)
\]

\[
C(j)=\sum_i \mathrm{JTI}(i,j)
\]

输出文件示例：

```text
marginals/N32768_bw100ps_row_marginal.csv
marginals/N32768_bw100ps_col_marginal.csv
```

用于观察单臂时间分布、边缘效应和 frame 内非均匀性。

#### Step 5：只对局部区域输出 selected tiles

对于需要高分辨率观察的区域，输出固定 tile：

```text
tile_size = 1024 or 2048
```

推荐 tile 类型：

```text
1. 主对角附近 tile；
2. frame 起点附近 tile；
3. frame 终点附近 tile；
4. coarse JTI 中发现异常的区域；
5. 非对角背景区域。
```

输出示例：

```text
tiles/N32768_bw100ps_tile_diag_000.npz
tiles/N32768_bw100ps_tile_diag_000.png
```

---

## 2. 问题二：超长 frame 会使 strict single-hit-per-frame 失效

### 原理

strict single-hit-per-frame 要求每个 frame 内每个通道只出现一个 hit。若 frame length 为 \(T\)，singles rate 为 \(R\)，则单通道每个 frame 的平均 hit 数为：

\[
\mu = RT
\]

Poisson 近似下，恰好一个 hit 的概率为：

\[
P_1=\mu e^{-\mu}
\]

当 \(T\) 增大时，多击 frame 会迅速增多，导致 strict single-hit 规则剔除大量数据。此时剩余数据不再是原始数据的无偏样本，而是经过强筛选后的子集。effective K 的变化可能反映 selection bias，而不是真实物理结构变化。

### 操作步骤

#### Step 1：保留 strict，但只作为 diagnostic baseline

不要删除旧 strict 方法。它应保留用于对照：

```text
method = strict_single_hit
```

但在超长 frame 下，strict 不作为主物理结论。

#### Step 2：主分析改为 G2-like coincidence accumulation

主分析不强制恢复唯一 pair，而是统计二阶相关直方图：

\[
G^{(2)}(t_s,t_i)
\]

可理解为：在固定物理 coincidence window 或固定分析窗口内，统计两通道 event pairs 的相关强度。

#### Step 3：使用固定物理 coincidence window

coincidence window 不应跟随 binwidth 或 frame length 自动变大。它应由实验系统决定，例如：

```text
1. SNSPD jitter；
2. TimeTagger timing resolution；
3. measured coincidence peak width；
4. optical/electronic timing drift；
5. expected pair correlation width。
```

推荐 sweep 几个固定窗口作为诊断：

```text
coincidence_window_ps = 100, 200, 300, 500
```

但主结果应选一个有物理依据的固定窗口。

#### Step 4：输出 strict selection-bias 诊断指标

每个 frame length 下输出：

```text
n_events_ch0
n_events_ch1
n_frames_common
n_strict_pairs
single_hit_retention_ratio
multi_hit_rejected_ratio
```

若 frame length 增大时 strict retention 快速下降，则 strict 结果不能作为主结论。

---

## 3. 问题三：nearest / greedy_unique 可能产生非物理配对

### 原理

`nearest` 和 `greedy_unique` 都是启发式硬配对算法。

在低计数率、低多击概率时，它们通常能近似 coincidence pairing。但当多个 photon 紧密相邻时，仅凭 arrival time 无法唯一确定真实 SPDC pair。

nearest 的风险：

```text
1. 偏向最小 |dt|；
2. 可能人为压窄 coincidence peak；
3. 在高亮度下会低估 timing spread。
```

`greedy_unique` 的风险：

```text
1. 避免 hit 重复使用，但不保证物理正确；
2. 依赖排序规则；
3. 依赖 conflict resolution；
4. 在局部多候选情况下可能产生任意性。
```

### 操作步骤

#### Step 1：将 nearest / greedy 降级为 diagnostic methods

保留：

```text
method = nearest
method = greedy_unique
method = strict_single_hit
method = folded_without_strict
```

但它们只用于 sensitivity check，不作为真实 pair ground truth。

#### Step 2：主结果以 G2-like accumulation 为准

主方法：

```text
method = g2_all_candidates
```

它统计所有满足固定 coincidence 条件的候选相关，而不是强制唯一配对。

#### Step 3：估计 accidental / background

为了避免 all-candidate 带来偶然符合膨胀，需要估计背景。

可选方法：

```text
1. sideband background；
2. time-shifted channel background；
3. off-diagonal background；
4. large-delay shifted coincidence histogram。
```

输出：

```text
raw_candidate_counts
background_estimate
background_subtracted_counts
accidental_fraction
```

#### Step 4：比较不同 method 的稳定性

输出：

```text
diag_fraction_by_method
main_diag_width_by_method
K_coarse_by_method
K_truncated_by_method
background_fraction_by_method
```

判断：

```text
如果 g2_all_candidates、nearest、greedy_unique、strict 在低多击区域趋势一致，说明 pairing rule 不主导结果；
如果在高维/长 frame 下明显分歧，主结论以 raw g2_all_candidates 为准，并报告 method sensitivity。2026-04-29 consensus: 不默认扣除 background。
```

---

## 4. 问题四：不能对每个 pair 自己选择 frame origin

### 原理

如果每个 pair 使用自己的 \(t_s\)、\(t_i\) 或 \(t_{mean}\) 作为 frame origin，再做 modulo folding，那么每个 coincidence 都被局部对齐。

这会造成三个问题：

```text
1. 消除真实 frame 内长时间结构；
2. 掩盖边缘效应和时间漂移；
3. 使 JTI 不再对应一个固定的全局 time-bin basis。
```

因此，per-pair origin 得到的图不应称为全局 JTI。它更接近局部 correlation kernel。

### 操作步骤

#### Step 1：使用固定全局 frame lattice

对每个 sweep 点固定：

\[
t_0 = \text{global origin}
\]

\[
T = N\Delta t
\]

每个事件使用同一个 frame lattice：

\[
\text{frame index}=\left\lfloor\frac{t-t_0}{T}\right\rfloor
\]

\[
\text{bin index}=\left\lfloor\frac{(t-t_0)\bmod T}{\Delta t}\right\rfloor
\]

#### Step 2：禁止主流程使用 per-pair origin

禁止主分析中使用：

```text
origin = t_s of each pair
origin = t_i of each pair
origin = t_mean of each pair
```

#### Step 3：如果需要局部 kernel，必须另命名

如果未来确实需要研究局部 coincidence kernel，可以单独输出：

```text
local_correlation_kernel
```

但不能与 global JTI 混用，也不能用它直接解释 frame-length-dependent effective dimensionality。

---

## 5. 问题五：frame boundary tearing 会撕裂真实近邻 coincidence

### 原理

在 modulo folding 中，如果一个 coincidence 位于 frame 边界附近：

```text
t_s 位于 frame 末端
t_i 位于下一个 frame 开头
```

则普通 binning 会得到：

```text
bin_s ≈ N - 1
bin_i ≈ 0
```

物理上两者接近，但在普通矩阵图上相距很远。这个问题称为 boundary tearing。

### 操作步骤

#### Step 1：主流程使用 edge guard

设置：

```text
edge_guard_ps = max(coincidence_window_ps, 3 × jitter_ps)
```

例如：

```text
coincidence_window_ps = 200 ps
jitter_ps = 30–50 ps
edge_guard_ps = 200–300 ps
```

#### Step 2：剔除主 JTI 中的边界候选

对每个 coincidence candidate 或 diagnostic pair，计算：

```text
phase_s = (t_s - t0) mod T
phase_i = (t_i - t0) mod T
```

如果满足任一条件，则不进入主 JTI：

```text
phase_s < edge_guard_ps
T - phase_s < edge_guard_ps
phase_i < edge_guard_ps
T - phase_i < edge_guard_ps
```

这些事件不丢弃原始记录，而是进入 edge diagnostics。

#### Step 3：输出 edge 诊断指标

```text
edge_guard_ps
n_candidates_before_edge_guard
n_candidates_after_edge_guard
edge_rejection_ratio
edge_candidate_diag_profile
```

判断：

```text
edge_rejection_ratio 低：边界处理对主结论影响小；
edge_rejection_ratio 高：frame origin 或 frame length 需要重新审查。
```

#### Step 4：可选 torus-aware diagnostic

如果需要评估 modulo folding 的周期性解释，可输出 circular diagonal profile。

定义 circular distance：

\[
d_{circ}(i,j)=\min(|i-j|,N-|i-j|)
\]

但该结果只作为 boundary diagnostic，不作为默认主结果。

---

## 6. 问题六：frame origin 可能影响 folding 结果

### 原理

frame_origin_ps 决定事件落入 frame 的位置。如果 JTI、diagonal profile 或 effective K 对 origin 很敏感，说明结果可能被边界、稀疏采样或非平稳性主导。

### 操作步骤

#### Step 1：为每个 frame length 设置多个 global origins

建议：

```text
frame_origin_ps = 0
frame_origin_ps = T/4
frame_origin_ps = T/2
frame_origin_ps = 3T/4
```

其中 \(T=\) frame_length_ps。

#### Step 2：每个 origin 独立计算指标

对每个 origin 输出：

```text
n_candidates_used
edge_rejection_ratio
diag_fraction
main_diag_width_ps
K_coarse
K_truncated
row_marginal_uniformity
col_marginal_uniformity
```

#### Step 3：计算 origin sensitivity

例如：

```text
origin_sensitivity_K = std(K across origins) / mean(K across origins)
origin_sensitivity_diag = std(diag_fraction across origins) / mean(diag_fraction across origins)
origin_sensitivity_edge = std(edge_rejection_ratio across origins) / mean(edge_rejection_ratio across origins)
```

#### Step 4：禁止把多个 origin 当独立数据叠加

多个 origin 是同一批数据的不同切分方式，不是独立重复实验。

因此：

```text
可以用于 sensitivity check；
不能直接叠加为 4 倍采样量；
不能通过挑选最好看的 origin 作为主结果。
```

---

## 7. 问题七：超大矩阵无法做完整 SVD / Schmidt 计算

### 原理

Schmidt / effective mode number 常通过奇异值谱计算。若矩阵为 \(A\)，奇异值为 \(s_i\)，一种常用 effective mode number 形式为：

\[
K = \frac{\left(\sum_i s_i^2\right)^2}{\sum_i s_i^4}
\]

但完整 SVD 对大矩阵的内存和计算成本非常高。对于超高维 JTI，应采用 exact / coarse / truncated 分层策略。

### 操作步骤

#### Step 1：小维度 exact SVD

对小维度 dense JTI 做完整 SVD：

```text
N = 256, 512, 1024, 2048, 4096
```

输出：

```text
K_dense_exact
singular_values_full
```

用途：

```text
1. 检验旧 pipeline；
2. 检验新 accumulator；
3. 为后续 coarse / truncated 方法提供参考。
```

#### Step 2：中维度 coarse SVD

对真实大维度 JTI 做 coarse rebin：

```text
coarse_N = 1024, 2048, 4096
```

然后对 coarse JTI 做 exact SVD。

输出：

```text
K_coarse_1024
K_coarse_2048
K_coarse_4096
```

判断标准：

```text
如果 K_coarse 随 coarse_N 增大趋于稳定，说明主要结构被捕获；
如果 K_coarse 持续增长，说明当前 coarse resolution 不足或结构仍未饱和。
```

#### Step 3：大维度 sparse / truncated SVD

对于真正超高维，不显式存储 dense matrix，而是使用 sparse COO 或 LinearOperator。

需要实现两个操作：

```python
y = A @ x
z = A.T @ y
```

其中 \(A\) 可以由 sparse triples 或 accumulator 动态定义。

估计前 \(r\) 个 singular values：

```text
r = 128, 256, 512, 1024
```

输出：

```text
top_r_singular_values
K_truncated_r128
K_truncated_r256
K_truncated_r512
K_truncated_r1024
captured_frobenius_energy_r
```

#### Step 4：报告 truncated SVD 是否饱和

计算：

\[
E_r = \frac{\sum_{i=1}^{r}s_i^2}{\|A\|_F^2}
\]

其中 \(\|A\|_F^2\) 是 Frobenius norm。

判断：

```text
如果 E_r 接近 1，说明前 r 个模式已捕获主要能量；
如果 E_r 很低，说明 singular spectrum 没有饱和，不能声称得到完整 K。
```

---

## 8. 问题八：超高维结果可能受采样稀疏性支配

### 原理

当 \(N\) 极大但总 coincidence candidate 数有限时，JTI 会非常稀疏。此时 effective mode number 可能主要受 shot noise、有限采样、偶然符合和 sparse artifact 影响。

因此，超高维 sweep 不能只报告一个 K 值，必须报告统计稳定性。

### 操作步骤

#### Step 1：记录基础统计量

每个 sweep 点输出：

```text
n_events_ch0
n_events_ch1
n_candidates_total
n_candidates_after_edge_guard
nonzero_bins
nonzero_fraction
mean_counts_per_nonzero_bin
diag_band_counts_fraction
method_sensitivity_summary
```

#### Step 2：进行 bootstrap

建议流程：

```text
1. 从 event blocks 或 candidate blocks 中有放回重采样；
2. 每次生成 coarse JTI 或 sparse representation；
3. 每次计算 K_coarse 或 K_truncated；
4. 重复 20–50 次；
5. 输出均值和标准差。
```

优先使用 block bootstrap，而不是单个 candidate 完全独立重采样，因为相邻事件可能存在时间相关性。

#### Step 3：输出 bootstrap 指标

```text
bootstrap_K_mean
bootstrap_K_std
bootstrap_K_relative_std
```

判断：

```text
如果 bootstrap_K_relative_std 很大，说明数据量不足；
如果 bootstrap_K_relative_std 很小，说明该维度下的 effective mode estimate 较稳定。
```

---

## 9. 问题九：P_plus 只能说明长时间 coincidence 稳定性，不能说明最高维度

### 原理

`P_plus` 描述的是 paired coincidence 沿长 acquisition window 的分布情况。它可以反映：

```text
1. coincidence 是否在采集时间内均匀；
2. 是否存在宏观漂移；
3. 是否存在采集中断；
4. 是否存在长时间计数率不稳定。
```

但它不是单光子一阶相干时间，也不是 time-bin entanglement 最高维度的直接判据。

真正与物理最高维度相关的是 pump coherence horizon 与 biphoton timing correlation width 的比值。

一个常见估计是：

\[
d_{\max} \sim \frac{\tau_{\mathrm{pump/coh}}}{\Delta t_{\mathrm{bin}}}
\]

更保守地：

\[
d_{\max} \sim \frac{\tau_{\mathrm{pump/coh}}}{\max(\Delta t_{\mathrm{bin}}, \tau_{\mathrm{jitter}}, \tau_{\mathrm{corr}})}
\]

### 操作步骤

#### Step 1：重新定位 P_plus

在报告中写作：

```text
P_plus is used as a long-acquisition stability diagnostic for paired coincidence events, rather than as a direct measure of coherence time or dimensionality.
```

#### Step 2：用泵浦线宽估计 coherence horizon

若有效泵浦线宽为 \(\Delta \nu\)，可用如下量级估计：

```text
Lorentzian convention: tau_coh ≈ 1 / (π Δν)
loose convention: tau_coh ≈ 1 / Δν
```

需要注明：SPDC 的实际相关泵浦是 SHG 后的 pump field，因此最好使用频率倍频后泵浦光的有效线宽；若暂无实测值，可暂时用激光器标称线宽作 order-of-magnitude proxy。

#### Step 3：JTI sweep 检查是否覆盖 coherence horizon

例如：

```text
binwidth_ps = 100 ps
frame_length = 3 us, 10 us, 30 us
N = 30000, 100000, 300000
```

检查：

```text
1. JTI diagonal structure 是否稳定；
2. effective mode number 是否继续增长或趋于饱和；
3. method choice 是否改变结论；
4. origin sensitivity 是否足够低；
5. edge rejection 是否可控；
6. bootstrap stability 是否足够好。
```

---

## 10. 推荐模块设计

建议新增非侵入式模块：

```text
src/jti_extract/ultra/
    g2_accumulate.py
    fold_lattice.py
    accumulators.py
    background.py
    svd_estimators.py
    diagnostics_pairing.py
    sweep_ultra_jti.py
```

### g2_accumulate.py

功能：

```text
1. 从 timetag 中构建 G2-like coincidence candidates；
2. 支持固定 coincidence window；
3. 不强制唯一配对；
4. 输出 raw candidate counts。
```

### fold_lattice.py

功能：

```text
1. 定义 fixed global frame lattice；
2. 计算 frame index 和 bin index；
3. 实现 edge guard；
4. 禁止 per-pair origin；
5. 支持 multiple global origins。
```

### accumulators.py

功能：

```text
1. coarse JTI accumulator；
2. diagonal profile accumulator；
3. row / column marginal accumulator；
4. selected tile accumulator；
5. sparse COO accumulator。
```

### background.py

功能：

```text
1. sideband background；
2. time-shifted background；
3. off-diagonal background；
4. accidental fraction 估计。
```

### svd_estimators.py

功能：

```text
1. dense exact SVD；
2. coarse SVD；
3. sparse / truncated / randomized SVD；
4. captured energy 计算；
5. bootstrap K 统计。
```

### diagnostics_pairing.py

功能：

```text
1. strict_single_hit diagnostic；
2. nearest diagnostic；
3. greedy_unique diagnostic；
4. folded_without_strict diagnostic；
5. method sensitivity summary。
```

### sweep_ultra_jti.py

功能：

```text
1. 读取 sweep config；
2. 调用 G2-like accumulator；
3. 对多个 binwidth / frame_length / global origin / method 进行 sweep；
4. 输出 metrics CSV；
5. 生成图像和 summary。
```

---

## 11. 推荐输出目录结构

```text
ultra_jti_sweep_YYYYMMDD/
    config.yaml
    metrics/
        g2_coverage_summary.csv
        pairing_diagnostic_summary.csv
        origin_sensitivity_summary.csv
        edge_guard_summary.csv
        schmidt_effective_summary.csv
    coarse_jti/
        N32768_bw100ps_origin0_coarse1024.npz
        N32768_bw100ps_originT4_coarse1024.npz
    diag_profiles/
        N32768_bw100ps_origin0_diag_profile.csv
    marginals/
        N32768_bw100ps_origin0_row_marginal.csv
        N32768_bw100ps_origin0_col_marginal.csv
    tiles/
        N32768_bw100ps_origin0_tile_diag_000.npz
        N32768_bw100ps_origin0_tile_diag_000.png
    svd/
        N32768_bw100ps_origin0_truncated_rank512.npz
    figures/
        K_vs_frame_length.png
        edge_rejection_vs_frame_length.png
        origin_sensitivity.png
        diag_profile_overlay.png
        method_sensitivity.png
```

---

## 12. 推荐 sweep 顺序

### Stage 1：小规模 exact 对齐

```text
N = 512, 1024, 2048, 4096
binwidth_ps = 100
method = g2_all_candidates, strict, folded_without_strict, nearest, greedy_unique
origin = 0
edge_guard_ps = max(coincidence_window_ps, 3 × jitter_ps)
```

目标：确认新 accumulator 与旧 pipeline 在可计算范围内可比，并量化 strict / nearest / greedy 的 bias。

### Stage 2：origin 与 edge guard 验证

```text
N = 8192, 16384
binwidth_ps = 100
origin = 0, T/4, T/2, 3T/4
edge_guard_ps = 100, 200, 300 ps
```

目标：判断 frame folding 是否受到边界撕裂和 origin choice 主导。

### Stage 3：中维度 coverage sweep

```text
N = 8192, 16384, 32768
binwidth_ps = 100
frame_length = 0.819 us, 1.638 us, 3.277 us
method = g2_all_candidates
```

目标：避免 full dense matrix，使用 coarse JTI、diagonal profile 和 coarse SVD 观察结构是否稳定。

### Stage 4：泵浦 coherence horizon sweep

```text
frame_length = 3 us, 10 us, 30 us
binwidth_ps = 100
N = 30000, 100000, 300000
method = g2_all_candidates
```

目标：检查 JTI 结构和 effective mode number 是否在 pump-coherence-limited frame scale 下稳定。

### Stage 5：最终汇总

输出图：

```text
K vs frame_length
K vs binwidth
K vs method
K vs coarse_N
K vs truncated_rank
edge_rejection_ratio vs frame_length
origin_sensitivity vs frame_length
bootstrap_K_std vs frame_length
diag_profile overlay by frame_length
```

---

## 13. 最终判断标准

一个超高维 JTI sweep 结果可以被认为较可靠，需要同时满足：

```text
1. 主结果基于 G2-like correlation，而不是 nearest / greedy 硬配对；
2. nearest / greedy / strict 只作为 diagnostic，并且其偏差被报告；
3. fixed global origin 被明确使用；
4. per-pair origin 未用于 global JTI；
5. edge guard rejection ratio 可控；
6. multiple global origins 下主要结论稳定；
7. coarse_N 增大后 K 逐渐稳定；
8. truncated rank 增大后 captured energy 足够高；
9. bootstrap K 方差可接受；
10. diagonal profile 与 coincidence peak / jitter 物理一致；
11. P_plus 只作为 acquisition stability 辅助证据；
12. 物理解释与泵浦有效线宽给出的 coherence horizon 一致。
```

若以上条件不满足，则应将结果表述为 exploratory diagnostic，而不是最终 dimension certification。

---

## 14. 一句话执行版

先在固定全局 frame lattice 上，用固定 coincidence window 构建 G2-like coincidence correlation；主 JTI 使用 edge guard 避免边界撕裂，多 global origins 只用于 sensitivity check；nearest、greedy_unique、strict 只作为 pairing-bias diagnostic；小维度做 exact SVD，中维度做 coarse SVD，大维度做 sparse/truncated SVD，并同步报告 edge rejection、origin sensitivity、method sensitivity、background fraction 和 bootstrap stability。
