# 工作流

## Workflow 1：Raw-Aligned FPC JTI 提取

基本流程：

```bash
# 1. 准备数据
# 需要 .ttbin 文件和 pminus_peaks.csv

# 2. 运行 raw-aligned JTI
jti-raw-aligned \
  --ttbin data.1.ttbin \
  --peaks-csv pminus_peaks.csv \
  --binwidth-ps 40 --dimensions 80 --guard-bins 2 \
  --delay-min-ps -1500 --delay-max-ps 300 \
  --compute-svd \
  --out results/

# 3. 检查输出
# - H_raw_aligned.png：主对角线是否清晰
# - residual_tau_histogram.png：主峰是否在 0 ps 附近
# - raw_aligned_meta.json：count_balance_error 是否为 0
```

## Workflow 2：Type-0 PPLN 单线 JTI 提取

```bash
# Type-0 PPLN 单峰数据，delay range 可以很窄
jti-raw-aligned \
  --ttbin Type0ppln.1.ttbin \
  --peaks-csv interchannel_delay.csv \
  --binwidth-ps 20 --dimensions 128 --guard-bins 2 \
  --delay-min-ps -200 --delay-max-ps 200 \
  --raw-ch-a-id 1 --raw-ch-b-id 3 \
  --compute-svd \
  --out results/
```

## Workflow 3：参数扫描 (binwidth × N sweep)

```bash
# 运行预定义的 12 组参数扫描
python scripts/run_raw_aligned_scan.py
```

扫描组合：
- 固定 frame_period ≈ 3200 ps：bw=20/25/40/50/80/100
- N 敏感性扫描：bw=40 时 N=64/80/96/128，bw=50 时 N=48/64/80/96

## Workflow 4：从 interchannel delay CSV 生成 pminus_peaks.csv

如果只有原始 interchannel delay histogram CSV（如 `interchannel_delay_ch1_ch3.csv`），
可以直接将其作为 `--peaks-csv` 使用（只要包含 `delay_ps` 和 `counts` 列）。

更精细的 peaks CSV 可以通过 `archived/diagnostics/analyze_interchannel_delay.py` 生成
（仅供参考，该脚本已 archive）。

## Workflow 5：多角度批量处理

对多个角度（如 90°/135°/180°）重复运行 raw-aligned JTI：

```bash
for angle in 90deg 135deg 180deg; do
  jti-raw-aligned \
    --ttbin "data_${angle}.1.ttbin" \
    --peaks-csv "peaks_${angle}.csv" \
    --binwidth-ps 40 --dimensions 80 --guard-bins 2 \
    --delay-min-ps -1500 --delay-max-ps 300 \
    --compute-svd \
    --out "results_${angle}/"
done
```
