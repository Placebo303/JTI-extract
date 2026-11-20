# JTI-extract

从 Swabian TimeTagger 的 `.ttbin` 原始时间标签直接生成 JTI（joint time-intensity，符合时间矩阵）。
只做全局坐标校准：全局 B 通道延时补偿 + 全局 residual-delay window 配对 + 非循环、edge-guarded 分箱，
输出绝对计数矩阵。不做 per-tooth ROI 筛选、不分配 peak_id、不做 comb line 重排、不做背景扣除。

当前版本：**0.4.0**（新增：`--peaks-csv` 变为可选；只给 `.ttbin` 即可用两路时间标签互相关自动确定延时）。

---

## 1. 环境要求

| 依赖 | 说明 |
|---|---|
| Python ≥ 3.9 | 本机实测 Python 3.12.12（Miniforge base） |
| numpy | `pip install` 依赖里已包含 |
| matplotlib | **只在画 PNG 时需要**，属于可选 extra `[plotting]`；缺失时会在写 PNG 那一步抛 `RuntimeError`（前面的矩阵已经算完，但整个运行仍算失败） |
| Swabian TimeTagger Python API | 读取 `.ttbin` 必需，由 Swabian 的 Time Tagger 安装包提供，**不在 PyPI 上** |
| pytest | 跑测试时需要（可选 extra `[dev]`） |

TimeTagger API 的位置（Windows 实测）：
`C:\Program Files\Swabian Instruments\Time Tagger\driver\python`。
安装器一般会把它写进系统 `PYTHONPATH`；若没有，运行时手动前置：

```bat
set PYTHONPATH=C:\Program Files\Swabian Instruments\Time Tagger\driver\python;%PYTHONPATH%
```

自检：

```bat
python -c "import numpy, TimeTagger; print('ok')"
python -c "import matplotlib; print('matplotlib', matplotlib.__version__)"
```

---

## 2. 安装

```bat
cd /d D:\Code\JTI提取
python -m pip install -e ".[plotting]"
```

三个容易踩的点：

1. **必须带 `[plotting]`**，否则 matplotlib 不会被安装，PNG 输出会失败。
2. 这条命令会把本机以前指向旧 checkout（例如 `D:\Code\JTI_extract_clean`）的 editable 安装**替换掉**；
   在没装之前，只有**仓库根目录**能用 `python -m jti_extract.cli.raw_aligned`（根目录有一个
   `jti_extract/__init__.py` dev shim，把包路径指到 `src/jti_extract`）。离开仓库根目录会 import 到旧代码。
3. 装好后可用短命令 `jti-raw-aligned`，等价于 `python -m jti_extract.cli.raw_aligned`。

---

## 3. 一条命令：ttbin → JTI（推荐，自动定延时）

```bat
cd /d D:\Code\JTI提取
python -m jti_extract.cli.raw_aligned ^
  --ttbin "D:\Data\Raw Data\JTI计算\JTI计算\FP #1\ii-DF776.348-1_2026-08-07_161354.1.ttbin" ^
  --raw-ch-a-id 1 --raw-ch-b-id 3 ^
  --binwidth-ps 40 --dimensions 80 --guard-bins 2 ^
  --compute-svd ^
  --out jti_out\fp1_set1
```

（PowerShell 用单行，或用反引号续行；Git Bash 用反斜杠续行。）

必须注意的两件事：

- **`--ttbin` 指向 `.1.ttbin` 数据分片**，不要指向同目录下 0 字节的 `.ttbin` 占位文件。
- **通道号必须和数据一致**：默认是 A=2 / B=3，而 FP #1 / FP #2（DF776.348）这批数据是 **A=1 / B=3**。
  选错时程序会报 `No events found for channel A=.../B=...`，并列出该文件里实际存在的通道号。

### 自动延时是怎么定出来的

`--peaks-csv` 现在不是必填。不给它时，程序直接用 `.ttbin` 里的两路时间标签做（加窗）互相关：

1. 对所有满足 `|t_B - t_A| <= 25000 ps` 的配对做 `Δt = t_B - t_A` 直方图（20 ps 分箱）——这就是两路
   时间标签流的互相关，不需要任何外部峰表；
2. 用 300 ps boxcar 平滑找到最亮的符合簇（300 ps 约等于一个典型 FP 腔 FSR / 梳齿簇尺度）。
   boxcar 会把窄峰抹成平顶，代码用“平顶取中心”消除这个偏差，单 bin 峰再用抛物线插值到亚 bin；
3. 以粗测峰为中心 ±300 ps 内改用 2 ps 细分箱，扣除环带背景后取该簇的**质心**，得到 `tau_align_ps`（整数 ps）；
4. 应用全局校准 `t_B_corr = t_B - tau_align_ps`，之后才做帧坐标与分箱。

终端会打印两行诊断（峰位与显著性），例如 FP #1 set1 全量实测：

```text
tau_align_ps = -119 ps (source: auto_correlation)
  correlation: 32,998 A-B pairs within +/-25000 ps | coarse peak = -126.2 ps (20 ps bins, 28.2 sigma)
  refined: centre of +/-300 ps cluster = -118.90 ps (2 ps bins, 39.8 sigma, used)
```

终端还会给出两类诊断：

- **接近等高的多个相关峰**（梳齿/多模结构）会打印 `note: N near-equal correlation clusters ...`，
  提示“延时是哪一簇”本身是一个模式选择，跨样本比较时建议固定 `--tau-align-ps`；
- **统计量不足**（搜索窗内 A-B 配对 < 5000）或峰在搜索窗边缘、显著性 < 5σ 时打印 WARNING——
  这时自动值可能锁到背景涨落上，请改用显式 `--tau-align-ps` 或 `--peaks-csv`。

`--auto-delay-range` 也有保护：当实测残余峰不可信（配对数不足或显著性 < 5σ）时，它不会把窗口挪走，
而是打印 WARNING 并保持以 0 ps 为中心。

### 参数扫描/试跑

先用小样本试参数（`--max-events` 限制读取的原始事件数；它同时是缓存 key 的一部分）：

```bat
python -m jti_extract.cli.raw_aligned --ttbin ... --max-events 200000 --out jti_out\trial
```

---

## 4. 什么时候仍然要给 peaks CSV 或显式 tau

`tau_align_ps` 的解析优先级：

`--tau-align-ps`（显式） > `--tau-auto` 或“没给 `--peaks-csv`”（互相关自动） > `--peaks-csv` 最亮峰。

适用场景：

| 场景 | 做法 |
|---|---|
| 复现历史结果 | FP #1 历史流程用 peaks CSV + 300 ps 平滑峰得到 `-130 ps`；自动值为 `-119 ps`（差 ~10 ps，小于一个 40 ps bin）。要复现就显式 `--tau-align-ps -130` |
| 有物理约定的“选哪一簇” | 显式 `--tau-align-ps` |
| 两通道几乎无符合 | 自动估计会报 `cannot calibrate the delay ... no A-B pairs`，改通道/加大搜索窗，或改用 peaks CSV |
| 已有延时直方图 CSV | 直接把该 CSV 当 `--peaks-csv`（只要有 `delay_ps`、`counts` 两列） |

```bat
:: A) 用 peaks CSV 的最亮峰
python -m jti_extract.cli.raw_aligned --ttbin ... --peaks-csv interchannel_delay_ch1_ch3.csv --out out\a

:: B) 显式延时
python -m jti_extract.cli.raw_aligned --ttbin ... --tau-align-ps -130 --out out\b

:: C) 给了 peaks CSV 但仍想用互相关（对比用）
python -m jti_extract.cli.raw_aligned --ttbin ... --peaks-csv ... --tau-auto --out out\c

:: D) 让 residual 延时窗自动居中到实测残余峰（而不是 0 ps）
python -m jti_extract.cli.raw_aligned --ttbin ... --auto-delay-range --delay-window-ps 900 --out out\d
```

---

## 5. 主要参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--ttbin` | 必填 | `.1.ttbin` 文件路径 |
| `--out` | 必填 | 输出目录 |
| `--peaks-csv` | 可选 | `delay_ps`/`counts` 两列的峰表；只用于“最亮峰”定 tau |
| `--tau-align-ps` | 无 | 显式 `tau_align_ps`（ps），优先级最高 |
| `--tau-auto` | 关 | 即使给了 `--peaks-csv` 也强制用互相关定 tau |
| `--tau-search-window-ps` | 25000 | 互相关搜索半窗（ps） |
| `--tau-coarse-bin-ps` | 20 | 粗测直方图分箱（ps） |
| `--tau-smooth-ps` | 300 | 粗测 boxcar 平滑宽度（ps），约取一个梳齿簇/FSR 尺度 |
| `--tau-refine` / `--no-tau-refine` | 开 | 是否做细分箱质心精修 |
| `--tau-refine-window-ps` | 300 | 精修质心窗口半宽（ps） |
| `--tau-refine-bin-ps` | 2 | 精修分箱（ps） |
| `--raw-ch-a-id` / `--raw-ch-b-id` | 2 / 3 | TimeTagger 逻辑通道号，必须与数据一致 |
| `--binwidth-ps` | 20 | JTI bin 宽度（ps） |
| `--dimensions` | 128 | JTI 维度 N；`frame_period = N × binwidth` |
| `--guard-bins` | 2 | 帧边缘保护 bin 数 |
| `--frame-origin-ps` | 0 | 帧原点（ps） |
| `--delay-min-ps` / `--delay-max-ps` | 自动 | residual-delay 窗上下界（ps） |
| `--delay-window-ps` | 无 | 半宽简写：窗 = ±W（配 `--auto-delay-range` 时为 中心±W） |
| `--auto-delay-range` | 关 | 窗中心取实测残余峰而非 0 ps；实测峰不可信时自动退回 0 ps 并告警 |
| `--max-events` | 无（全部） | 最多读取的原始事件数（试跑用） |
| `--chunk-size` | 50000 | 流式配对块大小 |
| `--compute-svd` | 关 | 额外计算 Schmidt-like K 并写 `summary.csv` |

未显式给 delay 窗时，默认半宽 = `dimensions × binwidth_ps // 2 - guard_bins × binwidth_ps`。

原理与坐标约定：

- `t_B_corr = t_B - tau_align_ps`
- `residual_tau = t_B_corr - t_A`，只保留 `delay_min <= residual_tau <= delay_max` 的配对（**有序 A-B 配对**，不去重）
- 帧坐标 `frame = floor((t - frame_origin) / frame_period)`，只保留同帧配对
- 帧内位置落在 `[guard_ps, frame_period - guard_ps)` 之外的事件对被剔除
- `H[i, j]` 累加绝对计数，`i` = A 侧 bin、`j` = B 侧 bin（`H_raw_aligned.png` 的 x 轴为 Signal、y 轴为 Idler）

---

## 6. 输出

| 文件 | 内容 |
|---|---|
| `H_raw_aligned.csv` | JTI 矩阵（CSV，含行列索引） |
| `H_raw_aligned.npz` | JTI 矩阵 + 元信息：`jti_counts`、`dimension`、`bin_width_ps`、`frame_origin_ps`、`tau_align_ps`、`delay_min_ps`、`delay_max_ps`、`guard_bins` |
| `H_raw_aligned.png` | JTI 热图（viridis） |
| `residual_tau_histogram.csv/png` | 配对后的 residual delay 直方图（主峰应落在 0 ps 附近） |
| `raw_aligned_meta.json` | 完整 metadata（见下） |
| `summary.csv` | 仅在 `--compute-svd` 时写出：K、purity、λ 权重等 |
| `_tag_cache/tags_cache_ch{A}_ch{B}.npz` | 从 ttbin 读出的 A/B 时间标签缓存（几十 MB），**复用可免去重新解析 ttbin** |

缓存 key = ttbin 绝对路径 + 文件大小 + mtime + 通道号 + `--max-events`。
换输出目录、改 `--max-events`（包括从有值改成不传）都会导致重读 ttbin。

`raw_aligned_meta.json` 关键字段：

- `analysis_mode` / `pairing_mode` / `raw_noise_preserved`
- `tau_align_ps`、`tau_align_source`（`explicit` / `auto_correlation` / `brightest_peak`）
- `tau_auto`：自动估计诊断（`null` 表示没走自动估计）。含 `n_pairs`、`coarse`（`peak_ps`、`significance`、`at_search_edge`、`bin_ps`、`smooth_bins`）、
  `refine`（`method`、`peak_ps`、`half_window_ps`、`bin_ps`、`significance`、`background_per_bin`）、`tau_align_ps_exact`、`refine_used`；
  `coarse` 里还有 `near_equal_candidates`（接近等高的候选簇峰位）与 `n_near_equal`
- `frame_origin_ps`、`binwidth_ps`、`dimension`、`frame_period_ps`、`guard_bins`
- `delay_min_ps` / `delay_max_ps` / `delay_span_ps`、`delay_span_exceeds_frame_period`、`delay_window_center_ps`、`delay_range_auto_centered`
- 计数守恒：`accepted_pairs_input = retained_in_jti + cross_frame_rejected + edge_rejected + invalid_bin`，
  即 `count_balance_error == 0`
- 对角线诊断：`weighted_mean_diag_offset_ps`、`weighted_std_diag_offset_ps`、`max_diag_offset_ps`
- `--compute-svd` 时追加 `K_raw_aligned`、`purity`、`n_singular_values`、`singular_values`、`lambda_weights`

---

## 7. 跑完怎么判断结果可信

1. 终端 `tau_align_ps` 的 source 与显著性符合预期（自动估计 ≥5σ，且未触发 `at_search_edge`）；
2. `residual_tau_histogram.png` 主峰在 0 ps 附近（明显偏移 = tau 没对准）；
3. `raw_aligned_meta.json` 里 `count_balance_error == 0`，且 `cross_frame_rejected` 占比不异常高
   （窗口宽于一个 frame period 时会告警 `delay_span_exceeds_frame_period`）；
4. `H_raw_aligned.png` 主对角线清晰；不清晰时先查 A/B 通道是否接反、tau 是否合理；
5. K 依赖 `binwidth` 与 `dimensions`，不同 frame period 的 K 不可直接比较。

---

## 8. 批处理与参数扫描

```bash
python scripts/run_raw_aligned_scan.py          # binwidth × N 扫描（自动延时）
python scripts/run_df776_dual_cavity.py         # DF776 双腔：延时分析→逐文件提取→归一化合并
```

多角度批量示例：

```bash
for angle in 90deg 135deg 180deg; do
  python -m jti_extract.cli.raw_aligned \
    --ttbin "data_$angle.1.ttbin" --raw-ch-a-id 1 --raw-ch-b-id 3 \
    --binwidth-ps 40 --dimensions 80 --guard-bins 2 --compute-svd \
    --out "jti_out/$angle"
done
```

---

## 9. 测试

```bat
cd /d D:\Code\JTI提取
python -m pytest -q
```

当前 26 个测试全部通过，其中 `tests/test_auto_tau.py`（16 个）覆盖自动延时：已知延时的合成时间标签、
直方图/峰值定位、显式值优先、peaks CSV 回退、`--tau-auto` 强制自动、接近等高簇的识别、
低统计量/残余峰不可信的降级保护等。

---

## 10. 项目结构

```text
src/jti_extract/cli/raw_aligned.py     主程序（唯一推荐的提取入口）
src/jti_extract/cli/tdc_layer_scan.py  底层 .ttbin 读取 load_tags
scripts/run_raw_aligned_scan.py        binwidth × N 参数扫描
scripts/run_df776_dual_cavity.py       DF776 双腔一条龙（仍未提交）
tests/                                 单元测试（含 test_auto_tau.py）
docs/                                  文档（索引见下）
archived/                              旧模式与诊断脚本（仅供参考）
jti_extract/__init__.py                仓库根目录 dev shim（未安装也能 import）
```

---

## 11. 文档

- [CLI 参考](docs/CLI.md)
- [方法](docs/METHOD.md)
- [工作流](docs/WORKFLOWS.md)
- [输出格式](docs/OUTPUTS.md)
- [数据格式](docs/DATA_CONTRACT.md)
- [SVD/K 算法](docs/SCHMIDT_ANALYSIS.md)
- [故障排除](docs/TROUBLESHOOTING.md)
- [Token 摘要](docs/TOKEN_SUMMARY.md)

---

## 12. 版本

- `0.4.0` — `--peaks-csv` 改为可选；新增基于 `.ttbin` 时间标签互相关的自动延时
  （粗测 + 细分箱质心精修、显著性/边缘诊断）；新增 `--auto-delay-range`；
  修正 peaks CSV 最亮峰恰为 0 ps 时的误报；改进通道选择错误提示。本版本为 **JTI-only** 发布：
  不含多峰拆分与额外诊断入口；上游 main 里那 4 个无法运行的 `examples/*.py` 已移除。
  详见 [CHANGELOG.md](CHANGELOG.md)。
