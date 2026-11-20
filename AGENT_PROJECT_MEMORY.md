# Agent Project Memory

## 唯一活跃脚本
- `src/jti_extract/cli/raw_aligned.py` — Raw-aligned FPC JTI 提取
- `scripts/run_raw_aligned_scan.py` — 参数扫描
- `scripts/run_df776_dual_cavity.py` — 双腔（FP #1/#2）延时分析+提取+归一化合并一条龙

## 环境坑（2026-08 实测）
- Swabian 安装器把驱动目录写进**系统 PYTHONPATH**；临时改 PYTHONPATH 必须前置追加，不能覆盖，否则 `import TimeTagger` 失败。
- site-packages 里有指向旧 checkout `D:\Code\JTI_extract_clean` 的 editable 安装；跑本仓库代码要保证本仓库 `src` 在 sys.path 最前。
- 沙箱禁止 shell/python 写 `results\` 子树；分析输出请写到工作区根级新目录（如 `jti_results_20260807/`）。

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

## 自动延时（0.4.0，2026-11-20）

- `jti-raw-aligned` 现在 `--peaks-csv` 可选：只给 `.ttbin` 即可用两路时间标签互相关自动定 `tau_align_ps`。
  优先级：`--tau-align-ps` > (`--tau-auto` 或没给 peaks CSV → 互相关) > peaks CSV 最亮峰。
- 自动延时 = 配对 Δt 直方图（±25 ns，20 ps 分箱）→ 300 ps boxcar 平滑取最亮簇（平顶取中心/抛物线插值）
  → ±300 ps 内 2 ps 细分箱扣背景取质心。诊断写在 `raw_aligned_meta.json` 的 `tau_auto`。
- 新参数：`--tau-auto`、`--tau-search-window-ps 25000`、`--tau-coarse-bin-ps 20`、`--tau-smooth-ps 300`、
  `--tau-refine/--no-tau-refine`、`--tau-refine-window-ps 300`、`--tau-refine-bin-ps 2`、`--auto-delay-range`。
- 实测 FP #1 set1（ch1/ch3，全量 354 万 A 事件）：自动 tau ≈ **-119 ps**（粗测 -126 ps，精修 -118.9 ps）；
  历史 peaks CSV + 300 ps 平滑峰流程是 **-130 ps**，差约 10 ps（< 一个 40 ps bin）。复现历史值用 `--tau-align-ps -130`。
- 该数据的延时结构是 ~280-300 ps 周期的梳齿簇（FP 腔 FSR），所以 300 ps 平滑尺度是关键默认值；
  想让程序对齐单个窄齿就把 `--tau-smooth-ps` / `--tau-refine-window-ps` 调小。
- 通道必须对：FP #1/#2 数据是 ch1/ch3（默认 2/3 会报错，新报错会列出文件里实际存在的通道）。
- 环境：改前 `jti-raw-aligned` 命令不存在（site-packages 里是 0.1.0 editable 指向 `D:\Code\JTI_extract_clean`）。
  要么在仓库根目录用 `python -m jti_extract.cli.raw_aligned`（根目录 `jti_extract/__init__.py` shim 生效），
  要么 `python -m pip install -e ".[plotting]"`（必须带 [plotting]，否则写 PNG 会 RuntimeError）。
- 可靠性保护：搜索窗内配对数 < 5000 会告警（`TAU_AUTO_MIN_TRUSTED_PAIRS`）；多个高度 ≥98% 的平滑峰会打印
  `note: N near-equal correlation clusters` 并把候选峰位写进 `tau_auto.coarse.near_equal_candidates`；
  `--auto-delay-range` 在残余峰不可信（配对 <5000 或 <5σ）时保持 0 ps 中心并告警。
  实测：400k 事件（2141 对）时自动粗测会锁到 +1340 ps 的假峰 → 小样本务必用显式 tau。
- `raw_aligned_meta.json` 现在在 SVD 之后写出，`--compute-svd` 时 K/purity/lambda 都进 meta；
  `summary.csv` 增加 `tau_align_ps`、`tau_align_source` 两列。
- 测试：`python -m pytest -q` → 26 passed，其中 `tests/test_auto_tau.py` 16 个覆盖自动延时。
- 版本号现在单一来源：`src/jti_extract/_version.py`（0.4.0）。
