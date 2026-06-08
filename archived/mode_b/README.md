# Archived: Mode B — BFC/FPC Multi-Line Schmidt Analysis

## 功能
从 FPC/BFC 数据提取多线 comb JTI，计算 per-tooth 和 global Schmidt-like K。

## 核心算法
- peak-aware greedy-unique pairing（事件不复用）
- per-tooth ROI 筛选（prominence fraction）
- H_comb, H_full_window, H_tooth_m 三种 JTI
- K_comb_weight 有效 comb 成分数
- 残差延时诊断

## 主要文件
- `compute_fpc_schmidt.py` — 主分析脚本 (935 行)
- `run_fpc_multiline_analysis.py` — FPC 多线 delay + centered-JTI (1396 行)

## 调用方式（已失效，仅供参考）
```bash
python compute_fpc_schmidt.py \
  --ttbin <path> --peaks-csv <path> --delay-csv <path> \
  --binwidth-ps 20 --dimensions 128 --guard-bins 2 \
  --out <dir>
```

## Archive 原因
被 `src/jti_extract/cli/raw_aligned.py` 的 raw-aligned 模式取代。
raw-aligned 模式不做 per-tooth ROI 筛选、不分配 peak_id、不重排 comb line。
