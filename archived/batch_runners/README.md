# Archived: Batch Runners

## 工具列表

### run_bfc_40_50_batch.py (158 行)
BFC 数据的 Mode B + CV 5ps 批处理。
调用：`python run_bfc_40_50_batch.py --data-root <dir> ...`

### run_pseudo_cv_batch.py (86 行)
6 组合（3 角度 × 2 binwidth）pseudo-CV 批处理。
调用：`python run_pseudo_cv_batch.py --data-root <dir> ...`

### pseudo_cv_from_modeb.py (277 行)
从 modeB 结果生成 pseudo-CV 热图。
调用：`python pseudo_cv_from_modeb.py --input <dir> ...`

## Archive 原因
批处理逻辑由 `scripts/run_raw_aligned_scan.py` 替代。
