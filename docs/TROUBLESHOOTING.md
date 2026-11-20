# 故障排除

## 环境

### cannot import Swabian TimeTagger Python API

报错示例：`RuntimeError: cannot import Swabian TimeTagger Python API from <python>: No module named 'TimeTagger'`

- 该 API 由 Swabian 的 Time Tagger 软件提供，**不在 PyPI 上**，`pip install` 装不到。
- Windows 默认安装位置：`C:\Program Files\Swabian Instruments\Time Tagger\driver\python`，
  安装器一般会把它写入系统 `PYTHONPATH`。
- 若当前 Python 环境找不到，运行时前置：

  ```bat
  set PYTHONPATH=C:\Program Files\Swabian Instruments\Time Tagger\driver\python;%PYTHONPATH%
  python -c "import TimeTagger; print(TimeTagger.__file__)"
  ```

- 注意用一个 Python 时就别临时覆盖 `PYTHONPATH`（要用 `set X=%X%;new` 追加），否则会连带丢掉驱动目录。

### No module named 'jti_extract.cli.raw_aligned'

两种原因：

1. 不在仓库根目录，且本机 site-packages 里有一个**旧的 editable 安装**（曾指向
   `D:\Code\JTI_extract_clean`）——旧版本没有 `raw_aligned` 模块。
   → 在仓库根目录执行 `python -m jti_extract.cli.raw_aligned ...`（根目录有 dev shim），
   或执行 `python -m pip install -e ".[plotting]"` 把安装指向本仓库。
2. `pip install -e .` 没装过、也不在仓库根目录。同上处理。

### matplotlib 报错（PNG 输出失败）

报错：`RuntimeError: matplotlib is required for PNG output: ...`

- 安装：`python -m pip install -e ".[plotting]"`，或 `python -m pip install matplotlib`。
- 计算（CSV/NPZ/meta）在写 PNG 之前已经完成；但仍建议装好，避免整个运行以非零码结束。

### 瓦片显示 / 中文乱码（可选）

matplotlib 默认字体对中文支持不佳，热图标题用英文即可；如需中文标题，自行设置
`plt.rcParams["font.sans-serif"]`。

## 输入与通道

### No events found for channel A=... / B=...

0.4.0 的错误信息会列出该文件里**实际存在的通道号**，例如：

```text
No events found for channel A=2 / B=3 in xxx.1.ttbin.
Channels present in the file: [1, 3]. Check --raw-ch-a-id / --raw-ch-b-id.
```

按提示改 `--raw-ch-a-id` / `--raw-ch-b-id`（FP #1 / FP #2 的 DF776.348 数据是 1 / 3）。

### cannot calibrate the delay from correlation: no A-B pairs

- 两个通道在该搜索窗内没有任何配对：通道选错、`.ttbin` 为空、或真实延时超过
  `--tau-search-window-ps`。
- 加大搜索窗：`--tau-search-window-ps 100000`；或显式 `--tau-align-ps` / 给 `--peaks-csv`。

### WARNING: weak correlation peak (<5 sigma)

- 采集太短、符合太少，或数据里没有明显符合峰（纯偶然符合）。
- 换更长采集；或显式 `--tau-align-ps`；或给 `--peaks-csv`。
- 也可以只用于评估：自动值仍会写入 `tau_auto`，但不要把它当可靠校准。

### WARNING: only N A-B pairs inside the search window

- 搜索窗内配对数 < 5000（`TAU_AUTO_MIN_TRUSTED_PAIRS`）：样本不足，自动延时可能锁到背景涨落。
- 用更长采集；或 `--max-events` 不要限太小；或改用 `--tau-align-ps` / `--peaks-csv`。
- 检查方式：看 `residual_tau_histogram.png` 与 `tau_auto` 里的 `n_pairs`。

### note: N near-equal correlation clusters

- 不是错误：数据有多个接近等高的符合簇（梳齿 / 多模 / FP 腔模式），“亮簇”只是模式选择。
- 同一批数据要横向比较时，固定 `--tau-align-ps`；候选峰位在
  `tau_auto.coarse.near_equal_candidates`。

### WARNING: --auto-delay-range ... not trustworthy

- `--auto-delay-range` 实测的残余峰配对数 < 5000 或显著性 < 5σ，程序不挪窗（保持 0 ps 中心）。
- 修：先解决 tau 本身（显式 `--tau-align-ps`），或换更长采集，再用 `--auto-delay-range`。

### WARNING: correlation peak sits at the search-window edge

- 真实延时接近或超过搜索窗边界 → 加大 `--tau-search-window-ps`（配对数和耗时随之增加）。

### peaks CSV not found

- 给了 `--peaks-csv` 但路径不对。去掉该参数即可改用 ttbin 互相关自动估计，
  或改对路径；也可用 `--tau-auto` 强制忽略该文件。

## 延时与矩阵质量

### Cannot determine tau_align_ps

- 只在使用 peaks CSV 时出现：CSV 为空或 `counts` 全 ≤ 0。
- 修：补正确峰表，或删掉 `--peaks-csv` 让它走自动互相关，或显式 `--tau-align-ps`。

### delay_span_ps >= frame_period_ps

- residual 延时窗比一个 frame period 还宽，跨帧剔除会很多。
- 缩小 `--delay-min-ps` / `--delay-max-ps`，或增大 `--dimensions`（frame period = N × binwidth）。

### residual_tau_histogram 主峰不在 0 ps 附近

说明 `tau_align_ps` 没把符合峰对到 0：

- 自动/CSV 给的 tau 不准 → 显式 `--tau-align-ps`；
- 或加 `--auto-delay-range` 把 residual 窗中心挪到实测残余峰（meta 里 `delay_window_center_ps`）；
- 先看终端打印的 coarse / refined 峰位与显著性。

### H_raw_aligned 主对角线不清晰

- A/B 通道接反 → 交换 `--raw-ch-a-id` / `--raw-ch-b-id`；
- tau 符号或数值不对（看 residual 直方图）；
- `--frame-origin-ps` 需要调整；
- 延时窗选得过窄，只剩边缘的齿。

### cross_frame_rejected 异常偏高

- 延时窗太宽或 frame period 太小 → 缩小 delay 窗，或增大 `--dimensions`。

### count_balance_error != 0

- 代码 bug，不应发生。请附上 `raw_aligned_meta.json` 报告。

## 缓存与性能

### 为什么换了参数还重新读 ttbin / 为什么没有重读

- 缓存文件：`<out>/_tag_cache/tags_cache_ch{A}_ch{B}.npz`，key = ttbin 绝对路径 + 大小 + mtime +
  通道号 + `--max-events`。
- 换 `--out`、换通道、改 `--max-events`、ttbin 被覆盖/改名 → 重新解析；
- 只改 `--tau-*` / `--delay-*` / `--binwidth-ps` 等 → 复用缓存。
- 缓存可安全删除，下次运行会重建。

### 运行很慢

- ttbin 解析 + JTI 配对都是全量扫描；先用 `--max-events 200000` 试参数，再全量跑。
- 全量数据（几百万事件）一次提取是本机分钟级；`--tau-search-window-ps` 过大会线性增加配对数。

## 文档与测试

- 版本号单一来源：`src/jti_extract/_version.py`；`pyproject.toml` 与包内 `__version__` 应一致。
- 测试：`cd <repo> && python -m pytest -q`（当前 26 passed）。
- 若 `tests/test_io_contract.py` 在 Windows 上因 `tests/_work/...npz` 被占用而失败，
  关掉占用该文件的进程后重跑。
