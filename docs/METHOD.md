# 方法定义：Raw-Aligned JTI

## 适用范围

本包的正式分析模式是 `jti-raw-aligned`。它从两路 TimeTagger 时间标签产生一个可复算的、绝对计数的 JTI。此方法不把直方图处理成归一化概率图，也不进行 per-tooth ROI 筛选、comb-line 重排、背景相减或隐式峰合并。

## 定义

令两路检测时间标签为 \(t_A\)、\(t_B\)。选择全局校准量 \(\tau_{\mathrm{align}}\)，并校正 B 通道：

\[
t_B^{\mathrm{corr}}=t_B-\tau_{\mathrm{align}}.
\]

仅保留满足全局 residual-delay window 的候选对：

\[
d_{\min}\leq t_B^{\mathrm{corr}}-t_A\leq d_{\max}.
\]

对于共同落在同一时间 frame、且不在 edge guard 内的候选对，按 bin width \(\Delta t\) 累加二维绝对计数：

\[
H[i,j]=\#\{(t_A,t_B):i=\lfloor x_A/\Delta t\rfloor,\;j=\lfloor x_B/\Delta t\rfloor\}.
\]

其中 \(x_A\)、\(x_B\) 是相对于 `frame_origin_ps` 的 frame-local 坐标。跨 frame 候选和 guard 区候选会在 metadata 中单独记数。

## 校准与多峰

未显式提供 `--tau-align-ps` 时，single 模式用 peaks CSV 中计数最大的峰作全局校准。微腔多峰模式先从 residual-delay histogram 生成峰目录，然后对每个选择峰以相同分箱定义独立输出一套 JTI。默认窗口按相邻检测峰的间距确定并保留一个 histogram bin 的间隔；显式窗口若重叠会被拒绝。峰编号按残差延时升序稳定排列；`peak_catalog.csv` 是峰选择和计数的记录，不是背景校正或物理模式识别。当前正式支持域限于同一分析 frame 内的已解析峰。

分析 frame 由 `dimensions * binwidth_ps` 定义，不会从峰间隔自动推断。使用者必须将其设为实验采用的时间 frame；否则 same-frame 筛选不具有预期的物理含义。

## 解释边界

- `H_raw_aligned` 是测得的 coincidence counts，不等于已经校正探测效率后的联合概率。
- 可选 SVD/K 从 \(\sqrt{H/\sum H}\) 计算，为数据矩阵的 Schmidt-like 指标；它不是对态纠缠维度的独立证明。
- TDC residue 诊断用于发现仪器时间量化结构；离线诊断本身不能完成硬件或光学来源归因。

每次结果应随 `raw_aligned_meta.json` 保存，以记录输入、通道、校准、窗口、frame geometry 和计数平衡。
