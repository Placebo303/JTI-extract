# Archived: Diagnostic Tools

## 工具列表

### analyze_coincidence_window.py (212 行)
分析随机时间窗口内的巧合分布，判断信号 vs 背景。
调用：`python analyze_coincidence_window.py --input <ttbin> ...`

### analyze_interchannel_delay.py (284 行)
分析 P_minus(tau) 互通道延时分布，输出延时直方图 CSV（可直接当 `jti-raw-aligned` 的 `--peaks-csv`）。

实际参数（与旧版 README 不同，以下为当前代码）：

```bash
python archived/diagnostics/analyze_interchannel_delay.py \
  --input data.1.ttbin \
  --channels 1 3 \
  --window-ps 25000 --bin-width-ps 20 \
  --output-dir results/delay
```

| 参数 | 说明 |
|---|---|
| `--input` | 输入 `.1.ttbin`（注意不是 `--ttbin`） |
| `--channels A B` | 两个逻辑通道号 |
| `--window-ps` | 搜索半窗（ps，默认 10000） |
| `--bin-width-ps` | 直方图分箱（ps，默认 10） |
| `--output-dir` | 输出目录（必填） |
| `--max-events` | 可选，限制读取事件数 |

输出（**不是** `pminus_peaks.csv`）：

- `interchannel_delay_ch{A}_ch{B}.csv`（两列：`delay_ps,counts`）
- `interchannel_delay_ch{A}_ch{B}.png`
- `interchannel_delay_ch{A}_ch{B}_summary.json`

该 CSV 可以直接作为 `jti-raw-aligned --peaks-csv` 使用（取最亮 bin 作为 `tau_align_ps`）；
但它给出的是“最亮 bin 中心”，若需要 300 ps 平滑峰的口径，请显式传 `--tau-align-ps`。

### analyze_ttbin_coincidence_timeline.py (318 行)
巧合率 vs 绝对采集时间，检测采集过程中的漂移。
调用：`python analyze_ttbin_coincidence_timeline.py --input <ttbin> ...`

### jti_delay_alignment.py (618 行)
Delay-peak 到 JTI diagonal-offset 对齐工具。
加载 delay histogram CSV，检测 peaks，评估 FWHM，选择最优 bin width。
调用：`python jti_delay_alignment.py --delay-csv <path> ...`

### README_jti_delay_alignment.md
jti_delay_alignment.py 的使用文档。

## Archive 原因

原始对齐模式不需要这些预处理步骤：延时直方图由 raw-aligned 脚本的
`residual_tau_histogram` 直接给出，`tau_align_ps` 现在也能直接从 `.ttbin` 时间标签互相关估计
（0.3.1 起）。本目录脚本仅用于交叉检查或生成可复用的延时直方图 CSV。
