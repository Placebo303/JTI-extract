# Type0ppln 直接 P_plus 提取与高维 auto-dim 说明

本文档记录 Type0ppln JTI 数据的主对角线方向时间支持分析。对应脚本为：

```text
scripts/run_type0ppln_pplus_auto_dim.py
```

最终使用的结果目录为：

```text
D:\Data\Raw Data\Type0ppln JTI\pplus_auto_dim_20260428_145224
```

## 1. 分析目标

本次分析的目标是从 Type0ppln 的 `.ttbin` 时间标签数据中，直接估计 JTI 主对角线方向的一维 profile：

```text
P_plus
```

它用于判断 JTI 沿主对角线方向的时间支持范围，即需要多大的 frame length 才能覆盖主要计数分布。

需要明确：

- `P_plus` 不是 Schmidt number。
- 本脚本不计算 Schmidt 模式数 `K`。
- 本脚本不构造完整 `dim x dim` JTI 矩阵。
- 高维运行时使用 sparse profile，避免在 32 GB 内存机器上分配超大 dense 数组。
- 按 2026-04-29 的 ultra JTI 规划，`P_plus` 仅作为 acquisition stability / paired coincidence support 诊断；不能作为单光子一阶相干时间、time-bin entanglement 最高维度或 fixed-lattice G2-like JTI sweep 的替代判据。
- 本报告中的 `nearest` pairing 是历史 Type0ppln P_plus pilot 设置；在 ultra-high-dimensional JTI 主线中，`nearest` / `greedy_unique` 只能作为 pairing-bias diagnostics，主结果应以 fixed-lattice raw `g2_all_candidates` 为准；2026-04-29 共识是不默认扣除 background。

此前 absolute-time sliding window 方案按采集绝对时间 `u=(t_s+t_i)/2` 切窗，每个 51.2 ns 窗口内只有极少 pairs，不适合估计 JTI 主对角线方向的整体时间支持。本方案改为直接在 frame/bin 坐标中统计 `P_plus`。

## 2. 数据与默认参数

数据目录：

```text
D:\Data\Raw Data\Type0ppln JTI
```

如果在 WSL/Linux 下无法访问 Windows 路径，脚本会尝试转换为：

```text
/mnt/d/Data/Raw Data/Type0ppln JTI
```

本次使用的主要参数：

| 参数 | 值 | 含义 |
|---|---:|---|
| channels | `1 3` | TimeTagger 硬件通道 |
| pairing_rule | `nearest` | 默认最近邻配对 |
| coincidence_window_ps | `200` | pair cutoff，单位 ps |
| bin_width_ps | `100` | JTI/frame binning 分辨率 |
| diag_band_bins | `1` | 主对角线带宽，允许 `abs(delta)<=1` |
| start_dim | `32` | 初始低维扫描维度 |
| low-dim max_dim | `65536` | 第一轮低维 auto-dim 上限 |
| high-dim continuation | powers of two | 从高维继续倍增 |
| jobs | `15` | frame-origin scoring 并行线程数 |
| profile_storage | `auto` | 低维 dense，高维 sparse |
| dense_profile_max_bins | `5000000` | dense profile 最大 bin 数 |

`coincidence_window_ps` 和 `bin_width_ps` 是两个不同概念：

- `coincidence_window_ps` 是配对时允许的最大时间差窗口。
- `bin_width_ps` 是把时间映射到 JTI/frame bin 时使用的分辨率。

因此本次固定 `coincidence_window_ps=200 ps`，不会让它跟随 `bin_width_ps` 自动改变。

## 3. 数据去重

脚本递归搜索数据目录下的 `.ttbin` 文件，并默认执行 logical recording 去重。

去重优先级：

1. 优先读取 TimeTagger 配置中的 `FileWriter.filename`。
2. 如果没有该字段，则使用 fallback signature：
   - 时间戳 sample；
   - total events；
   - 所选通道计数。

当前目录中：

```text
TimeTags_2026-04-03_213758.ttbin
TimeTags_2026-04-03_213758.1.ttbin
```

被折叠为一个 logical dataset。最终保留文件为：

```text
D:\Data\Raw Data\Type0ppln JTI\TimeTags_2026-04-03_213758.ttbin
```

duplicate count 为 `1`。

## 4. 计算流程

整体流程如下：

```text
.ttbin
  -> load_tags 读取通道 1 和 3
  -> nearest_pairs 配对
  -> 全局 tau0_ps 估计
  -> 对每个 dim 选择 best frame_origin
  -> 映射到 x_bin, y_bin
  -> 统计 P_plus 和 P_minus
  -> 计算宽度指标和 auto-dim 覆盖判据
```

### 4.1 读取与配对

`.ttbin` 读取复用项目中的：

```text
jti_extract.cli.tdc_layer_scan.load_tags
```

pairing 复用：

```text
nearest_pairs
greedy_unique_pairs
```

本次实际使用：

```text
pairing_rule=nearest
coincidence_window_ps=200
```

### 4.2 tau0_ps 对齐

每个 logical file 只估计一个全局 `tau0_ps`，不随 dim 变化，也不做窗口级重估。

本次延续前序结果使用：

```text
tau0_ps = -4.0 ps
```

### 4.3 frame_origin 选择

为了保证 direct profile 与项目现有 dense JTI 坐标逻辑一致，脚本复用现有 best frame origin 的排序规则：

1. 最大化主对角线比例 `diag_main_fraction`；
2. 再最小化 `diag_pm1_fraction`；
3. 再最大化 `diag_contrast`；
4. 最后选择最小 `frame_origin_ps`。

高维情况下不能调用会分配 `dim x dim` 矩阵的 `_counts_for_frame_origin()`。因此脚本实现了 direct paired-event frame-origin scoring：

```text
paired timestamps -> x_bin, y_bin
diag_main_fraction = count(x_bin == y_bin) / total_pairs
diag_pm1_fraction = count(y_bin == x_bin +/- 1, non-wrapping) / total_pairs
```

该方法不构造 dense JTI，适合 `dim` 达到数十亿以上的情况。

## 5. P_plus 与 P_minus 定义

对每个 pair，经 `frame_origin_ps` 和 `bin_width_ps` 映射后得到：

```text
x_bin in [0, dim-1]
y_bin in [0, dim-1]
```

定义 circular diagonal offset：

```text
delta = ((y_bin - x_bin + dim//2) % dim) - dim//2
```

主对角线带判据：

```text
abs(delta) <= diag_band_bins
```

本次 `diag_band_bins=1`。

主 profile：

```text
P_plus[x_bin] += 1
```

这里使用 `x_bin` 作为主对角线坐标，避免 circular boundary 附近用 `(x_bin+y_bin)/2` 造成错误跳到 frame 中部。

垂直方向检查 profile：

```text
P_minus[delta] += 1
```

`P_minus` 用于检查相对延迟方向，即主对角线垂直方向的宽度。

## 6. 高维 sparse 实现

低维时可以使用 dense 一维数组：

```text
P_plus: length dim
P_minus: observed delta histogram
```

但本次最终需要：

```text
dim = 137438953472
```

如果用 dense `P_plus`，仅一个 int64 数组就需要约：

```text
137438953472 * 8 bytes ~= 1 TB
```

这不适合 32 GB 内存机器。因此高维时使用 sparse profile：

```text
nonzero bin index -> count
observed delta -> count
```

最终 sparse 结果：

```text
n_nonzero_P_plus_bins = 645394
estimated_profile_bytes ~= 10326400 bytes
```

也就是 profile 本体约 10 MB 量级，而不是 TB 量级。

## 7. 宽度指标

对 `P_plus` 计算：

| 指标 | 含义 |
|---|---|
| peak counts | 最大 bin 计数 |
| peak index | 峰值 bin |
| FWHM_ps | 半高宽 |
| central_50_width_ps | 覆盖 50% 计数的主宽度 |
| central_90_width_ps | 覆盖 90% 计数的主宽度 |
| central_95_width_ps | 覆盖 95% 计数的主宽度 |
| sigma_ps | 加权标准差 |
| participation_time_ps | `(sum P)^2 / sum(P^2) * bin_width_ps` |

对 `P_minus` 计算：

| 指标 | 含义 |
|---|---|
| peak delta | 最大计数的 offset |
| FWHM_ps | 垂直方向半高宽 |
| sigma_ps | 垂直方向加权标准差 |
| central_90_width_ps | 覆盖 90% 的垂直方向宽度 |
| central_95_width_ps | 覆盖 95% 的垂直方向宽度 |

高维 sparse 模式下，`central_90_width_ps` 和 `central_95_width_ps` 从非零 bin 的排序和 circular/min-contiguous interval 逻辑计算，不需要 materialize 整个长度为 `dim` 的数组。

## 8. auto-dim 覆盖判据

每个 dim 的 frame length 为：

```text
frame_length_ps = dim * bin_width_ps
```

主要判据：

```text
width_ratio_95 = P_plus_central_95_width_ps / frame_length_ps
```

边缘计数比例：

```text
edge_bins = max(1, int(dim * edge_bins_fraction))
edge_fraction = (sum(P_plus[:edge_bins]) + sum(P_plus[-edge_bins:])) / sum(P_plus)
```

相邻维度宽度变化：

```text
relative_change_W95 = abs(W95_current - W95_previous) / max(W95_current, eps)
```

covered 判据：

```text
covered = (
    width_ratio_95 < 0.7
    and edge_fraction < 0.05
    and relative_change_W95 < 0.05
)
```

解释：

- 如果 `W95/frame_length` 接近 1，说明当前 frame 太短，只能给出下界。
- 如果 `edge_fraction` 高，说明 profile 仍贴边，可能没完整覆盖。
- 如果 `W95` 仍随 dim 明显增长，说明还没有饱和。
- 三个条件同时满足，才认为当前 dim 足够覆盖主对角线方向时间支持。

## 9. 实际运行步骤

### 9.1 语法检查

```powershell
python -m py_compile scripts\run_type0ppln_pplus_auto_dim.py
```

结果：通过。

### 9.2 dry run

```powershell
python scripts\run_type0ppln_pplus_auto_dim.py --dry-run --data-root "D:\Data\Raw Data\Type0ppln JTI" --auto-dim --min-next-dim 131072 --high-dim-max-dim 68719476736 --bin-width-ps 100 --channels 1 3 --pairing-rule nearest --coincidence-window-ps 200 --diag-band-bins 1 --jobs 15 --profile-storage auto --continue-from-existing "D:\Data\Raw Data\Type0ppln JTI\pplus_auto_dim_20260428_021824"
```

dry run 检查内容：

- data root 是否存在；
- `.ttbin` 文件发现；
- dedupe 预览；
- import 是否可用；
- 缓存是否存在；
- planned dims；
- dense/sparse 内存估计。

### 9.3 单元测试

```powershell
python -m pytest tests\test_binning.py tests\test_pairing.py tests\test_io_contract.py
```

结果：

```text
8 passed
```

### 9.4 第一轮高维续跑

```powershell
python scripts\run_type0ppln_pplus_auto_dim.py --data-root "D:\Data\Raw Data\Type0ppln JTI" --auto-dim --min-next-dim 131072 --high-dim-max-dim 68719476736 --bin-width-ps 100 --channels 1 3 --pairing-rule nearest --coincidence-window-ps 200 --diag-band-bins 1 --jobs 15 --profile-storage auto --continue-from-existing "D:\Data\Raw Data\Type0ppln JTI\pplus_auto_dim_20260428_021824"
```

输出目录：

```text
D:\Data\Raw Data\Type0ppln JTI\pplus_auto_dim_20260428_144846
```

该轮跑到：

```text
dim = 68719476736
frame_length_ps = 6871947673600
W95_ps = 2850677295100.0
width_ratio_95 = 0.41482814341725316
edge_fraction = 0.23003622593330586
status = NOT_SATURATED
```

虽然 `width_ratio_95` 已低于 0.7，但 `edge_fraction` 仍高于 0.05，所以没有 cover。

### 9.5 第二轮继续向更高维探索

```powershell
python scripts\run_type0ppln_pplus_auto_dim.py --data-root "D:\Data\Raw Data\Type0ppln JTI" --auto-dim --min-next-dim 137438953472 --high-dim-max-dim 562949953421312 --bin-width-ps 100 --channels 1 3 --pairing-rule nearest --coincidence-window-ps 200 --diag-band-bins 1 --jobs 15 --profile-storage auto --continue-from-existing "D:\Data\Raw Data\Type0ppln JTI\pplus_auto_dim_20260428_144846"
```

最终输出目录：

```text
D:\Data\Raw Data\Type0ppln JTI\pplus_auto_dim_20260428_145224
```

该轮在第一个更高维度即达到 covered。

## 10. 最终结果

最终 logical file：

```text
000_C_Users_PC_Documents_Time_Tagger_Lab_Time_Tag_Files_TimeTags_2026-04-03_213758.ttbin
```

最终结果：

| 指标 | 值 |
|---|---:|
| n_pairs | `646811` |
| tau0_ps | `-4.0` |
| final_dim | `137438953472` |
| final_frame_length_ps | `13743895347200` |
| final_frame_length_s | `13.7438953472` |
| final_W95_ps | `2850677295100.0` |
| final_W95_s | `2.8506772951` |
| final_width_ratio_95 | `0.20741407170862658` |
| final_edge_fraction | `0.0` |
| final_covered | `True` |
| final_status | `OK` |
| stop_reason | `covered` |
| profile_storage | `sparse` |
| n_nonzero_P_plus_bins | `645394` |
| frame_origin_method | `direct_paired_event_scan` |

最终判断：

```text
Type0ppln P_plus 已在 dim=137438953472 时达到 covered。
```

这意味着在当前判据下，`P_plus` 的 95% 主时间支持约为：

```text
W95 ~= 2.8506772951 s
```

最终 frame length 约为：

```text
13.7438953472 s
```

因此 `W95/frame_length ~= 0.207`，并且 edge fraction 为 0，说明 profile 不再贴边。

## 11. 输出文件说明

最终输出目录：

```text
D:\Data\Raw Data\Type0ppln JTI\pplus_auto_dim_20260428_145224
```

主要文件：

| 文件 | 说明 |
|---|---|
| `README.md` | 本次运行自动生成的简要说明 |
| `run_config.json` | 完整运行参数 |
| `dedupe_report.csv` | `.ttbin` logical dataset 去重报告 |
| `pplus_auto_dim_summary.csv` | 每个 dim 的完整指标 |
| `auto_dim_decision.csv` | auto-dim 覆盖判据相关列 |
| `file_summary.csv` | 每个 logical file 的最终结果 |
| `profiles/P_plus_*.csv` | `P_plus` profile，sparse 模式下仅保存非零 bin |
| `profiles/P_minus_*.csv` | `P_minus` profile |
| `plots/P_plus_*.png` | 单 dim 的 `P_plus` 曲线 |
| `plots/P_minus_*.png` | 单 dim 的 `P_minus` 曲线 |
| `plots/time_support_vs_dim_*.png` | 时间支持随 dim 变化 |
| `plots/diag_band_fraction_vs_dim_*.png` | 主对角线带内比例随 dim 变化 |
| `logs/run.log` | 运行日志 |

## 12. 如何解读结果

### 12.1 为什么低维一直接近 0.95

低维时 `frame_length_ps` 远小于实际主对角线方向支持范围，所以 `P_plus` 被 frame 边界截断。此时：

```text
W95/frame_length ~= 0.95
```

只能说明当前 frame 几乎被填满，不能说明真实支持宽度就是这个值。

### 12.2 为什么 dim=68719476736 仍未 cover

该维度下：

```text
width_ratio_95 = 0.41482814341725316
edge_fraction = 0.23003622593330586
```

虽然 `W95/frame_length` 已小于 0.7，但边缘计数比例仍高，说明 profile 仍有明显贴边风险。因此状态为：

```text
NOT_SATURATED
```

这一步不能作为最终覆盖结论。

### 12.3 为什么 dim=137438953472 cover

该维度下：

```text
width_ratio_95 = 0.20741407170862658
edge_fraction = 0.0
relative_change_W95 = 0.0
```

三个覆盖判据同时满足：

- `width_ratio_95 < 0.7`
- `edge_fraction < 0.05`
- `relative_change_W95 < 0.05`

因此停止继续增大 dim，并标记：

```text
covered = True
status = OK
stop_reason = covered
```

## 13. 内存与速度注意事项

本任务高维部分的关键约束是不能分配 dense `dim` profile，更不能构造 dense `dim x dim` JTI。

对于最终维度：

```text
dim = 137438953472
```

如果构造 dense `dim x dim` JTI，矩阵元素数量约为：

```text
1.89e22
```

完全不可行。

如果构造 dense 一维 `P_plus` int64 数组，也约为 1 TB，不适合 32 GB 内存机器。

因此脚本在高维使用 sparse 存储：

```text
profile_storage = sparse
n_nonzero_P_plus_bins = 645394
estimated_profile_bytes ~= 10 MB
```

frame-origin scoring 使用 `ThreadPoolExecutor(max_workers=15)` 并行扫描候选 origin。线程方式可以共享大数组，避免多进程复制 paired arrays。

## 14. 复现建议

如果只想复现最终 covered 续跑，可从已生成的中间结果继续：

```powershell
python scripts\run_type0ppln_pplus_auto_dim.py --data-root "D:\Data\Raw Data\Type0ppln JTI" --auto-dim --min-next-dim 137438953472 --high-dim-max-dim 562949953421312 --bin-width-ps 100 --channels 1 3 --pairing-rule nearest --coincidence-window-ps 200 --diag-band-bins 1 --jobs 15 --profile-storage auto --continue-from-existing "D:\Data\Raw Data\Type0ppln JTI\pplus_auto_dim_20260428_144846"
```

如果从头开始，建议先 dry-run，再运行低维到高维的完整 auto-dim 流程，并保留每轮输出目录作为 `--continue-from-existing` 的输入。

## 15. 当前结论

> 2026-04-29 consistency note: 本节结论只适用于 Type0ppln direct pair-wise `P_plus` profile 的 acquisition-support / auto-dim 诊断，不应被引用为单光子相干时间、Schmidt number 或 ultra-high-dimensional fixed-lattice G2-like JTI 的最终维度结论。

在 `channels=1,3`、`coincidence_window_ps=200`、`bin_width_ps=100`、`diag_band_bins=1` 的设置下，Type0ppln 数据的主对角线方向 `P_plus` 需要远高于 `65536` 的维度才能覆盖。

最终在：

```text
dim = 137438953472
frame_length_ps = 13743895347200
```

达到覆盖。估计的 `P_plus` 95% 时间支持为：

```text
W95 = 2850677295100 ps ~= 2.8506772951 s
```

该结果是 direct pair-wise `P_plus` profile 的时间支持估计，不是 Schmidt number，也不是 dense cumulative JTI SVD 结果。
