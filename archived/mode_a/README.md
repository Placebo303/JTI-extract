# Archived: Mode A — Single-Line JTI Extraction

## 功能
从 .ttbin 提取单线 JTI 矩阵（CV/DV/SVD），扫描 frame_origin，计算 Schmidt number。

## 核心算法
- all-pairs window pairing（事件可复用）
- frame_origin 扫描优化对角线对比度
- edge-guarded unwrapped JTI
- SVD/K 计算

## 主要文件
- `extract_jti.py` → wrapper for `jti_extract.cli.extract:main`
- `compute_jti_schmidt.py` → wrapper for `jti_extract.cli.schmidt:main`
- `tdc_layer_scan.py` → wrapper for `jti_extract.cli.tdc_layer_scan:main`
- `tdc_residue_diagnostics.py` → wrapper for `jti_extract.cli.tdc_residue:main`
- `sitecustomize.py` → 一次性 ttbin 通道检查工具

## 调用方式（已失效，仅供参考）
```bash
python extract_jti.py --ttbin <path> --binwidth-ps 20 --dimensions 128 --out <dir>
python compute_jti_schmidt.py --input <dir> --out <dir>
```

## Archive 原因
被 `src/jti_extract/cli/raw_aligned.py` 的 raw-aligned FPC JTI 提取模式取代。
src/jti_extract/ library 保留，但 CLI entry points 已从 pyproject.toml 移除。
