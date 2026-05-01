# JTI 提取与 TDC 40ps 诊断工具

这个仓库用于从 timetag 数据中提取离散 joint time-bin coincidence matrix，并配套完成 TDC 40ps residue 诊断与 Schmidt number 分析。项目采用 Python `src/` layout，同时保留旧脚本入口。

## 核心 workflow

1. 从 `parsed_timebin_data.npz` 或 `*.ttbin` 提取 JTI counts。
2. 诊断 singles / pair dt 的 40ps residue 结构。
3. 从 JTI counts CSV 计算 Schmidt number、purity 和 singular weights 摘要。

## 安装

```bash
python -m pip install -e .
python -m pip install -e ".[plotting,dev]"
```

`*.ttbin` 读取需要 Swabian TimeTagger Python bindings。该依赖随 Swabian 软件安装，不在 PyPI 强制安装。

## 最小命令

```bash
python extract_jti.py --data "<path/to/dataset>" --binwidth-ps 200 --dimensions 32 --frame-origin-ps 0 --out results/jti_run
python compute_jti_schmidt.py --input results/jti_run
python tdc_residue_diagnostics.py --ttbin "<path/to/data.ttbin>" --out results/tdc_residue
python tdc_layer_scan.py --ttbin "<path/to/data.ttbin>" --out results/tdc_layer_scan
```

安装后也可以使用 console scripts：

```bash
jti-extract --help
jti-schmidt --help
jti-tdc-residue --help
jti-tdc-layer-scan --help
```

## 文档导航

- [数据契约](docs/DATA_CONTRACT.md)
- [CLI 说明](docs/CLI.md)
- [输出文件](docs/OUTPUTS.md)
- [工作流](docs/WORKFLOWS.md)
- [40ps 诊断](docs/DIAGNOSTICS_40PS.md)
- [Schmidt 分析](docs/SCHMIDT_ANALYSIS.md)
- [故障排查](docs/TROUBLESHOOTING.md)
- [给 AI 接手用的省 token 摘要](docs/TOKEN_SUMMARY.md)
