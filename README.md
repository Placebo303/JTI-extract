# JTI提取 (`extract_jti.py`)

[English README](./README_EN.md) | [License](./LICENSE)

从 Swabian Instruments **Time Tagger** 的 ToA 时间戳数据中提取 **delay-delay JTI**（Joint Temporal Intensity）矩阵，并导出为 **CSV / NPZ / PNG**（可选）。

主入口脚本：`extract_jti.py`

## 功能

- 支持两种输入来源：`parsed_timebin_data.npz` 或原始 `*.ttbin`
- 支持多组参数批量导出（例如 `--binwidth-ps 50,100 --dimensions 16,32`）
- 可选：accidentals 背景扣除、peak 对齐、归一化、PNG 热力图导出
- 支持 Windows 路径与 WSL/Linux 路径转换

## 环境要求

- Python 3
- 必需：`numpy`
- 可选（仅 `--plot`）：`matplotlib`
- 可选（仅直接读取 `*.ttbin`）：Swabian `TimeTagger` Python 绑定

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

### 模式 A：使用 `parsed_timebin_data.npz`（推荐）

脚本会在 `--data` 目录下查找：

- `parsed_timebin_data.npz`
- `01_raw_parsing/parsed_timebin_data.npz`
- `results/01_raw_parsing/parsed_timebin_data.npz`

运行示例：

```bash
python extract_jti.py --data "E:\Data\YourDataset"
```

导出 NPZ + PNG：

```bash
python extract_jti.py \
  --data "E:\Data\YourDataset" \
  --out "E:\Data\YourDataset\jti_out" \
  --npz --plot
```

### 模式 B：直接读取 `*.ttbin`

需要 Swabian `TimeTagger` Python 绑定。

```bash
python extract_jti.py \
  --data "E:\Data\YourDataset" \
  --ttbin "E:\Data\YourDataset\file.ttbin" \
  --binwidth-ps 100 --dimensions 16 \
  --out "E:\Data\YourDataset\jti_out" \
  --plot
```

如果目录内同时有 NPZ 和 TTBIN，但你想强制读取 TTBIN，请加 `--prefer-ttbin`。

## 输出文件

每个 `(dimension, binwidth_ps)` 组合会生成一个文件名前缀：

`{prefix}jti_dim{dim}_bw{bw}ps`

默认输出：

- `{stem}.counts.csv`
- `{stem}.normalized.csv`
- `{stem}.meta.json`

可选输出：

- `{stem}.npz`（加 `--npz`）
- `{stem}.png`（加 `--plot`）

汇总文件：

- `{prefix}jti_summary.json`

## 常见注意点

- `--raw-ch-a-id` / `--raw-ch-b-id` 是硬件原始通道号（读 TTBIN 时用，默认 `1/2`）
- `--ch-a` / `--ch-b` 是映射后的逻辑标签（默认 `0/1`）
- 不要把原始通道号和逻辑标签混用

## 常见报错排查

- `numpy is missing ...`：当前 Python 环境没有 numpy
- `matplotlib is required for --plot`：安装 matplotlib 或去掉 `--plot`
- `cannot import TimeTagger`：安装 Swabian 软件和对应 Python 绑定，或改用模式 A

