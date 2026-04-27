# JTI Counts 提取 (`extract_jti.py`)

[English README](./README_EN.md) | [License](./LICENSE)

从已对齐的到达时间数据中提取 arrival-time basis 下的离散 joint time-bin coincidence matrix（下文简称 JTI counts 表）。

主入口脚本：`extract_jti.py`

## 这个工具输出什么

主结果是离散 joint time-bin counts matrix，也就是 `counts.csv`。

- 输入 timetag 默认视为两路相对时间已经完成对齐。
- `frame_origin_ps` 控制离散 time-bin 映射所使用的公共时间原点 / frame phase。
- 当前版本默认采用 `strict_single_hit_per_frame` 后选择规则。
- 因此输出结果不是“所有事件的无条件二维直方图”，而是经过该规则筛选后的离散 JTI counts 表。

## 功能

- 支持两种输入：`parsed_timebin_data.npz` 或原始 `*.ttbin`
- 导出主结果 `counts.csv`
- 显式支持 `--frame-origin-ps`
- 支持 `--scan-frame-origin`，用于扫描候选 `t0` 并诊断主对角线与相邻次级对角线
- 可选导出 `NPZ` 和 `PNG`
- 旧的 background subtraction / peak alignment / normalization 仍可作为可选分析步骤保留，但不会修改主输出 `counts.csv`

## 环境要求

- Python 3
- 必需：`numpy`
- 可选：`matplotlib`（仅 `--plot` 需要）
- 可选：Swabian `TimeTagger` Python 绑定（仅直接读取 `*.ttbin` 需要）

安装基础依赖：

```bash
python -m pip install -U numpy
python -m pip install -U matplotlib  # 仅 --plot 需要
```

## 快速开始

查看命令行帮助：

```bash
python extract_jti.py --help
```

### 最小提取示例

```bash
python extract_jti.py \
  --data "E:\Data\YourDataset" \
  --binwidth-ps 200 \
  --dimensions 32 \
  --frame-origin-ps 0 \
  --out "E:\Data\YourDataset\jti_out"
```

### Frame-Origin 扫描示例

如果 JTI 中存在稳定的相邻次级对角线，可以用扫描判断它是否与 `t0` 的选择有关。

```bash
python extract_jti.py \
  --data "E:\Data\YourDataset" \
  --binwidth-ps 200 \
  --dimensions 32 \
  --scan-frame-origin \
  --frame-origin-start-ps 0 \
  --frame-origin-stop-ps 200 \
  --frame-origin-step-ps 5 \
  --out "E:\Data\YourDataset\jti_out"
```

### 输入模式

模式 A：使用 `parsed_timebin_data.npz`（推荐）

脚本会在 `--data` 下查找：

- `parsed_timebin_data.npz`
- `01_raw_parsing/parsed_timebin_data.npz`
- `results/01_raw_parsing/parsed_timebin_data.npz`

模式 B：直接读取 `*.ttbin`

需要 Swabian `TimeTagger` Python 绑定。

```bash
python extract_jti.py \
  --data "E:\Data\YourDataset" \
  --ttbin "E:\Data\YourDataset\file.ttbin" \
  --binwidth-ps 200 \
  --dimensions 32 \
  --frame-origin-ps 0 \
  --out "E:\Data\YourDataset\jti_out"
```

如果目录内同时存在 NPZ 和 TTBIN，但想强制使用 TTBIN，请加 `--prefer-ttbin`。

## 输出文件

每个 `(dimension, binwidth_ps)` 组合对应一个前缀：

`{prefix}jti_dim{dim}_bw{bw}ps`

主输出：

- `{stem}.counts.csv`
- `{stem}.meta.json`

可选输出：

- `{stem}.npz`，其中主数组为 `jti_counts`
- `{stem}.png`，基于原始 counts 的热力图

启用 `--scan-frame-origin` 时额外输出：

- `{stem}.frame_origin_scan.csv`
- `{stem}.frame_origin_scan_best.json`

汇总文件：

- `{prefix}jti_summary.json`

## 扫描诊断指标

frame-origin 扫描会计算：

- `diag_main_sum`：主对角线计数和
- `diag_pm1_sum`：上下相邻一条次级对角线计数和，按非循环方式处理
- `total_sum`：总计数
- `diag_main_fraction`
- `diag_pm1_fraction`
- `diag_contrast = diag_main_fraction - diag_pm1_fraction`

最优 `frame_origin_ps` 的选择规则为：

1. 最大化 `diag_main_fraction`
2. 若并列，则最小化 `diag_pm1_fraction`
3. 若仍并列，则最大化 `diag_contrast`
4. 若仍并列，则取最小 `frame_origin_ps`

## 说明

- 按项目约定，`TimeTag` 视为 ps 单位。
- `frame_origin_ps` 控制的是公共时间原点 / frame phase，不是两路相对延时补偿。
- 扫描模式只允许单个 `--binwidth-ps` 和单个 `--dimensions`。
- `--raw-ch-a-id` / `--raw-ch-b-id` 是 TTBIN 解析时的硬件通道号。
- `--ch-a` / `--ch-b` 是映射后的逻辑标签。

## 内置自测

无需额外测试框架：

```bash
python extract_jti.py --self-test
```

## 常见问题

- `numpy is missing ...`：当前 Python 环境缺少 `numpy`
- `matplotlib is required for --plot`：安装 `matplotlib` 或去掉 `--plot`
- 读取 `*.ttbin` 时 `cannot import TimeTagger`：安装 Swabian 软件及匹配的 Python 绑定，或改用 NPZ 输入模式
