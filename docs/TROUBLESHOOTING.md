# 故障排除

## 常见错误

### "No events found in .ttbin"
- .ttbin 文件为空或路径错误
- 检查 `--ttbin` 路径

### "Cannot determine tau_align_ps"
- pminus_peaks.csv 为空或格式不正确
- 确认 CSV 包含 `delay_ps` 和 `counts` 列
- 或显式指定 `--tau-align-ps`

### "delay_span_ps >= frame_period_ps"
- delay range 太宽，会导致大量 cross_frame_rejected
- 缩小 `--delay-min-ps` / `--delay-max-ps`
- 或增大 `--dimensions`

### count_balance_error != 0
- 代码 bug，不应发生
- 请报告此问题

### residual_tau_histogram 主峰不在 0 ps 附近
- `tau_align_ps` 可能不正确
- 检查 pminus_peaks.csv 中的最亮峰
- 或显式指定 `--tau-align-ps`

### H_raw_aligned 主对角线不清晰
- A/B 通道可能反了（交换 `--raw-ch-a-id` 和 `--raw-ch-b-id`）
- `frame_origin_ps` 可能需要调整
- `tau_align_ps` 符号可能反了

### cross_frame_rejected 异常偏高
- delay range 太宽或 frame_period 太小
- 增大 `--dimensions` 或缩小 delay range

### matplotlib 报错
- 安装 matplotlib：`pip install matplotlib`
- 或不使用 PNG 输出（脚本仍会生成 CSV 和 NPZ）
