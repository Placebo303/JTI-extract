# JTI-extract

用于 TimeTagger 原始时间标签的组内 JTI（joint time-intensity）提取包。正式分析入口是 `jti-raw-aligned`：它以全局延时校准、全局 residual-delay coincidence window 和非循环、edge-guarded 分箱生成绝对计数 JTI，不做 per-tooth ROI 筛选、峰重排或背景相减。

## 安装

```bash
pip install -e ".[plotting]"
```

读取 `.ttbin` 还需要 Swabian TimeTagger Python API；见 [故障排除](docs/TROUBLESHOOTING.md)。

## 推荐工作流

```bash
jti-raw-aligned \
  --ttbin data.1.ttbin \
  --peaks-csv pminus_peaks.csv \
  --binwidth-ps 40 --dimensions 80 --guard-bins 2 \
  --delay-min-ps -1500 --delay-max-ps 300 \
  --compute-svd \
  --out results/
```

`pminus_peaks.csv` 至少包含 `delay_ps`、`counts` 两列；默认以最亮峰确定全局 `tau_align_ps`。输出的 `H_raw_aligned.*` 为绝对计数矩阵，`raw_aligned_meta.json` 记录通道、窗口、frame origin、计数守恒诊断和可选的 Schmidt-like SVD/K 结果。

## 微腔多峰

多峰数据使用同一 raw-aligned 定义逐峰提取，不把不同延时峰静默合并：

```bash
jti-raw-aligned \
  --ttbin microcavity.1.ttbin --peaks-csv delay_peaks.csv \
  --peak-mode auto --peak-window-ps 120 \
  --binwidth-ps 40 --dimensions 80 --out results_multipeak/
```

`--peak-mode auto` 检测 residual-delay 局部峰；`--peak-mode selected --peak-indices 0,2` 只提取按延时升序编号的峰。每个峰写入 `peaks/peak_XXX/`，根目录的 `peak_catalog.csv` 记录峰中心、窗口和原始计数。默认不合并峰；如需合并，必须在下游明确记录选择的峰与加权规则。

## 其他命令

- `jti-tdc-residue`：独立的 TDC fine-time residue 诊断，不能替代 JTI 提取或证明物理归因。
- `jti-tdc-layer-scan`：更完整的离线 residue 分层诊断。
- `jti-extract`：旧 CV/DV/SVD 提取流程，仅为复现历史结果保留；不推荐用于新的组内结果。

详细参数、方法定义和输出契约见 [文档索引](docs/index.md)。
