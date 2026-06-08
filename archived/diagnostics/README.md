# Archived: Diagnostic Tools

## 工具列表

### analyze_coincidence_window.py (212 行)
分析随机时间窗口内的巧合分布，判断信号 vs 背景。
调用：`python analyze_coincidence_window.py --ttbin <path> ...`

### analyze_interchannel_delay.py (284 行)
分析 P_minus(tau) 延时分布，生成 pminus_peaks.csv 和 pminus_delay_histogram.csv。
调用：`python analyze_interchannel_delay.py --ttbin <path> ...`

### analyze_ttbin_coincidence_timeline.py (318 行)
巧合率 vs 绝对采集时间，检测采集过程中的漂移。
调用：`python analyze_ttbin_coincidence_timeline.py --ttbin <path> ...`

### jti_delay_alignment.py (618 行)
Delay-peak 到 JTI diagonal-offset 对齐工具。
加载 delay histogram CSV，检测 peaks，评估 FWHM，选择最优 bin width。
调用：`python jti_delay_alignment.py --delay-csv <path> ...`

### README_jti_delay_alignment.md
jti_delay_alignment.py 的使用文档。

## Archive 原因
原始对齐模式不需要这些预处理步骤。延时直方图由 raw-aligned 脚本的
residual_tau_histogram 直接替代。pminus_peaks.csv 仍需提供给 raw-aligned
脚本用于自动确定 tau_align_ps，但生成方式可由用户自行决定。
