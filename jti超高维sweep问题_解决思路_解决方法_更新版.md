# JTI 超高维 / 超长 Frame Sweep 实现方案（一，更新版）：问题—解决思路—解决方法

## 0. 文档定位

本文档用于从规划、汇报和 agent handoff 角度整理当前 JTI sweep 面临的核心问题，并给出对应的解决思路与工程方法。

本更新版吸收了两个关键修正：

1. `nearest` 和 `greedy_unique` 都是启发式硬配对算法，在多光子或多个 coincidence candidate 紧密相邻时可能产生非物理配对，因此不能作为主物理配对算法，只能作为 pairing-bias diagnostic。
2. 不允许对每个 pair 单独选择 frame origin。主 JTI 必须建立在固定全局 frame lattice 上，并通过 edge guard 与 multi-origin sensitivity check 控制边界撕裂问题。

因此，当前推荐的主流程不再是：

```text
timetags → nearest / greedy pair list → modulo folding → dense JTI → full SVD
```

而应改为：

```text
timetags
→ fixed global frame lattice
→ G2-like coincidence accumulation / all-candidate correlation histogram
→ accidental or background estimation
→ coarse JTI / diagonal profile / marginals / selected tiles
→ effective mode / truncated singular-spectrum analysis

parallel diagnostics:
strict / nearest / greedy_unique / folded_without_strict
→ pairing-bias and stability check
```

核心原则是：主分析应以统计相关量为中心，而不是以唯一事件级硬配对为中心。

---

## 1. 问题一：完整 dense JTI 在超高维情况下内存不可承受

### 问题描述

传统流程通常是：

\[
\text{timetags} \rightarrow \text{strict frame JTI} \rightarrow \text{dense matrix} \rightarrow \text{full SVD}
\]

在低维或中等维度下，这个流程可行。但当维度 \(N\) 提升到几万甚至几十万时，完整 JTI 矩阵的内存占用会迅速失控。

例如，若 binwidth 为 100 ps：

- \(3.2\,\mu s\) frame length 对应约 \(N=32000\)；
- \(31.8\,\mu s\) frame length 对应约 \(N=318000\)。

此时 dense matrix 的存储规模为 \(N^2\)。对于 \(N=32768\)，矩阵已有约 \(1.07\times10^9\) 个元素；对于 \(N=318000\)，矩阵元素数约为 \(1.01\times10^{11}\)。即使使用 uint32，也可能达到数 GB 到数百 GB 的量级。

### 解决思路

不要把完整 \(N\times N\) JTI 当作唯一数据结构。JTI 应该被拆解成多种低内存视图：

1. 全局低分辨率 coarse JTI；
2. 主对角附近 diagonal band；
3. row / column marginals；
4. diagonal profile；
5. sparse COO 非零项；
6. selected tiles 局部高分辨率图。

这些视图共同描述 JTI 的主要结构，而不需要存储完整 dense matrix。

### 解决方法

建立如下数据流：

\[
\text{timetags} \rightarrow \text{G2-like correlation / coincidence candidates} \rightarrow
\begin{cases}
\text{coarse JTI} \\
\text{diagonal band} \\
\text{marginals} \\
\text{selected tiles} \\
\text{sparse representation}
\end{cases}
\]

具体输出建议：

```text
coarse_JTI_1024.npz
coarse_JTI_2048.npz
diag_profile.csv
row_marginal.csv
col_marginal.csv
selected_tiles/*.npz
selected_tiles/*.png
sparse_coo/*.npz
```

对于超高维 sweep，默认不输出完整 dense CSV。完整 dense JTI 只保留在小维度 exact validation 阶段使用。

---

## 2. 问题二：超长 frame 会导致 strict single-hit-per-frame 严重剔除数据

### 问题描述

当前 strict single-hit-per-frame 逻辑会要求一个 frame 内每个通道最多保留一个 hit。一旦 frame 变长，同一 frame 内出现多个 hit 的概率显著增加，从而导致大量 frame 被剔除。

如果 singles rate 为 \(R\)，frame length 为 \(T\)，则单通道每个 frame 内的平均 hit 数为：

\[
\mu = RT
\]

在 Poisson 近似下，单个 channel 恰好一个 hit 的概率为：

\[
P_1 = \mu e^{-\mu}
\]

如果两个 channel 都要求 single-hit，保留概率会进一步下降。随着 \(T\) 增大，strict single-hit 规则会从“去除复杂事件”变成“强 selection filter”，导致 JTI 和 effective mode 结果混入 selection bias。

### 解决思路

必须把主分析从 strict single-hit frame JTI 中解放出来。

主流程应统计 G2-like coincidence correlation histogram，而不是强行恢复每一个真实 SPDC pair。因为在多光子或高亮度条件下，仅凭两路 timetag 通常无法唯一判断哪个 signal hit 对应哪个 idler hit。

### 解决方法

推荐使用两层结构：

```text
主分析层：
G2-like all-candidate coincidence accumulation + diagnostics-only method/origin/edge sensitivity

2026-04-29 consensus: ultra 主结果保持 raw nonnegative `g2_all_candidates` counts；不默认扣除 background，也不输出 background-subtracted signed spectrum。

诊断层：
strict / nearest / greedy_unique / folded_without_strict，用于 pairing-bias sensitivity check
```

其中：

- `strict_single_hit`：旧 baseline，只作为 diagnostic；
- `nearest`：每个 hit 与最近的另一通道 hit 配对，但可能人为压窄 coincidence peak；
- `greedy_unique`：一对一贪心匹配，避免 hit 重复使用，但结果依赖排序与窗口；
- `folded_without_strict`：先按固定 coincidence window 形成候选，再 fold 进 frame，不因多击 frame 整体剔除。

关键原则：

```text
nearest / greedy_unique 不作为真实物理配对恢复算法；
它们只用于判断 JTI 结构和 effective mode trend 是否对 pairing heuristic 敏感；
主结果应以 G2-like correlation + background/accidental control 为准。
```

---

## 3. 问题三：nearest 和 greedy_unique 可能产生非物理配对

### 问题描述

当多个 photon 或多个 coincidence candidate 在时间上紧密相邻时，nearest 和 greedy_unique 都可能产生错误配对。

例如：

```text
channel s: s1, s2
channel i: i1, i2
```

如果 \(s_1,s_2,i_1,i_2\) 都落在一个很小时间窗口内，仅凭 arrival time 很难唯一判断真实 pair 是 \((s_1,i_1),(s_2,i_2)\) 还是 \((s_1,i_2),(s_2,i_1)\)。

nearest 会偏向最小 \(|dt|\)，可能人为压窄相关峰；greedy_unique 会避免重复使用 hit，但仍然依赖排序和局部冲突处理规则。

### 解决思路

不要把 pair list 当成“真实 pair ground truth”。在高维 JTI 分析中，更稳妥的观测量是二阶相关直方图：

\[
G^{(2)}(t_s,t_i)
\]

它统计的是两通道事件在时间上的相关强度，而不是对每一个 event 进行唯一物理归属。

### 解决方法

主流程采用：

```text
all-candidate coincidence accumulation within fixed physical coincidence window
+ sideband / time-shift / off-diagonal background estimation
+ optional accidental subtraction
```

并将 nearest / greedy / strict 放到诊断层：

```text
if G2-like JTI, nearest, greedy_unique, strict 在低多击区域趋势一致：
    说明 pairing choice 不主导结论。

if 这些方法在高维/长 frame 下明显分歧：
    主结论以 G2-like correlation 为准；
    nearest / greedy 只作为系统误差提示。
```

---

## 4. 问题四：每个 pair 自选 frame origin 会破坏全局 JTI 物理意义

### 问题描述

如果对每个 pair 自己选择一个 frame origin，例如用 \(t_s\) 或 \(t_{mean}\) 取整后再做 modulo folding，那么每个 coincidence 都被局部重对齐。

这样得到的图更像局部 correlation kernel，而不是全局 JTI。它会人为消除 frame 内长时间结构、边缘结构和时间分布不均匀性，并使 effective mode / Schmidt-like metric 失去原本的 frame 解释。

### 解决思路

主 JTI 必须建立在固定全局 frame lattice 上。frame origin 应该是全局常数，而不是 pair-dependent quantity。

### 解决方法

对每个 sweep 点固定：

\[
t_0 = \text{constant global origin}
\]

\[
T = N\Delta t
\]

所有事件使用同一个时间网格：

\[
\text{frame index} = \left\lfloor \frac{t-t_0}{T} \right\rfloor
\]

\[
\text{bin index} = \left\lfloor \frac{(t-t_0) \bmod T}{\Delta t} \right\rfloor
\]

禁止在主分析中使用：

```text
per-pair origin = t_s
per-pair origin = t_i
per-pair origin = t_mean
```

---

## 5. 问题五：frame 边界附近会出现事件撕裂

### 问题描述

在固定 frame lattice 下，如果一个真实 coincidence pair 跨越 frame 边界，例如：

```text
t_s 位于 frame 末端
t_i 位于下一个 frame 开头
```

直接 modulo folding 会把它们放到矩阵两个相反边缘：

```text
bin_s ≈ N - 1
bin_i ≈ 0
```

物理上这两个事件相距很近，但普通平面 JTI 上看起来相距很远，这就是 boundary tearing。

### 解决思路

主流程采用：

```text
fixed global origin + edge guard + multi-origin sensitivity check
```

不建议默认使用 per-pair origin，也不建议一开始就把 JTI 当作 torus/circular frame，除非理论模型明确需要周期性 folding。

### 解决方法

#### 方法 A：固定全局 origin

所有事件使用同一个 frame origin。

#### 方法 B：edge guard

设置：

```text
edge_guard_ps = max(coincidence_window_ps, 3 × jitter_ps)
```

若某个 event 或 coincidence candidate 中任一 photon 距离 frame 边界小于 edge_guard，则不进入主 JTI，只进入边界诊断统计。

需要输出：

```text
edge_guard_ps
n_candidates_before_edge_guard
n_candidates_after_edge_guard
edge_rejection_ratio
```

若 edge rejection ratio 很低，说明边界处理对主结果影响小。若很高，说明 frame length、origin 或 folding 方式需要重新评估。

#### 方法 C：多 origin sensitivity check

对每个 frame length \(T\)，取多个固定全局 origin：

```text
origin = 0
origin = T/4
origin = T/2
origin = 3T/4
```

每个 origin 独立计算：

```text
coarse JTI
diag profile
marginals
effective K
edge rejection ratio
```

这些 origin 不能直接叠加为 4 倍数据量，只能用于 sensitivity analysis。

#### 方法 D：torus / circular metric 只作为补充诊断

如果明确采用 periodic frame folding，则可以使用 circular distance：

\[
d_{circ}(i,j)=\min(|i-j|, N-|i-j|)
\]

或 wrapped diagonal offset。

但默认主线仍建议使用 fixed origin + edge guard，而不是 torus interpretation。

---

## 6. 问题六：超大 JTI 的完整 SVD / Schmidt 计算不可行

### 问题描述

传统 Schmidt / effective mode number 计算通常依赖对 JTI 矩阵做 SVD。当矩阵达到几万维甚至几十万维时，完整 SVD 的计算量和内存需求都不可接受。

即使矩阵勉强能存储，完整 SVD 也可能无法在普通工作站或云服务器上完成。

### 解决思路

Schmidt / effective mode 分三档处理：

1. 小维度：dense exact SVD；
2. 中维度：coarse/rebinned JTI exact SVD；
3. 大维度：sparse / randomized / truncated SVD。

不要试图对每一个超大 frame 都构造完整 dense matrix 并做 full SVD。

### 解决方法

#### Level A：小维度 exact validation

推荐范围：

```text
N = 256, 512, 1024, 2048, 4096
```

用途：

```text
1. 与旧 pipeline 对齐；
2. 验证 G2-like / folding accumulator 是否正确；
3. 建立 exact effective K 的基准曲线。
```

#### Level B：中维度 coarse SVD

真实 \(N\) 可以是 8192、16384、32768 或更高，但统一 rebin 到：

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

#### Level C：大维度 sparse / truncated SVD

对于 \(N=32768\) 到 \(N=318000\) 的超高维情况，使用 sparse COO 或 LinearOperator，不显式构造完整矩阵。

只实现矩阵乘法：

```python
y = A @ x
z = A.T @ y
```

然后估计前 \(r\) 个奇异值，例如：

```text
r = 128, 256, 512, 1024
```

输出：

```text
top_r_singular_values
captured_frobenius_energy
K_truncated_r
K_convergence_vs_r
```

如果 captured energy 不足，不能声称已经得到全局 Schmidt number，只能说明当前 singular spectrum 尚未饱和。

---

## 7. 问题七：超高维不一定代表统计量可靠

### 问题描述

即使内存和计算问题解决，超高维矩阵仍然可能面临严重的采样稀疏问题。

例如，当 \(N=300000\)，但总 coincidence candidate 只有 \(10^6\) 时，平均每个 bin 或每个局部结构上的 counts 会非常稀疏。此时 effective mode 或 SVD 结果可能主要受 shot noise、偶然符合、稀疏采样影响。

### 解决思路

每一个 sweep 点都必须输出统计稳定性指标，而不是只输出一张图或一个 K 值。

### 解决方法

每个参数点至少输出：

```text
n_events_ch0
n_events_ch1
n_candidates_total
n_candidates_used
nonzero_bins
nonzero_fraction
mean_counts_per_nonzero_bin
diag_band_counts_fraction
method_sensitivity_summary
bootstrap_K_mean
bootstrap_K_std
```

同时建议做 bootstrap：

1. 从 coincidence candidates 或 event blocks 中重采样；
2. 对每个 bootstrap sample 重新计算 coarse K 或 truncated K；
3. 记录均值和标准差；
4. 判断当前维度下 K 是否稳定。

如果 K 的 bootstrap 方差很大，则该维度下的数据量不足，不应解释为物理饱和或物理上限。

---

## 8. 问题八：P_plus 不能作为高维度或相干时间主判据

### 问题描述

此前使用的 `P_plus` 分析主要反映 pair events 在 acquisition window 内的分布稳定性。例如 3 秒范围内的 P_plus 分布可以说明 coincidence 是否均匀、是否有宏观漂移、是否有采集中断。

但它不能直接说明单光子相干时间，也不能直接说明 time-bin entanglement 的最高维度。

### 解决思路

重新定位 P_plus：

- P_plus 是 acquisition stability / paired coincidence support 诊断；
- JTI / JSI sweep 才是时间-频率结构和有效维度分析主线；
- 泵浦有效线宽提供物理 coherence horizon；
- JTI sweep 检验实验数据是否覆盖并稳定逼近该 horizon。

### 解决方法

在文档和汇报中采用如下表述：

```text
P_plus is used as a long-acquisition stability diagnostic for paired coincidence events, rather than as a direct measure of single-photon coherence time or dimensionality.
```

主线应改为：

```text
The physically meaningful temporal dimensionality is constrained by the pump coherence horizon and the biphoton timing correlation width. The JTI sweep is used to evaluate whether the measured joint temporal structure and effective mode number remain stable as the frame length approaches this coherence-limited scale.
```

---

## 9. 推荐总体方案

最终推荐流程如下：

```text
1. 从 timetag 数据中构建 fixed-global-lattice coincidence candidates 或 G2-like correlation histogram
2. 使用固定物理 coincidence window，而不是随 frame length 改变 pairing window
3. 主分析采用 all-candidate / G2-like accumulation，并配合 diagnostics-only method/origin/edge sensitivity；不默认扣除 background
4. nearest / greedy_unique / strict 只作为 pairing-bias diagnostic
5. folding 使用固定全局 frame origin，不允许 per-pair origin
6. 主 JTI 使用 edge guard 控制 boundary tearing
7. 多个 global origins 只做 origin sensitivity analysis，不能叠加为独立样本
8. 小 N 输出 dense JTI 并做 exact SVD
9. 中 N 输出 coarse JTI、diagonal band、marginals，并做 coarse SVD
10. 大 N 输出 sparse / tiled / diagonal profiles，并做 truncated SVD 或趋势估计
11. 同步报告 pairing method、edge rejection、origin sensitivity、candidate counts、bootstrap stability
```

最终结论不应写成：

```text
We generated a full 300000 × 300000 JTI and calculated the exact Schmidt number.
```

而应写成：

```text
We implemented a fixed-lattice, G2-like JTI sweep with edge-guarded accumulation, coarse-grained global visualization, diagonal-band statistics, origin-sensitivity analysis, and truncated singular-spectrum estimation, enabling effective temporal-dimensionality analysis up to the pump-coherence-limited frame scale.
```

---

## 10. 推荐执行顺序

### Step 1：小规模 exact 对齐

```text
N = 512, 1024, 2048, 4096
binwidth = 100 ps
methods = G2-like, strict, folded_without_strict, nearest, greedy_unique
```

目标：验证 accumulator 正确性，并量化 strict / nearest / greedy 的系统偏差。

### Step 2：中等维度 coverage sweep

```text
N = 8192, 16384, 32768
binwidth = 100 ps
frame length = 0.819 us, 1.638 us, 3.277 us
```

目标：开始接近 100 kHz 泵浦线宽对应的 coherence scale，同时避免 full dense matrix。

### Step 3：泵浦相干时间量级 sweep

```text
frame length = 3 us, 10 us, 30 us
binwidth = 100 ps
N = 30000, 100000, 300000
```

目标：检验 JTI 结构和 effective mode number 是否在泵浦 coherence horizon 附近稳定。

### Step 4：最终物理解释

把结果分成两层：

```text
实验可直接计算的维度：由 exact / coarse / truncated SVD 给出。
物理可支持的维度估计：由泵浦有效线宽和 timing correlation width 给出。
```

---

## 11. 一句话总结

当前 JTI sweep 的核心改造是：从 dense-matrix-centered pipeline 转向 fixed-global-lattice G2-like correlation pipeline；从 strict single-hit 或 nearest/greedy 硬配对转向 coincidence-correlation 主分析；从 per-pair origin 转向 fixed global origin + edge guard + origin sensitivity；从 full SVD 转向 exact/coarse/truncated 分层估计；从单一 K 值转向带有 pairing bias、boundary sensitivity、origin sensitivity 和 bootstrap stability 的综合维度评估。
