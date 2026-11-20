# 工作流

## Workflow 1：单条命令 ttbin → JTI（自动延时）

```bash
jti-raw-aligned \
  --ttbin data.1.ttbin \
  --out results/fp1_set1 \
  --raw-ch-a-id 1 --raw-ch-b-id 3 \
  --binwidth-ps 40 --dimensions 80 --guard-bins 2 \
  --compute-svd
```

- 不给 `--peaks-csv`、不给 `--tau-align-ps` 时，`tau_align_ps` 由 `.ttbin` 里 A/B 两路时间标签的
  （加窗）互相关自动估计（算法见 [CLI.md](CLI.md)）。
- 通道号必须对：默认 2 / 3，FP #1、FP #2（DF776.348）数据是 **1 / 3**；选错会报
  `No events found for channel A=... / B=...` 并列出文件里的实际通道。
- 第一次跑会解析整个 ttbin 并写 `results/fp1_set1/_tag_cache/`；之后用同一个 `--out` 重跑会复用缓存，
  换 `--out` 会重读（见 [OUTPUTS.md](OUTPUTS.md)）。
- 跑完检查：
  - 终端 `tau_align_ps = ... (source: auto_correlation)`：显著性 ≥5σ 且没有 WARNING；
  - `raw_aligned_meta.json`：`count_balance_error == 0`；
  - `residual_tau_histogram.png`：主峰在 0 ps 附近；
  - `H_raw_aligned.png`：主对角线清晰。

参考实测（FP #1 set1，`ii-DF776.348-1_2026-08-07_161354.1.ttbin`，ch1/ch3，全量约 354 万 A /
296 万 B 事件）：自动估计约 **-119 ps**（粗测 -126 ps，精修 -119 ps）。数值随数据而变，不要当常数。

## Workflow 2：用 peaks CSV / 显式 tau 复现历史结果

历史流程用 peaks CSV + 300 ps 平滑峰，对同一组数据得到 **-130 ps**，与自动互相关的 -119 ps 差约 10 ps
（小于一个默认 40 ps bin）。三种复现方式：

```bash
# A) 用延时直方图 CSV 的最亮峰（等价于最亮 bin 的中心）
jti-raw-aligned --ttbin data.1.ttbin \
  --peaks-csv interchannel_delay_ch1_ch3.csv --out results/hist_peak

# B) 精确复现历史值（推荐）
jti-raw-aligned --ttbin data.1.ttbin \
  --tau-align-ps -130 --out results/hist_tau

# C) 给了 peaks CSV 但仍用互相关，做对比
jti-raw-aligned --ttbin data.1.ttbin \
  --peaks-csv interchannel_delay_ch1_ch3.csv --tau-auto --out results/auto_cmp
```

注意：peaks CSV 的“最亮峰”是直方图 bin 中心（10 ps 箱 → 10 ps 台阶、20 ps 箱 → 20 ps 台阶），
不等于 300 ps 平滑峰；要完全复现历史口径请用 `--tau-align-ps`。

## Workflow 3：自动延时窗口调参

默认 `--tau-search-window-ps 25000`（±25 ns）、20 ps 分箱、300 ps 平滑、精修开。

| 现象 | 调法 |
|------|------|
| 峰在搜索窗边缘（WARNING search-window edge） | 加大 `--tau-search-window-ps`（配对数与耗时随之增长） |
| 符合率低 / 采集短 → 粗测 <5σ | 用更长采集、确认通道；或改用 `--peaks-csv` / `--tau-align-ps` |
| 梳齿簇很宽、想平滑掉更多结构 | 加大 `--tau-smooth-ps`（粗测精度更粗，最终值仍由精修给） |
| 相邻梳齿峰高度接近，想锁到整个簇的中心 | 保持精修开，并让 `--tau-refine-window-ps` 覆盖整个簇 |
| 只想快速试跑 | `--no-tau-refine`，或 `--max-events` 小样本（注意显著性会随之下降） |

```bash
# 放宽搜索窗 + 更宽的平滑（大延时或宽梳齿簇）
jti-raw-aligned --ttbin data.1.ttbin --out results/wide \
  --tau-search-window-ps 100000 --tau-smooth-ps 500

# 关掉精修，只要粗测值
jti-raw-aligned --ttbin data.1.ttbin --out results/coarse --no-tau-refine
```

## Workflow 4：residual 延时窗自动居中（`--auto-delay-range`）

显式 / peaks CSV 的 tau 与真实符合峰差得比较多时，配对会落在 residual 窗之外。
`--auto-delay-range` 把窗中心挪到实测残余峰：

```bash
jti-raw-aligned --ttbin data.1.ttbin \
  --tau-align-ps -130 \
  --auto-delay-range --delay-window-ps 900 \
  --out results/centered
```

- `--delay-window-ps` 给半宽（此时窗 = 中心 ± W）；不给则用默认半宽
  `dimensions * binwidth_ps // 2 - guard_bins * binwidth_ps`。
- 同时给了 `--delay-min-ps` 和 `--delay-max-ps` 时该参数不生效。
- 实际中心记入 meta：`delay_window_center_ps` / `delay_range_auto_centered`。
- tau 来自自动互相关时残余峰 ≈ 0，这个参数基本只在显式 / peaks CSV 的 tau 下有意义。

## Workflow 5：参数扫描 (binwidth × N sweep)

```bash
python scripts/run_raw_aligned_scan.py
```

- 脚本头部写死了本机 ttbin、输出根目录，并固定 `--tau-align-ps 830`、
  `--delay-min-ps -1500 --delay-max-ps 300`；换数据前先改文件里的常量。
- 共 12 组：固定 `frame_period ≈ 3200 ps`（bw = 20/25/40/50/80/100）；N 敏感性（bw=40 时
  N=64/80/96/128，bw=50 时 N=48/64/80/96）。每组 `--compute-svd`，最后合并成 `scan_summary.csv`。
- 想改成自动延时：把脚本 `COMMON_ARGS` 里的 `--tau-align-ps 830` 去掉即可（0.4.0 起不需要 peaks CSV）。

## Workflow 6：多角度批量

```bash
for angle in 90deg 135deg 180deg; do
  jti-raw-aligned \
    --ttbin "data_${angle}.1.ttbin" \
    --out "results_${angle}" \
    --raw-ch-a-id 1 --raw-ch-b-id 3 \
    --binwidth-ps 40 --dimensions 80 --guard-bins 2 \
    --compute-svd
done
```

- 每个角度各自自动定 tau；某个角度显著性低（<5σ）时，单独给它 `--peaks-csv` 或 `--tau-align-ps`。
- 想统一延时：先用 `--max-events` 小样本试跑看每个文件的自动值，再显式传入。
- Windows CMD 用 `for %a in (90deg 135deg 180deg) do ...`；PowerShell 用
  `foreach ($a in @('90deg','135deg','180deg')) { ... }`。

## Workflow 7：Type-0 PPLN 单线 JTI

单线数据符合峰窄，用窄 residual 窗 + 自动延时即可：

```bash
jti-raw-aligned \
  --ttbin type0ppln.1.ttbin \
  --out results/type0 \
  --raw-ch-a-id 1 --raw-ch-b-id 3 \
  --binwidth-ps 20 --dimensions 128 --guard-bins 2 \
  --delay-min-ps -200 --delay-max-ps 200 \
  --compute-svd
```

- `--delay-min-ps` / `--delay-max-ps` 必须成对给；只给一个会被忽略。
- 通道号按实际数据改。

## Workflow 8：只有延时直方图 CSV 时

任何 `delay_ps,counts` 两列的延时直方图 CSV 都可以直接当 `--peaks-csv`
（例如 `archived/diagnostics/analyze_interchannel_delay.py` 输出的 `interchannel_delay_ch1_ch3.csv`）：

```bash
python archived/diagnostics/analyze_interchannel_delay.py \
  --input data.1.ttbin --channels 1 3 \
  --window-ps 25000 --bin-width-ps 20 \
  --output-dir results/delay

jti-raw-aligned --ttbin data.1.ttbin \
  --peaks-csv results/delay/interchannel_delay_ch1_ch3.csv \
  --out results/jti
```

该脚本（已归档）只输出最亮 bin 口径；需要 300 ps 平滑峰的历史口径时，显式 `--tau-align-ps`。

## 兼容性

- **旧流程仍然可用**：给了 `--peaks-csv` 且不给 `--tau-auto` / `--tau-align-ps` 时，仍然取 CSV 最亮峰
  当 `tau_align_ps`（0.4.0 起由截断改为四舍五入，整数峰无差别）。
- 旧脚本里写死的 `--peaks-csv` 可以保留，无害；想改成自动估计只需删掉该参数。
