# 数据格式

## 输入文件

### .ttbin 文件
Swabian TimeTagger 原始时间戳文件。由 TimeTagger 软件生成。

需要指定 channel A 和 channel B 的 ID（通过 `--raw-ch-a-id` 和 `--raw-ch-b-id`）。

### pminus_peaks.csv
延时分布的 peaks CSV。必须包含以下列：

| 列 | 类型 | 说明 |
|---|---|---|
| `delay_ps` | float | 延时值（ps） |
| `counts` | float | 该延时处的计数 |

脚本只使用 `counts` 最大的峰的 `delay_ps` 来确定 `tau_align_ps`。
其余列（如 `smoothed_counts`, `relative_to_main`, `bin_index`）会被忽略。

此 CSV 可以由 `archived/diagnostics/analyze_interchannel_delay.py` 生成，
也可以由用户手动准备。只要包含 `delay_ps` 和 `counts` 列即可。

## 输出文件

见 [OUTPUTS.md](OUTPUTS.md)。
