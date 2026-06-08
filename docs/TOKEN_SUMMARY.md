# Token Summary

## 项目
JTI-extract：Raw-aligned FPC JTI 提取工具。

## 唯一活跃脚本
- `src/jti_extract/cli/raw_aligned.py` — 主程序（raw-aligned FPC JTI 提取）
- `scripts/run_raw_aligned_scan.py` — 参数扫描

## 核心算法
- `t_B_corr = t_B - tau_align_ps`（tau_align_ps 由 pminus_peaks.csv 最亮峰自动确定）
- `residual_tau = t_B_corr - t_A`
- 全局 delay window 筛选：`delay_min <= residual_tau <= delay_max`
- 帧坐标：`frame_a = (t_A - origin) // frame_period`, `frame_b = (t_B_corr - origin) // frame_period`
- 只保留 `frame_a == frame_b` 的事件对
- Edge guard 剔除帧边界事件
- SVD/K：`P=H/sum(H), A=sqrt(P), SVD(A), K=1/sum(lambda^2)`

## 关键约束
- 不做 per-tooth ROI 筛选
- 不分配 peak_id
- 不生成 H_tooth
- 不做 comb line 重排
- 不做背景扣除
- 保留全局 delay range 内的原始噪声和背景

## 已 Archive
- `archived/mode_a/` — Mode A 单线 JTI (extract.py)
- `archived/mode_b/` — Mode B BFC/FPC Schmidt (compute_fpc_schmidt.py)
- `archived/diagnostics/` — 诊断工具
- `archived/batch_runners/` — 旧批处理

## 数据要求
- `.ttbin` 文件（Swabian TimeTagger 格式）
- `pminus_peaks.csv`（需有 `delay_ps` 和 `counts` 列）

## entry point
```bash
jti-raw-aligned --ttbin ... --peaks-csv ... --out ...
python -m jti_extract.cli.raw_aligned --ttbin ... --peaks-csv ... --out ...
```
