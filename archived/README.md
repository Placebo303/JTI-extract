# Archived Files

These files are archived from earlier development phases and are no longer part of the active analysis pipeline.

Active tool: `src/jti_extract/cli/raw_aligned.py` — Raw-aligned FPC JTI extraction.

## mode_a/
Mode A 单线 JTI 提取（CV/DV/SVD）及 legacy wrappers。
已被 raw-aligned FPC JTI 模式取代。

| File | Description |
|------|-------------|
| `extract_jti.py` | Mode A wrapper → jti_extract.cli.extract |
| `compute_jti_schmidt.py` | Legacy wrapper → jti_extract.cli.schmidt |
| `tdc_layer_scan.py` | Legacy wrapper → jti_extract.cli.tdc_layer_scan |
| `tdc_residue_diagnostics.py` | Legacy wrapper → jti_extract.cli.tdc_residue |
| `sitecustomize.py` | 一次性 ttbin 通道检查工具 |

## mode_b/
Mode B BFC/FPC 多线 Schmidt 分析。
已被 raw-aligned FPC JTI 模式取代。

| File | Description |
|------|-------------|
| `compute_fpc_schmidt.py` | BFC/FPC multi-line Schmidt analysis (935 lines) |
| `run_fpc_multiline_analysis.py` | FPC multiline delay + centered-JTI (1396 lines) |

## diagnostics/
诊断工具集：巧合窗口、延时分布、时间线、delay alignment。
原始对齐模式不需要这些预处理步骤。

| File | Description |
|------|-------------|
| `analyze_coincidence_window.py` | Coincidence window analysis (212 lines) |
| `analyze_interchannel_delay.py` | Inter-channel delay distribution (284 lines) |
| `analyze_ttbin_coincidence_timeline.py` | Coincidence rate timeline (318 lines) |
| `jti_delay_alignment.py` | Delay-peak to JTI diagonal-offset alignment (618 lines) |
| `README_jti_delay_alignment.md` | Documentation for jti_delay_alignment.py |

## batch_runners/
旧批处理脚本。由 `scripts/run_raw_aligned_scan.py` 替代。

| File | Description |
|------|-------------|
| `run_bfc_40_50_batch.py` | BFC batch runner (158 lines) |
| `run_pseudo_cv_batch.py` | Pseudo-CV batch runner (86 lines) |
| `pseudo_cv_from_modeb.py` | Pseudo-CV from modeB (277 lines) |

## P_plus Analysis (Type0ppln)

| File | Description |
|------|-------------|
| `scripts/run_type0ppln_pplus_auto_dim.py` | Direct P_plus extraction for Type0ppln JTI data |
| `configs/type0ppln.yaml` | Type0ppln configuration |
| `configs/type2.yaml` | Old Type-II SPDC configuration template |
| `docs/TYPE0PPLN_PPLUS_AUTO_DIM_REPORT.md` | 572-line analysis report |
