# Agent Project Memory

## 唯一活跃脚本
- `src/jti_extract/cli/raw_aligned.py` — Raw-aligned FPC JTI 提取
- `scripts/run_raw_aligned_scan.py` — 参数扫描

## 调用方式
```bash
jti-raw-aligned --ttbin ... --peaks-csv ... --out ...
python -m jti_extract.cli.raw_aligned --ttbin ... --peaks-csv ... --out ...
python scripts/run_raw_aligned_scan.py
```

## 核心函数
- `build_raw_aligned_jti()` — chunk streaming 配对 + 帧坐标 binning
- `infer_tau_align_brightest()` — 从 peaks CSV 自动确定 tau_align_ps
- `_compute_svd_k()` — SVD/K 计算
- `_compute_diagonal_diagnostics()` — 对角线偏移诊断
- `_compute_diagonal_diagnostics()` — count balance 验证

## 数据流
```
.ttbin + pminus_peaks.csv
  → load_tags() → t_a, t_b
  → infer_tau_align_brightest() → tau_align_ps
  → build_raw_aligned_jti() → H, meta
  → _compute_svd_k() → K, purity, lambdas (optional)
  → save outputs
```

## 关键约束
- 不做 per-tooth ROI 筛选
- 不分配 peak_id
- 不做 comb line 重排
- 不做背景扣除
- 保留原始噪声

## 已 Archive（archived/）
- mode_a/ — Mode A (extract.py)
- mode_b/ — Mode B (compute_fpc_schmidt.py)
- diagnostics/ — 诊断工具
- batch_runners/ — 旧批处理

## library 依赖
- `jti_extract.cli.tdc_layer_scan.load_tags` — 加载 .ttbin

## 测试
- `tests/test_binning.py` — 保留
- `tests/test_io_contract.py` — 保留
- 其余测试已 archive
