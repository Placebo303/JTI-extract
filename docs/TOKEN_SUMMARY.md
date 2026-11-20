# Token Summary

## 项目

JTI-extract：从 TimeTagger `.ttbin` 原始时间标签提取 raw-aligned JTI 矩阵（0.3.1）。

## 唯一活跃脚本

- `src/jti_extract/cli/raw_aligned.py` — 主程序（raw-aligned JTI 提取 + 自动延时校准）
- `scripts/run_raw_aligned_scan.py` — binwidth × N 参数扫描
- `scripts/run_df776_dual_cavity.py` — DF776 双腔一条龙（未提交）

## 核心算法

1. 延时校准（三种来源，优先级从高到低）：
   - `--tau-align-ps` 显式；
   - `.ttbin` 两路时间标签互相关：`Δt = t_B - t_A` 直方图（±25 ns、20 ps 分箱）→ 300 ps boxcar
     平滑取最亮簇（平顶取中心 / 抛物线插值）→ ±300 ps 内 2 ps 细分箱扣背景取质心；
     配对 <5000 或 <5σ 会告警，多个接近等高的簇会列出候选峰位（`near_equal_candidates`）；
   - `--peaks-csv` 的最亮峰。
2. `t_B_corr = t_B - tau_align_ps`
3. `residual_tau = t_B_corr - t_A`，只保留 `delay_min <= residual_tau <= delay_max` 的有序 A-B 配对
   （不去重、不分配 peak_id）。
4. 帧坐标：`frame = floor((t - origin) / frame_period)`，只保留同帧配对；帧内位置在
   `[guard_ps, frame_period - guard_ps)` 之外的剔除。
5. `H[i,j]` 直接累加绝对计数（i = A 侧、j = B 侧）。
6. 可选 SVD/K：`P = H / sum(H)`，`A = sqrt(P)`，`svd(A)`，`K = 1 / sum(lambda^2)`。

## 关键约束

- 不做 per-tooth ROI 筛选、不分配 peak_id、不生成 H_tooth
- 不做 comb line 重排、不做背景扣除，保留全局延时窗内的原始噪声与背景
- 输出是**绝对计数**矩阵，normalization = none

## 数据要求

- `.ttbin` 必需（`--ttbin` 指向 `.1.ttbin` 数据分片；通道号必须与数据一致）
- peaks CSV **可选**：只在“用最亮峰定 tau”时需要，必须含 `delay_ps`、`counts` 两列

## 调用方式

```bash
# 自动延时（推荐）
jti-raw-aligned --ttbin data.1.ttbin --raw-ch-a-id 1 --raw-ch-b-id 3 \
  --binwidth-ps 40 --dimensions 80 --guard-bins 2 --compute-svd --out results/

# 显式 / peaks CSV（复现历史）
jti-raw-aligned --ttbin data.1.ttbin --tau-align-ps -130 --out results_tau130/
jti-raw-aligned --ttbin data.1.ttbin --peaks-csv pminus_peaks.csv --out results_peaks/

# 模块方式（未安装时，必须在仓库根目录）
python -m jti_extract.cli.raw_aligned --ttbin ... --out ...
```

## 环境要点（本机实测）

- Python 3.12.12（Miniforge base）；numpy 2.4.0；matplotlib 3.10.8
- TimeTagger API：`C:\Program Files\Swabian Instruments\Time Tagger\driver\python`（在 PYTHONPATH 中）
- 安装必须带 extra：`python -m pip install -e ".[plotting]"`（否则 PNG 失败）
- site-packages 里可能残留旧的 editable 安装（指向 `D:\Code\JTI_extract_clean`）；不在仓库根目录时
  会 import 到旧代码

## 已 Archive

- `archived/mode_a/` — Mode A 单线 JTI（extract.py）
- `archived/mode_b/` — Mode B BFC/FPC Schmidt
- `archived/diagnostics/` — 诊断工具（延时直方图、时间线等）
- `archived/batch_runners/` — 旧批处理
