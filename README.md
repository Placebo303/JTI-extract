# JTI-extract

Raw-aligned FPC JTI (Joint Time-Intensity) extraction from TimeTagger `.ttbin` data.

## Quick Start

```bash
pip install -e .

jti-raw-aligned \
  --ttbin data.1.ttbin \
  --peaks-csv pminus_peaks.csv \
  --binwidth-ps 40 --dimensions 80 --guard-bins 2 \
  --delay-min-ps -1500 --delay-max-ps 300 \
  --compute-svd \
  --out results/
```

## 依赖
- numpy
- matplotlib（绘图）
- Swabian TimeTagger Python API（读取 .ttbin）

## 原理
只做坐标校准，不做模式选择和结构重排：
1. 从 pminus_peaks.csv 最亮峰确定 `tau_align_ps`
2. 全局 B 通道校正：`t_B_corr = t_B - tau_align_ps`
3. 全局 residual delay window 筛选：`delay_min <= (t_B_corr - t_A) <= delay_max`
4. 帧坐标 + edge guard + binning → `H_raw_aligned`
5. 可选 SVD/K 计算

## 输出
- `H_raw_aligned.csv/npz/png` — JTI 矩阵
- `residual_tau_histogram.csv/png` — 残差延时直方图
- `raw_aligned_meta.json` — 完整 metadata
- `summary.csv`（`--compute-svd` 时）— SVD/K 结果

## 参数扫描
```bash
python scripts/run_raw_aligned_scan.py
```

## 项目结构
```
src/jti_extract/cli/raw_aligned.py     ← 主脚本
scripts/run_raw_aligned_scan.py        ← 参数扫描
src/jti_extract/                       ← library（load_tags 等）
tests/                                 ← 测试
docs/                                  ← 文档
archived/                              ← 旧脚本存档
```

## 文档
- [CLI 参考](docs/CLI.md)
- [工作流](docs/WORKFLOWS.md)
- [输出格式](docs/OUTPUTS.md)
- [SVD/K 算法](docs/SCHMIDT_ANALYSIS.md)
- [数据格式](docs/DATA_CONTRACT.md)
- [故障排除](docs/TROUBLESHOOTING.md)
