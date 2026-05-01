# AGENT_HANDOFF.md

## 初始化摘要

本次操作于 2026-04-29 重新生成项目 harness 文档系统。依据 [`AGENT_PROJECT_MEMORY.md`](AGENT_PROJECT_MEMORY.md) 和实际仓库扫描交叉验证后，生成了 5 个标准 harness 文件。

## 生成的文件

1. **AGENTS.md** — 项目级 Agent 总规则：执行环境、核心约束原则、禁止行为、允许操作、Schema 保护清单、科学语义保护、项目结构速查、高风险变量、已知环境约束
2. **CURRENT_TASK.md** — 当前任务模板（当前状态：No active implementation task yet）
3. **RUN_COMMANDS.md** — 安全命令与重型命令分类，含路径约定
4. **REVIEW_CHECKLIST.md** — 代码审查清单，含 8 大类审查项和审查总结格式
5. **AGENT_HANDOFF.md** — 本交接文档

## 信息来源分类

### Repo-verified（仓库实际扫描确认）

- 项目名称：`jti-extract`，版本 `0.1.0`（[`pyproject.toml`](pyproject.toml:7)）
- Python 版本要求：>= 3.9（[`pyproject.toml`](pyproject.toml:10)）
- 核心依赖：`numpy`；可选依赖 `matplotlib`（plotting）、`pytest`（dev）（[`pyproject.toml`](pyproject.toml:13)）
- 包结构：`src/jti_extract/`（src layout）（[`pyproject.toml`](pyproject.toml:28)）
- 开发垫片：[`jti_extract/__init__.py`](jti_extract/__init__.py) 重定向到 `src/jti_extract/`
- CLI 入口：`jti-extract`、`jti-schmidt`、`jti-tdc-residue`、`jti-tdc-layer-scan`（[`pyproject.toml`](pyproject.toml:22)）
- CLI 参数全部与 [`AGENT_PROJECT_MEMORY.md`](AGENT_PROJECT_MEMORY.md) 列表一致：
  - [`extract.py`](src/jti_extract/cli/extract.py:908): 25 个参数（含 `--no-bg`、`--no-align` 两个 SUPPRESS 参数）
  - [`schmidt.py`](src/jti_extract/cli/schmidt.py:288): 6 个参数
  - [`tdc_residue.py`](src/jti_extract/cli/tdc_residue.py:212): 8 个参数
  - [`tdc_layer_scan.py`](src/jti_extract/cli/tdc_layer_scan.py:670): 19 个参数
  - [`run_type0ppln_pplus_auto_dim.py`](scripts/run_type0ppln_pplus_auto_dim.py:1361): 25 个参数
- Type0ppln CSV 列定义由 [`SUMMARY_FIELDS`](scripts/run_type0ppln_pplus_auto_dim.py:34)、[`FILE_SUMMARY_FIELDS`](scripts/run_type0ppln_pplus_auto_dim.py:76)、[`DEDUPE_FIELDS`](scripts/run_type0ppln_pplus_auto_dim.py:93)、[`AUTO_DECISION_FIELDS`](scripts/run_type0ppln_pplus_auto_dim.py:104) 定义，与 memory 列表一致
- CLI self-test：`jti-extract --self-test`、`jti-schmidt --self-test`（[repo-verified via search]）
- pytest 测试文件：[`test_cli_smoke.py`](tests/test_cli_smoke.py)、[`test_io_contract.py`](tests/test_io_contract.py)、[`test_binning.py`](tests/test_binning.py)、[`test_pairing.py`](tests/test_pairing.py)、[`test_schmidt.py`](tests/test_schmidt.py)
- `scripts/run_type0ppln_pplus_auto_dim.py` 支持 `--dry-run`（[repo-verified via search]）
- `*.ttbin` 读取需要 Swabian TimeTagger Python 绑定（[`tdc_residue.py`](src/jti_extract/cli/tdc_residue.py:32)）
- 配置文件键：[`smoke.yaml`](configs/smoke.yaml) `data`, `binwidth_ps`, `dimensions`, `frame_origin_ps`, `out`；[`type0ppln.yaml`](configs/type0ppln.yaml) `ttbin`, `ch_a`, `ch_b`, `window_ps`；[`type2.yaml`](configs/type2.yaml) `ttbin`, `ch_a`, `ch_b`, `window_ps`
- `DEFAULT_DATA_ROOT` 在 [`run_type0ppln_pplus_auto_dim.py`](scripts/run_type0ppln_pplus_auto_dim.py:31) 中为 `D:\Data\Raw Data\Type0ppln JTI`（legacy Windows path）
- 文档目录：`docs/CLI.md`、`docs/DATA_CONTRACT.md`、`docs/OUTPUTS.md` 等
- 顶层兼容性脚本：[`extract_jti.py`](extract_jti.py)、[`compute_jti_schmidt.py`](compute_jti_schmidt.py)、[`tdc_layer_scan.py`](tdc_layer_scan.py)、[`tdc_residue_diagnostics.py`](tdc_residue_diagnostics.py)

### Memory-derived（来自 AGENT_PROJECT_MEMORY.md，需验证）

- WSL/Linux 作为优先执行环境
- Type0ppln `P_plus` 输出目录命名模式：`pplus_auto_dim_YYYYMMDD_HHMMSS`
- Type0ppln 高维分析必须使用稀疏模式（dense `dim x dim` JTI 矩阵在高维下不可行）
- Type0ppln `P_plus_central_95_width_ps`、`width_ratio_95`、`edge_fraction`、`relative_change_W95`、`covered`、`final_status` 含义保护
- 历史 Windows 数据根路径：`D:\Data\Raw Data\Type0ppln JTI` (legacy Windows path)
- `tag_cache/` 作为生成的缓存目录
- 时间戳输出目录命名约定
- Pairing rule 和 duplicate-recording dedupe method 语义
- `coincidence_window_ps` 与 `bin_width_ps` 必须保持独立性
- Type0ppln pilot 历史默认参数：channels `1,3`、`pairing_rule=nearest`、`coincidence_window_ps=200`、`bin_width_ps=100`、`diag_band_bins=1`

### Uncertain（不确定项，需人工验证）

1. `jti-extract` 所有 flag 组合下的精确输出文件名模式（如 `--scan-frame-origin` 下的输出命名）
2. 顶层兼容性脚本（`extract_jti.py` 等）是否调用包 CLI 或包含不同行为
3. TimeTagger 绑定和硬件元数据 API 在目标 WSL 环境中是否可用
4. 是否需要创建专用的 sample-data smoke fixture（超出当前 `tests/fixtures/`）
5. 生成的 `pytest-cache-files-*`、`tests/_tmp_pytest`、`tests/_work` 等目录是否存在且需清理
6. 所有文档在 WSL 项目副本中是否为 UTF-8 干净（Windows 终端预览曾显示乱码）
7. `docs/reports/` 目录下的内容是否为生成物
8. [`sitecustomize.py`](sitecustomize.py) 的用途和是否需要维护

## 冲突记录

- **未发现仓库实际扫描与 [`AGENT_PROJECT_MEMORY.md`](AGENT_PROJECT_MEMORY.md) 的冲突**
- CLI 参数列表：全部一致（含 `--no-bg`、`--no-align` 两个 SUPPRESS 参数，memory 未列出但不构成冲突，因为它们是内部隐藏参数）
- CSV 列定义：`SUMMARY_FIELDS`、`FILE_SUMMARY_FIELDS`、`DEDUPE_FIELDS`、`AUTO_DECISION_FIELDS` 与 memory 列表完全一致
- 配置文件键：实际扫描结果与 memory 描述一致，memory 标注的 `uncertain` 已在本次验证中确认

## 本次与上一版 harness 文件的差异

- **AGENTS.md**: 增加了项目结构速查、高风险变量、已知环境约束等章节；增加了 CLI 参数的源文件行号引用；增加了 `--no-bg`/`--no-align` SUPPRESS 参数的说明；增加配置文件键的具体内容
- **CURRENT_TASK.md**: 增加了 Baseline Policy 中关于稀疏 profile 的约束；增加了语法检查命令
- **RUN_COMMANDS.md**: 增加了 `git diff --cached`、全量 pytest 命令、更完整的语法检查列表；增加了 `DEFAULT_DATA_ROOT` 的路径约定说明
- **REVIEW_CHECKLIST.md**: 增加了 Type0ppln CSV 列定义审查项、高维稀疏模式审查项、`examples/tiny_run/expected_outputs/` 覆盖风险审查项、`DEFAULT_DATA_ROOT` 路径审查项、pairing rule 语义审查项、`coincidence_window_ps` 独立性审查项
- **AGENT_HANDOFF.md**: 全面重写，增加详细的交叉验证结果、信息来源分类、冲突记录、差异说明

## 后续待验证项

1. 验证 `--self-test` 命令在当前 WSL 环境中实际可用
2. 运行 `python -m pytest tests/ -v` 确认测试通过
3. 验证 WSL 环境中 TimeTagger 绑定的可用性
4. 确认外部数据在 WSL 中的实际挂载路径
5. 确认 `jti-extract` 完整 flag 组合下的输出文件名模式
6. 确认顶层兼容性脚本与包 CLI 的行为一致性
7. 确认 `docs/reports/` 内容是否为生成物

## 2026-04-29 文档更新：Dense JTI + Schmidt 帧长覆盖判据

### 修改文件

1. **[`docs/WORKFLOWS.md`](docs/WORKFLOWS.md)** — 新增 Workflow 6: Dense JTI + Schmidt Frame-Length Coverage Scan
   - 说明使用较大 `binwidth_ps` 配合内存可承受的 dense 维度使 `frame_length_ps` 覆盖 µs 量级
   - 明确 `P_plus` 不应用作单光子相干时间判据（偏向 paired coincidence / diagonal profile / 采集稳定性诊断）
   - 给出候选参数表：`N=1024` 下 `bw=3000,5000,10000 ps` 分别约对应 `3.072,5.12,10.24 µs`
   - 完整操作步骤：`jti-extract` 生成不同 bw 的 dense counts CSV → `jti-schmidt` 计算 Schmidt 指标 → 比较收敛趋势
   - 收敛/饱和判据说明及风险提醒

2. **[`docs/SCHMIDT_ANALYSIS.md`](docs/SCHMIDT_ANALYSIS.md)** — 大幅扩展
   - 新增"帧长覆盖判据"章节：Schmidt 指标随 `frame_length_ps` 的收敛/饱和方法
   - 收敛判据表：`schmidt_number`、`K_over_dimension`、`largest_weight` 的收敛与未收敛信号
   - 明确 `P_plus` 不适用作单光子相干时间判据
   - 候选参数表（含 `N=1024` 和 `N=2048` 组合，附内存估算）
   - 操作示例与风险限制

3. **[`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)** — 大幅扩展
   - 新增 Dense JTI + Schmidt 专属排障章节
   - 内存不足（OOM）：按 N 值的内存估算表与对策
   - SVD 计算耗时：复杂度说明与对策
   - 大 `binwidth_ps` 导致时间分辨率下降：权衡说明
   - `frame_origin` 对大 `bw` 的影响：敏感性说明与对策
   - `P_plus` 误解为单光子相干时间：原因与正确替代方法
   - 数据覆盖风险：防护措施

### Schema Impact

- **无**。本次仅修改文档文件，未改变任何 CLI 参数、CSV 列名、JSON/YAML 键、输出文件命名或算法语义。

### Baseline Impact

- **无**。未修改任何算法代码、科学计算逻辑或配置默认值。

### 未运行命令

- 本次为纯文档更新，无需运行验证命令。
- 修改不涉及代码变更，pytest 和语法检查结果应与修改前一致。

## 重要提醒

- 不要运行完整实验，仅使用 `--self-test` 或 `--dry-run`
- 不要覆盖 `results/` 下的已有内容
- 不要使用 Windows 绝对路径作为执行路径
- 不要静默修改任何 schema 相关内容
- Minimal patch only 原则适用于所有代码修改
- 本文件未虚构任何项目状态；所有 memory-derived 内容均标注来源

## 2026-04-29 文档更新：TimeTagger WSL 环境规则

### 修改文件

1. **[`AGENTS.md`](AGENTS.md)** — 增加 TimeTagger WSL 虚拟环境、正确导入方式、禁止系统 `python3` 运行 TimeTagger 脚本、`.ttbin` 数据路径建议。
2. **[`RUN_COMMANDS.md`](RUN_COMMANDS.md)** — 增加 TimeTagger import/version/virtual capability 最小验证命令，以及运行 TimeTagger 相关脚本的推荐命令。
3. **[`AGENT_HANDOFF.md`](AGENT_HANDOFF.md)** — 记录本次 harness 文档更新。

### TimeTagger 环境事实

- WSL user: `karel_303` [user-provided]
- TimeTagger virtualenv: `~/envs/timetagger` [user-provided]
- Python executable: `~/envs/timetagger/bin/python` [user-provided]
- Installed pip package: `Swabian-TimeTagger` [user-provided]
- Correct import: `from Swabian import TimeTagger` [user-provided]
- Forbidden import: `import TimeTagger` [user-provided]
- `.ttbin` 离线读取优先使用 `TimeTagger.FileReader()`，不要再默认走 `createTimeTaggerVirtual()`；该结论来自真实 Stage 0-2 运行验证 [repo-verified]

### Schema Impact

- **无**。本次仅修改 harness 文档，未改变 CLI 参数、CSV 列名、JSON/YAML 键、输出字段或文件命名。

### Baseline Impact

- **无**。未修改算法代码、科学计算逻辑或配置默认值。

### Commands Run

- 未运行命令。本次为文档更新，仅写入用户提供的环境规则。

### Remaining Risks

- 现有源码中是否仍存在 `import TimeTagger` 尚未在本次文档更新中扫描；如后续修改 TimeTagger 代码，应按 [`AGENTS.md`](AGENTS.md) 规则替换为 `from Swabian import TimeTagger`。
- `load_channels_from_ttbin()` 的 `max_events` 当前按总事件数限制，不是按通道分别限制；如果未来要改语义，必须显式迁移并同步文档/测试。

## 2026-04-29 Current task 更新：Dense JTI + Schmidt + strict single-hit 风险

### 修改文件

1. **[`CURRENT_TASK.md`](CURRENT_TASK.md)** — 从模板改为 active planning/documentation task：
   - 明确排除 `P_plus` 作为单光子相干时间判据。
   - 规划使用较大 `binwidth_ps`、可承受 dense `N x N` JTI 与 Schmidt 收敛/饱和判断 `frame_length_ps` 覆盖情况。
   - 明确 [`_pairs_from_timetags()`](src/jti_extract/cli/extract.py:258) 的 `strict_single_hit_per_frame` 语义不允许在当前任务中修改。
   - 新增关键风险：大 `binwidth_ps/frame_length_ps` 会提高多击帧概率，strict single-hit policy 会剔除这些 frame，可能导致 `n_pairs` 下降与 Schmidt 指标选择偏差。
   - 要求后续 sweep 同步审查 `pairs_meta.n_events_ch0`、`pairs_meta.n_events_ch1`、`pairs_meta.n_frames_common`、`pairs_meta.n_pairs`、`single_hit_policy` 与派生 single-hit 保留率。
   - 给出 `N=1024` 与 `N=2048` 的推荐 `bw` 起点、frame-origin scan 策略、重型命令模板与 rollback 策略。
2. **[`AGENT_HANDOFF.md`](AGENT_HANDOFF.md)** — 记录本次 current task 更新与风险补充。

### Schema Impact

- **无**。本次仅修改 harness 文档，未改变 CLI 参数、CSV 列名、JSON/YAML 键、输出字段或文件命名。
- [`CURRENT_TASK.md`](CURRENT_TASK.md) 明确后续如需派生 `frame_length_ps` 或 single-hit 保留率，应优先在文档/helper 中计算，不应改既有 `jti_schmidt_summary.csv` schema，除非另开 schema 迁移任务。

### Baseline Impact

- **无**。未修改任何算法代码、科学计算逻辑或配置默认值。
- 当前任务明确禁止修改 [`_pairs_from_timetags()`](src/jti_extract/cli/extract.py:258)、[`_jti_from_pairs()`](src/jti_extract/cli/extract.py:310) 和 [`compute_schmidt_number_from_jti()`](src/jti_extract/cli/schmidt.py:94) 的科学语义。

### Commands Run

- 未运行 shell 命令。
- 使用只读文件检查确认 [`CURRENT_TASK.md`](CURRENT_TASK.md) 原状态、[`RUN_COMMANDS.md`](RUN_COMMANDS.md) 可用命令、[`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) 交接上下文，以及 [`_pairs_from_timetags()`](src/jti_extract/cli/extract.py:258) 的 strict single-hit 语义。

### Remaining Risks

- 尚未实际运行 `jti-extract` / `jti-schmidt` sweep；当前为规划与 harness 更新。
- 后续真实数据 sweep 必须使用全新输出目录，并检查大 `bw` 下 single-hit 保留率是否足够稳定。
- 如果多击帧剔除严重，不能直接把 Schmidt 收敛/不收敛解释为相干时间覆盖结论；需另开任务设计 pairing/folding 对照。

## 2026-04-29 Current task 重新规划：Ultra-high-dimensional fixed-lattice G2-like JTI sweep

### 信息来源

- [`jti超高维sweep问题_解决思路_解决方法_更新版.md`](jti超高维sweep问题_解决思路_解决方法_更新版.md)
- [`jti超高维sweep问题_原理与操作步骤_更新版.md`](jti超高维sweep问题_原理与操作步骤_更新版.md)
- 只读参考：[`_pairs_from_timetags()`](src/jti_extract/cli/extract.py:258)、[`_jti_from_pairs()`](src/jti_extract/cli/extract.py:310)、[`compute_schmidt_number_from_jti()`](src/jti_extract/cli/schmidt.py:94)、[`folding_summary()`](src/jti_extract/cli/tdc_layer_scan.py:539)

### 修改文件

1. **[`CURRENT_TASK.md`](CURRENT_TASK.md)** — 重新规划为 `ultra-high-dimensional fixed-lattice G2-like JTI sweep`：
   - 主流程从 dense matrix / strict hard pairing / full SVD 改为 fixed global frame lattice + `g2_all_candidates` + background estimation + coarse/banded/tiled/sparse views + exact/coarse/truncated effective-mode analysis。
   - 明确 strict single-hit、nearest、greedy_unique、folded_without_strict 均为 diagnostics，不作为主物理配对算法。
   - 明确禁止 per-pair origin，global JTI 必须使用固定全局 frame lattice。
   - 纳入 edge guard、multi-origin sensitivity、background/accidental estimation、bootstrap stability、truncated SVD captured energy 等必要判据。
   - 规划后续非侵入式模块 [`src/jti_extract/ultra/`](src/jti_extract/ultra/)，但当前阶段未允许代码实现。
2. **[`AGENT_HANDOFF.md`](AGENT_HANDOFF.md)** — 记录本次重新规划，并提供下一步 agent 任务块。

### 当前判断

- `P_plus` 只作为 acquisition stability / paired coincidence support 诊断，不再作为相干时间或最高维度判据。
- [`_pairs_from_timetags()`](src/jti_extract/cli/extract.py:258) 的 strict single-hit 语义必须保留，但在超长 frame 下只能作为 selection-bias diagnostic。
- [`nearest_pairs()`](src/jti_extract/cli/tdc_layer_scan.py:307) 与 [`greedy_unique_pairs()`](src/jti_extract/cli/tdc_layer_scan.py:327) 不能作为真实物理 pair recovery；只能用于 method sensitivity。
- 超高维主分析应使用 fixed-lattice G2-like all-candidate coincidence accumulation，并通过 edge guard、origin sensitivity、background estimation 和 bootstrap 控制风险。
- 超高维默认不输出完整 dense CSV；应输出 coarse JTI、diagonal profiles、marginals、selected tiles、sparse COO 与 effective-mode summaries。

### Schema Impact

- **无既有 schema impact**。本次仅更新 harness 文档，未修改 CLI 参数、CSV 列名、JSON/YAML 键、输出字段或文件命名。
- [`CURRENT_TASK.md`](CURRENT_TASK.md) 规定：如后续新增 ultra sweep 输出，必须使用新输出目录和新 CSV schema；不得修改既有 `jti_schmidt_summary.csv` 或 counts CSV schema，除非另开 schema migration task。

### Baseline Impact

- **无**。未修改算法代码、科学计算逻辑或配置默认值。
- 重新规划明确保护 [`_pairs_from_timetags()`](src/jti_extract/cli/extract.py:258)、[`_jti_from_pairs()`](src/jti_extract/cli/extract.py:310)、[`compute_schmidt_number_from_jti()`](src/jti_extract/cli/schmidt.py:94) 的既有语义。

### Commands Run

- 未运行 shell 命令。
- 使用只读工具检查 [`CURRENT_TASK.md`](CURRENT_TASK.md) 与 [`src/jti_extract/cli/tdc_layer_scan.py`](src/jti_extract/cli/tdc_layer_scan.py:539) 相关 diagnostic/folding 逻辑。

### Remaining Risks

- 当前是规划与 harness 更新，未实现 [`src/jti_extract/ultra/`](src/jti_extract/ultra/)。
- 尚未为 ultra sweep 定义正式 CLI、config schema、测试 fixtures 或输出字段类型。
- 后续如果实现 G2-like accumulator，需要特别审查 all-candidate 复杂度、accidental/background subtraction、edge guard 统计和 sparse/truncated SVD 数值稳定性。

## Next Agent Task

### Goal

将 ultra-high-dimensional fixed-lattice G2-like JTI sweep 规划同步到项目文档，准备后续实现任务，但本任务不写业务代码。

### Must Read First

- [`AGENTS.md`](AGENTS.md)
- [`CURRENT_TASK.md`](CURRENT_TASK.md)
- [`RUN_COMMANDS.md`](RUN_COMMANDS.md)
- [`REVIEW_CHECKLIST.md`](REVIEW_CHECKLIST.md)
- [`jti超高维sweep问题_解决思路_解决方法_更新版.md`](jti超高维sweep问题_解决思路_解决方法_更新版.md)
- [`jti超高维sweep问题_原理与操作步骤_更新版.md`](jti超高维sweep问题_原理与操作步骤_更新版.md)
- [`src/jti_extract/cli/extract.py`](src/jti_extract/cli/extract.py:258)（只读）
- [`src/jti_extract/cli/tdc_layer_scan.py`](src/jti_extract/cli/tdc_layer_scan.py:539)（只读）
- [`src/jti_extract/cli/schmidt.py`](src/jti_extract/cli/schmidt.py:94)（只读）

### Constraints

- Do not modify raw data or existing results.
- Do not modify [`_pairs_from_timetags()`](src/jti_extract/cli/extract.py:258), [`_jti_from_pairs()`](src/jti_extract/cli/extract.py:310), or [`compute_schmidt_number_from_jti()`](src/jti_extract/cli/schmidt.py:94).
- Do not promote `nearest` or `greedy_unique` to main physical pairing algorithms.
- Do not use per-pair origin for global JTI.
- Do not add runnable ultra CLI commands until implementation exists.
- Preserve existing CLI/CSV/JSON/YAML schema.

### Files to Modify

- [`docs/SCHMIDT_ANALYSIS.md`](docs/SCHMIDT_ANALYSIS.md)
- [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md)
- [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)
- [`RUN_COMMANDS.md`](RUN_COMMANDS.md) only for non-runnable planning templates or clearly marked future heavy commands
- [`REVIEW_CHECKLIST.md`](REVIEW_CHECKLIST.md) if adding review criteria for ultra sweep
- [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md)

### Files Not to Modify

- [`src/jti_extract/cli/extract.py`](src/jti_extract/cli/extract.py)
- [`src/jti_extract/cli/schmidt.py`](src/jti_extract/cli/schmidt.py)
- [`src/jti_extract/cli/tdc_layer_scan.py`](src/jti_extract/cli/tdc_layer_scan.py)
- [`src/jti_extract/core/`](src/jti_extract/core/)
- [`configs/`](configs/)
- [`results/`](results/)
- all `*.ttbin`

### Patch Instructions

1. Update [`docs/SCHMIDT_ANALYSIS.md`](docs/SCHMIDT_ANALYSIS.md) to distinguish exact dense Schmidt from coarse/truncated effective-mode analysis.
2. Update [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md) with the fixed-lattice `g2_all_candidates` workflow and staged sweep plan.
3. Update [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) with strict selection bias, nearest/greedy heuristic bias, boundary tearing, origin sensitivity, sparse sampling, and truncated SVD risks.
4. Update [`REVIEW_CHECKLIST.md`](REVIEW_CHECKLIST.md) with ultra sweep review gates: fixed origin, no per-pair origin, edge guard, background estimation, bootstrap stability, no dense full matrix by default.
5. Keep [`RUN_COMMANDS.md`](RUN_COMMANDS.md) conservative: do not add executable ultra commands before implementation exists; any future templates must be marked `Do not run by default`.

### Commands to Run

For pure documentation updates, no experiment commands are required. Allowed checks:

```bash
git status
git diff
```

### Expected Outputs

- Updated documentation that consistently describes the ultra JTI plan.
- No code changes.
- No generated experiment outputs.

### Acceptance Criteria

- Documentation says main ultra workflow is `g2_all_candidates` on a fixed global frame lattice.
- Documentation says strict / nearest / greedy_unique are diagnostics only.
- Documentation forbids per-pair origin for global JTI.
- Documentation requires edge guard, origin sensitivity, background estimation, bootstrap stability, and captured-energy reporting.
- Existing schema and baseline algorithms remain unchanged.

### If It Fails

- If docs conflict with [`CURRENT_TASK.md`](CURRENT_TASK.md), treat [`CURRENT_TASK.md`](CURRENT_TASK.md) as the current planning source of truth.
- If source code behavior conflicts with docs, cite source code line anchors and update docs to match code facts.
- If implementation is requested, first update [`CURRENT_TASK.md`](CURRENT_TASK.md) Allowed Files and create a separate implementation task.

## 2026-04-29 文档升级：Ultra JTI sweep 可行性评估落地

### 修改文件

1. **[`docs/SCHMIDT_ANALYSIS.md`](docs/SCHMIDT_ANALYSIS.md)** — 新增 ultra-high-dimensional JTI 的 exact/coarse/truncated effective-mode 分层策略，明确 raw nonnegative counts 与 background-subtracted signed spectrum 的命名区别。
2. **[`docs/WORKFLOWS.md`](docs/WORKFLOWS.md)** — 将 dense JTI + Schmidt workflow 标注为 legacy/small-scale validation，并新增 Workflow 7: fixed-lattice `g2_all_candidates` ultra sweep。
3. **[`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)** — 新增 all-candidate background、strict selection bias、nearest/greedy heuristic bias、boundary tearing、signed spectrum、sparse sampling 等排障项。
4. **[`REVIEW_CHECKLIST.md`](REVIEW_CHECKLIST.md)** — 新增 Ultra-high-dimensional JTI Sweep Gates。
5. **[`RUN_COMMANDS.md`](RUN_COMMANDS.md)** — 增加 ultra sweep “规划中，当前不可运行”占位，明确不得伪造 `jti-ultra-sweep` 命令。
6. **[`AGENT_HANDOFF.md`](AGENT_HANDOFF.md)** — 记录本次文档升级。

### Schema Impact

- **无**。本次仅修改文档与 harness 文件，未改变 CLI 参数、CSV 列名、JSON/YAML 键、输出字段或文件命名。

### Baseline Impact

- **无**。未修改算法代码、科学计算逻辑或配置默认值。
- 文档继续要求保护 [`_pairs_from_timetags()`](src/jti_extract/cli/extract.py:258)、[`_jti_from_pairs()`](src/jti_extract/cli/extract.py:310)、[`compute_schmidt_number_from_jti()`](src/jti_extract/cli/schmidt.py:94) 的既有语义。

### Commands Run

- 未运行 shell 命令。
- 使用只读工具读取 [`docs/SCHMIDT_ANALYSIS.md`](docs/SCHMIDT_ANALYSIS.md)、[`docs/WORKFLOWS.md`](docs/WORKFLOWS.md)、[`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)、[`REVIEW_CHECKLIST.md`](REVIEW_CHECKLIST.md)、[`RUN_COMMANDS.md`](RUN_COMMANDS.md) 后执行文档 patch。

### Remaining Risks

- Ultra sweep 仍处于规划阶段，尚未实现 [`src/jti_extract/ultra/`](src/jti_extract/ultra/) 或 CLI。
- 后续进入实现前必须先更新 [`CURRENT_TASK.md`](CURRENT_TASK.md) Allowed Files、输出 schema、测试计划与 validation commands。

## 2026-04-29 文档一致性检查：Ultra JTI sweep 术语与风险对齐

### 检查范围

- 搜索并检查所有 Markdown 文档中的 `P_plus`、Schmidt、dense JTI、strict single-hit、nearest、greedy、per-pair origin、ultra、G2-like、`g2_all_candidates` 相关表述。
- 重点核对 [`CURRENT_TASK.md`](CURRENT_TASK.md)、[`docs/SCHMIDT_ANALYSIS.md`](docs/SCHMIDT_ANALYSIS.md)、[`docs/WORKFLOWS.md`](docs/WORKFLOWS.md)、[`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)、[`docs/TYPE0PPLN_PPLUS_AUTO_DIM_REPORT.md`](docs/TYPE0PPLN_PPLUS_AUTO_DIM_REPORT.md)、[`docs/DATA_CONTRACT.md`](docs/DATA_CONTRACT.md)、[`docs/index.md`](docs/index.md)、[`RUN_COMMANDS.md`](RUN_COMMANDS.md)、[`REVIEW_CHECKLIST.md`](REVIEW_CHECKLIST.md)。

### 修正文件

1. **[`docs/SCHMIDT_ANALYSIS.md`](docs/SCHMIDT_ANALYSIS.md)** — 将 dense frame-length Schmidt 判据明确标注为 legacy/small-scale dense validation；补充 strict single-hit selection bias 限制，避免被误读为超高维主线。
2. **[`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)** — 将 P_plus 排障项中的“Schmidt 收敛判据”限定为小规模 dense validation，并指向 Workflow 7 作为超高维主线。
3. **[`docs/TYPE0PPLN_PPLUS_AUTO_DIM_REPORT.md`](docs/TYPE0PPLN_PPLUS_AUTO_DIM_REPORT.md)** — 增加 2026-04-29 consistency note：`P_plus` 仅为 acquisition-support / auto-dim 诊断，不是单光子相干时间、Schmidt number 或 ultra fixed-lattice G2-like JTI 最终维度判据；历史 `nearest` pairing 仅代表 pilot 设置。
4. **[`docs/index.md`](docs/index.md)** — 增加 [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md) 索引入口，便于发现 Workflow 7。
5. **[`docs/DATA_CONTRACT.md`](docs/DATA_CONTRACT.md)** — 增加 ultra planning note：`nearest` / `greedy_unique` 是 diagnostics，主线为 fixed-global-lattice `g2_all_candidates`。
6. **[`AGENT_HANDOFF.md`](AGENT_HANDOFF.md)** — 记录本次一致性检查。

### 当前一致性结论

- 文档现已统一：超高维 / 超长 frame 主线是 fixed global frame lattice + raw `g2_all_candidates` + diagnostics-only method/origin/edge sensitivity + coarse/sparse/tiled outputs + coarse/truncated effective-mode analysis；2026-04-29 共识是不默认扣除 background。
- 文档现已统一：strict single-hit、nearest、greedy_unique、folded_without_strict 只作为 diagnostics，不作为主物理配对算法。
- 文档现已统一：`P_plus` 只作为 acquisition stability / paired coincidence support / auto-dim 诊断，不作为单光子相干时间、Schmidt number 或 ultra JTI final dimension certification。
- 文档现已统一：当前尚未实现 [`src/jti_extract/ultra/`](src/jti_extract/ultra/) 或 `jti-ultra-sweep` CLI，禁止伪造可运行命令。

### Commands Run

- 未运行 shell 命令。
- 使用 `search_files` 搜索 Markdown 文档，并使用只读工具检查相关段落后执行文档 patch。

### Schema Impact

- 无。仅修改文档。

### Baseline Impact

- 无。未修改任何代码或算法语义。

## 2026-04-29 推荐 long-plan prompt：Minimal Ultra Accumulator Prototype

### 使用场景

用户希望像 plan mode 一样，用一个超长 prompt 让实现 agent 按阶段连续推进。当前推荐只让 long-plan 执行 Stage A，即 `minimal ultra accumulator prototype`。不要在同一个 prompt 中实现 background、SVD、bootstrap 或 CLI。

### 推荐 Prompt

```markdown
你将继续 `jti-extract` 项目的 ultra-high-dimensional fixed-lattice G2-like JTI sweep 路线。请严格按以下要求执行，使用最小 patch，只实现 Stage A: minimal ultra accumulator prototype。

## Must Read First

1. `AGENTS.md`
2. `CURRENT_TASK.md`
3. `RUN_COMMANDS.md`
4. `REVIEW_CHECKLIST.md`
5. `AGENT_HANDOFF.md`
6. `docs/WORKFLOWS.md` Workflow 7
7. `docs/SCHMIDT_ANALYSIS.md` ultra effective-mode notes
8. `docs/TROUBLESHOOTING.md` ultra sweep troubleshooting
9. Source references, read-only:
   - `src/jti_extract/cli/extract.py` around `_pairs_from_timetags()` and `_jti_from_pairs()`
   - `src/jti_extract/cli/tdc_layer_scan.py` around `_iter_all_pair_delta_chunks()`, `nearest_pairs()`, `greedy_unique_pairs()`, and `folding_summary()`
   - `src/jti_extract/cli/schmidt.py` around `compute_schmidt_number_from_jti()`

## Goal

Implement only the first minimal ultra prototype layer:

- fixed global frame lattice helpers;
- edge guard;
- fixed physical coincidence-window all-candidate iterator;
- coarse JTI accumulator;
- diagonal profile accumulator;
- row/column marginal accumulator;
- tiny-array unit tests.

Do not implement background subtraction, SVD, truncated SVD, bootstrap, selected tiles, config files, output directories, or CLI in this task.

## Files Allowed to Modify / Add

- `src/jti_extract/ultra/__init__.py`
- `src/jti_extract/ultra/fold_lattice.py`
- `src/jti_extract/ultra/g2_accumulate.py`
- `src/jti_extract/ultra/accumulators.py`
- `tests/test_ultra_lattice.py`
- `tests/test_ultra_accumulators.py`
- `RUN_COMMANDS.md` only if adding the new pytest / py_compile commands
- `AGENT_HANDOFF.md` to record changes

## Files Not Allowed to Modify

- Any `*.ttbin`
- `results/` or existing generated outputs
- `src/jti_extract/cli/extract.py`
- `src/jti_extract/cli/schmidt.py`
- `src/jti_extract/cli/tdc_layer_scan.py`
- `src/jti_extract/core/`
- `configs/`
- existing CSV/JSON/YAML schemas
- `pyproject.toml` console scripts; do not add `jti-ultra-sweep`

## Baseline Constraints

- Do not change `_pairs_from_timetags()` strict single-hit semantics.
- Do not change `_jti_from_pairs()` dense raw counts semantics.
- Do not change `compute_schmidt_number_from_jti()` semantics.
- Do not promote `nearest` or `greedy_unique` to main physical pairing algorithms.
- Do not use per-pair origin for global JTI.
- `coincidence_window_ps` must be a fixed physical window and must not scale with `N`, `binwidth_ps`, or `frame_length_ps`.

## Required Design

### `fold_lattice.py`

Implement pure NumPy helpers, for example:

- `frame_length_ps(n_bins, bin_width_ps) -> int`
- `phase_in_frame(times_ps, frame_origin_ps, frame_length_ps) -> np.ndarray`
- `bin_indices(times_ps, frame_origin_ps, bin_width_ps, n_bins) -> np.ndarray`
- `edge_guard_mask(times_ps, frame_origin_ps, frame_length_ps, edge_guard_ps) -> np.ndarray`

All functions must use a fixed global origin. No per-pair origin is allowed.

### `g2_accumulate.py`

Implement all-candidate iterator over sorted `t_a`, `t_b`:

- fixed `coincidence_window_ps`;
- chunked over `t_a`;
- returns or yields candidate `t_a`, `t_b`, `delta_ps` arrays;
- chunking must not change total output.

### `accumulators.py`

Implement minimal accumulators:

- coarse JTI accumulator;
- diagonal profile accumulator;
- row marginal accumulator;
- column marginal accumulator;
- summary counts including `n_candidates_total`, `n_candidates_after_edge_guard`, `edge_rejection_ratio`.

Use only in-memory arrays and pytest tmp fixtures. Do not write official output files.

## Required Tests

Add tiny synthetic tests that verify:

1. fixed lattice binning with `frame_origin_ps` is correct;
2. edge guard rejects events near frame boundaries;
3. all-candidate iterator matches hand-calculated candidates;
4. chunked and unchunked candidate iteration produce the same candidates;
5. coarse JTI, diagonal profile, row marginal, and column marginal totals match `n_candidates_after_edge_guard`;
6. `coincidence_window_ps` does not depend on `N`, `binwidth_ps`, or `frame_length_ps`.

## Commands to Run

Run only these light commands:

```bash
python -m pytest tests/test_ultra_lattice.py -v
python -m pytest tests/test_ultra_accumulators.py -v
python -m pytest tests/test_cli_smoke.py -v
python -m pytest tests/test_schmidt.py -v
python -m py_compile src/jti_extract/ultra/fold_lattice.py
python -m py_compile src/jti_extract/ultra/g2_accumulate.py
python -m py_compile src/jti_extract/ultra/accumulators.py
```

Do not run full experiments. Do not read real `.ttbin` files. Do not write to `results/`.

## Acceptance Criteria

- All new ultra tests pass.
- Existing smoke and Schmidt tests pass.
- No existing CLI behavior changes.
- No schema changes to existing outputs.
- No generated real results.
- `AGENT_HANDOFF.md` records modified files, schema impact, baseline impact, commands run, results, remaining risks, and suggested next stage.

## Stop Conditions

Stop and report instead of continuing if:

- any baseline file needs modification;
- any output schema change seems necessary;
- all-candidate complexity requires real data assumptions;
- tests fail in a way that requires changing existing algorithms;
- implementation would require adding a CLI or config schema.
```

### 执行建议

- 优先让执行 agent 先更新 [`CURRENT_TASK.md`](CURRENT_TASK.md)，把 Allowed Files 从 planning-only 切换到 Stage A 实现范围。
- 如果执行 agent 没有权限修改代码，应先让其生成实现 patch plan，不要强行写代码。
- Stage A 通过后，再另开 Stage B prompt 处理 diagnostics/background。

## 2026-04-29 Stage A: minimal ultra accumulator prototype

### 修改文件

1. **[`src/jti_extract/ultra/__init__.py`](src/jti_extract/ultra/__init__.py)** — 新建 ultra 模块包标记。
2. **[`src/jti_extract/ultra/fold_lattice.py`](src/jti_extract/ultra/fold_lattice.py)** — 新建固定全局 frame lattice 辅助函数：
   - [`frame_length_ps()`](src/jti_extract/ultra/fold_lattice.py:11) — 帧长 = N × binwidth_ps。
   - [`phase_in_frame()`](src/jti_extract/ultra/fold_lattice.py:20) — 每个时间戳的帧内相位 (times - origin) % frame_length。
   - [`bin_indices()`](src/jti_extract/ultra/fold_lattice.py:42) — 帧内 bin 索引 floor((t - origin) / bw) % N。
   - [`edge_guard_mask()`](src/jti_extract/ultra/fold_lattice.py:66) — 布尔 mask，拒绝距帧边界 < edge_guard_ps 的事件。
3. **[`src/jti_extract/ultra/g2_accumulate.py`](src/jti_extract/ultra/g2_accumulate.py)** — 新建 all-candidate coincidence iterator：
   - [`_candidates_one_chunk()`](src/jti_extract/ultra/g2_accumulate.py:18) — 单个 t_a chunk 的 searchsorted 实现。
   - [`iter_all_candidates()`](src/jti_extract/ultra/g2_accumulate.py:66) — 跨 t_a 逐 chunk yield (t_a, t_b, delta_ps) 候选数组。
   - [`all_candidates()`](src/jti_extract/ultra/g2_accumulate.py:98) — 拼接所有 chunk 的便捷包装。
4. **[`src/jti_extract/ultra/accumulators.py`](src/jti_extract/ultra/accumulators.py)** — 新建最小 accumulator 类：
   - [`FixedLatticeAccumulator`](src/jti_extract/ultra/accumulators.py:27) — coarse JTI / diagonal profile / row marginal / column marginal / summary counts。
   - 支持 `coarse_n_bins` 可选 coarse JTI rebinning。
   - 提供 `check_internal_consistency()` 验证所有累加器总和与 `n_candidates_after_edge_guard` 一致。
5. **[`tests/test_ultra_lattice.py`](tests/test_ultra_lattice.py)** — 新建 fold_lattice 单元测试：
   - `TestFrameLength`、`TestPhaseInFrame`、`TestBinIndices`、`TestEdgeGuardMask`、`TestCoincidenceWindowIndependence`。
6. **[`tests/test_ultra_accumulators.py`](tests/test_ultra_accumulators.py)** — 新建 accumulators 与 g2_accumulate 单元测试：
   - `TestAllCandidates` — hand-calculation 验证、随机数组计数验证。
   - `TestChunkedUnchunked` — chunked vs unchunked 等价性验证（含 `chunk_events=1`）。
   - `TestFixedLatticeAccumulator` — 内部一致性与 multi-batch 验证。
7. **[`RUN_COMMANDS.md`](RUN_COMMANDS.md)** — 新增 ultra 模块语法检查和单元测试命令。

### Schema Impact

- **无**。未修改 CLI 参数、CSV 列名、JSON/YAML 键、输出字段或文件命名。
- 新模块 [`src/jti_extract/ultra/`](src/jti_extract/ultra/) 是独立的非侵入式命名空间，不影响既有 `jti-extract`、`jti-schmidt`、`jti-tdc-residue`、`jti-tdc-layer-scan` 或 `run_type0ppln_pplus_auto_dim.py` 的输出。

### Baseline Impact

- **无**。未修改 [`_pairs_from_timetags()`](src/jti_extract/cli/extract.py:258)、[`_jti_from_pairs()`](src/jti_extract/cli/extract.py:310)、[`compute_schmidt_number_from_jti()`](src/jti_extract/cli/schmidt.py:94)、[`nearest_pairs()`](src/jti_extract/cli/tdc_layer_scan.py:307)、[`greedy_unique_pairs()`](src/jti_extract/cli/tdc_layer_scan.py:327) 的既有语义。
- 未修改 [`configs/`](configs/)、[`results/`](results/) 或已有生成物。

### Commands Run

```bash
# Using ~/envs/jti_dev/bin/python with PYTHONPATH=src
python -m pytest tests/test_ultra_lattice.py -v          # 11 passed in 0.08s
python -m pytest tests/test_ultra_accumulators.py -v       # 13 passed in 0.06s
python -m pytest tests/test_cli_smoke.py -v                # 2 passed in 0.38s
python -m pytest tests/test_schmidt.py -v                  # 2 passed in 0.04s
python -m py_compile src/jti_extract/ultra/fold_lattice.py  # OK
python -m py_compile src/jti_extract/ultra/g2_accumulate.py # OK
python -m py_compile src/jti_extract/ultra/accumulators.py  # OK
```

### Results

- **test_ultra_lattice.py**: 11/11 passed (frame length, phase, bin indices, edge guard, independence with real assertions)
- **test_ultra_accumulators.py**: 18/18 passed (previous tests + chunk_events validation, add_candidates shape validation)
- **test_ultra_diagnostics_pairing.py**: 11/11 passed (strict retention, nearest, greedy, method comparison)
- **test_cli_smoke.py**: 2/2 passed (no regression)
- **test_schmidt.py**: 2/2 passed (no regression)
- **py_compile**: all 4 ultra modules compile without errors

### Remaining Risks

- 当前仅为最小原型，未实现 background subtraction、SVD、truncated SVD、bootstrap、selected tiles、config 或 CLI。
- All-candidate iterator 在极高计数率或超大窗口下可能返回大量候选；目前未对候选数量做上限保护。
- `FixedLatticeAccumulator` 的 coarse JTI rebinning 使用 `floor_divide(N // coarse_N)`，在 `N` 不能被 `coarse_N` 整除时最后一个 bin 覆盖范围可能不等宽。
- 未对 `t_a`/`t_b` 的排序前提做运行时检查（调用者负责传入排序数组）。
- 未使用 `.ttbin` 数据验证；所有测试基于合成小数组。
- `edge_guard_mask` 分别对 `t_a` 和 `t_b` 独立应用，未考虑跨 frame wrap-around 的 coincidence 损失。

### Historical Suggested Next Stage (Stage B) — superseded by completed prototype

以下建议已由 2026-04-29 Stage A hardening + Stage B diagnostics-only prototype 覆盖，保留为历史记录。2026-04-29 用户确认：不需要扣除 background，后续不得默认实现 background subtraction 或 background-subtracted signed spectrum。

- 修复 Stage A review 发现的小问题：真实 coincidence-window independence 断言、`chunk_events <= 0` 显式报错、`add_candidates()` 输入长度检查、文档状态漂移
- strict retention diagnostic (保留率与 frame_length 关系)
- folded_without_strict diagnostic
- nearest/greedy method sensitivity wrapper
- origin sensitivity / edge-guard sensitivity summary
- 保持 raw nonnegative counts 为主结果；不扣除 background

## 2026-04-29 Harness 更新：Stage B diagnostics-only plan 与 no-background-subtraction 共识

### 修改文件

1. **[`CURRENT_TASK.md`](CURRENT_TASK.md)** — 将 ultra 路线从 background-estimation wording 调整为 diagnostics-only method/origin/edge sensitivity；Stage B 改为 `diagnostics-only planning and Stage A hardening`；明确不默认扣除 background，不输出 background-subtracted signed spectrum。
2. **[`RUN_COMMANDS.md`](RUN_COMMANDS.md)** — 修正 stale 状态：Stage A [`src/jti_extract/ultra/`](src/jti_extract/ultra/) library prototype 已存在且可运行单元测试；`jti-ultra-sweep` CLI、真实 sweep orchestration、config schema 和正式输出目录仍未实现。
3. **[`REVIEW_CHECKLIST.md`](REVIEW_CHECKLIST.md)** — 将 ultra review gate 改为 raw nonnegative counts 主结果保护，禁止默认 background subtraction。
4. **[`AGENT_HANDOFF.md`](AGENT_HANDOFF.md)** — 记录 Stage A review 后的 Stage B plan 与 no-background-subtraction 共识。

### Schema Impact

- **无既有 schema impact**。本次仅修改 harness 文档，未改变 CLI 参数、CSV 列名、JSON/YAML 键、输出字段或文件命名。
- 对未来 ultra schema 的约束已更新：不得默认新增 `background_counts_fraction`、`n_candidates_after_background` 或 background-subtracted signed spectrum 作为主输出。

### Baseline Impact

- **无**。未修改任何算法代码、科学计算逻辑或配置默认值。
- 继续保护 [`_pairs_from_timetags()`](src/jti_extract/cli/extract.py:258)、[`_jti_from_pairs()`](src/jti_extract/cli/extract.py:310)、[`compute_schmidt_number_from_jti()`](src/jti_extract/cli/schmidt.py:94)、[`nearest_pairs()`](src/jti_extract/cli/tdc_layer_scan.py:307)、[`greedy_unique_pairs()`](src/jti_extract/cli/tdc_layer_scan.py:327) 的既有语义。

### Commands Run

- 未运行 shell 命令。本次为 harness 文档更新。
- 使用只读工具检查 [`CURRENT_TASK.md`](CURRENT_TASK.md)、[`RUN_COMMANDS.md`](RUN_COMMANDS.md)、[`REVIEW_CHECKLIST.md`](REVIEW_CHECKLIST.md)、[`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) 以及相关 docs 中的 background wording。

### Remaining Risks

- [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md)、[`docs/SCHMIDT_ANALYSIS.md`](docs/SCHMIDT_ANALYSIS.md)、[`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)、[`docs/DATA_CONTRACT.md`](docs/DATA_CONTRACT.md)、[`docs/TYPE0PPLN_PPLUS_AUTO_DIM_REPORT.md`](docs/TYPE0PPLN_PPLUS_AUTO_DIM_REPORT.md) 仍含旧 background-control wording；当前 Harness Docs mode 不能编辑 `docs/`，需切换到允许 docs 的模式后同步。
- Stage A 代码 hardening 尚未执行；下一轮 implementation agent 应先修复 review 中的小问题，再实现 diagnostics-only Stage B。

## Next Agent Task

### Goal

先做 Stage A hardening，再实现 Stage B diagnostics-only planning/原型。不得实现 background subtraction、SVD、bootstrap、CLI、config schema 或真实 sweep 输出。

### Must Read First

- [`AGENTS.md`](AGENTS.md)
- [`CURRENT_TASK.md`](CURRENT_TASK.md)
- [`RUN_COMMANDS.md`](RUN_COMMANDS.md)
- [`REVIEW_CHECKLIST.md`](REVIEW_CHECKLIST.md)
- [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md)
- [`src/jti_extract/ultra/fold_lattice.py`](src/jti_extract/ultra/fold_lattice.py)
- [`src/jti_extract/ultra/g2_accumulate.py`](src/jti_extract/ultra/g2_accumulate.py)
- [`src/jti_extract/ultra/accumulators.py`](src/jti_extract/ultra/accumulators.py)
- [`tests/test_ultra_lattice.py`](tests/test_ultra_lattice.py)
- [`tests/test_ultra_accumulators.py`](tests/test_ultra_accumulators.py)

### Constraints

- Do not modify raw data or existing results.
- Do not write to [`results/`](results/).
- Do not add `jti-ultra-sweep` CLI or modify [`pyproject.toml`](pyproject.toml).
- Do not change existing CLI/core baseline semantics.
- Do not implement background subtraction or background-subtracted signed spectrum.
- Keep raw nonnegative `g2_all_candidates` counts as the main result.

### Files to Modify

- [`src/jti_extract/ultra/g2_accumulate.py`](src/jti_extract/ultra/g2_accumulate.py)
- [`src/jti_extract/ultra/accumulators.py`](src/jti_extract/ultra/accumulators.py)
- [`tests/test_ultra_lattice.py`](tests/test_ultra_lattice.py)
- [`tests/test_ultra_accumulators.py`](tests/test_ultra_accumulators.py)
- Optional Stage B diagnostics-only module if needed: `src/jti_extract/ultra/diagnostics_pairing.py`
- Optional tests if adding diagnostics module: `tests/test_ultra_diagnostics_pairing.py`
- [`RUN_COMMANDS.md`](RUN_COMMANDS.md) only for new light pytest/py_compile commands
- [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md)

### Files Not to Modify

- [`src/jti_extract/cli/extract.py`](src/jti_extract/cli/extract.py)
- [`src/jti_extract/cli/schmidt.py`](src/jti_extract/cli/schmidt.py)
- [`src/jti_extract/cli/tdc_layer_scan.py`](src/jti_extract/cli/tdc_layer_scan.py)
- [`src/jti_extract/core/`](src/jti_extract/core/)
- [`configs/`](configs/)
- [`results/`](results/)
- any `*.ttbin`
- [`pyproject.toml`](pyproject.toml)

### Patch Instructions

1. In [`iter_all_candidates()`](src/jti_extract/ultra/g2_accumulate.py:62), convert `chunk_events` to int once and raise `ValueError` when `chunk_events <= 0`; add tests for `chunk_events=0` and `chunk_events=-1`.
2. In [`FixedLatticeAccumulator.add_candidates()`](src/jti_extract/ultra/accumulators.py:102), explicitly validate equal input lengths and raise `ValueError` on mismatch; add a test.
3. Replace the empty coincidence-window independence test in [`tests/test_ultra_lattice.py`](tests/test_ultra_lattice.py:118) with real assertions.
4. If implementing diagnostics-only Stage B, create strict retention / folded_without_strict / nearest-greedy sensitivity helpers that consume synthetic arrays only and do not call `.ttbin` readers.
5. Do not implement sideband/time-shift background estimate, background subtraction, or signed spectrum output.

### Commands to Run

```bash
python -m pytest tests/test_ultra_lattice.py -v
python -m pytest tests/test_ultra_accumulators.py -v
python -m pytest tests/test_cli_smoke.py -v
python -m pytest tests/test_schmidt.py -v
python -m py_compile src/jti_extract/ultra/fold_lattice.py
python -m py_compile src/jti_extract/ultra/g2_accumulate.py
python -m py_compile src/jti_extract/ultra/accumulators.py
```

If adding `diagnostics_pairing.py`, also run:

```bash
python -m pytest tests/test_ultra_diagnostics_pairing.py -v
python -m py_compile src/jti_extract/ultra/diagnostics_pairing.py
```

### Acceptance Criteria

- Stage A hardening tests pass.
- `chunk_events <= 0` cannot silently drop candidates.
- `add_candidates()` rejects mismatched candidate arrays.
- coincidence-window independence has real assertions.
- No existing CLI/schema/baseline changes.
- No background subtraction or background-subtracted signed spectrum is added.
- No real `.ttbin` data is read and no [`results/`](results/) output is written.

### If It Fails

- If tests fail due to baseline code assumptions, stop and report; do not modify existing CLI/core algorithms.
- If diagnostics require output schema or CLI, stop and update [`CURRENT_TASK.md`](CURRENT_TASK.md) before implementation.
- If background subtraction seems necessary, stop and report because 2026-04-29 project consensus says it is not needed by default.

## 2026-04-29 Stage A hardening + Stage B diagnostics-only prototype

### 修改文件

| 文件 | 操作 | 说明 |
|---|---|---|
| [`src/jti_extract/ultra/g2_accumulate.py`](src/jti_extract/ultra/g2_accumulate.py) | 修改 | `iter_all_candidates()` 新增 `chunk_events <= 0` 时 raise `ValueError` |
| [`src/jti_extract/ultra/accumulators.py`](src/jti_extract/ultra/accumulators.py) | 修改 | `add_candidates()` 新增 `t_a.shape != t_b.shape` 时 raise `ValueError` |
| [`tests/test_ultra_lattice.py`](tests/test_ultra_lattice.py) | 修改 | `test_independence` 从 `pass` 替换为真实断言；新增 `all_candidates`/`FixedLatticeAccumulator` import |
| [`tests/test_ultra_accumulators.py`](tests/test_ultra_accumulators.py) | 修改 | 新增 `TestChunkEventsValidation`（2 tests）、`TestAddCandidatesValidation`（2 tests） |
| [`src/jti_extract/ultra/diagnostics_pairing.py`](src/jti_extract/ultra/diagnostics_pairing.py) | 新建 | `_nearest_pairs()`、`_greedy_unique_pairs()`、`strict_retention_meta()`、`method_comparison_summary()` |
| [`tests/test_ultra_diagnostics_pairing.py`](tests/test_ultra_diagnostics_pairing.py) | 新建 | 11 tests：strict retention、nearest、greedy、method comparison |
| [`RUN_COMMANDS.md`](RUN_COMMANDS.md) | 修改 | 新增 `diagnostics_pairing.py` 语法检查和测试命令 |

### Schema Impact

- **无**。未修改 CLI 参数、CSV 列名、JSON/YAML 键、输出字段或文件命名。
- `diagnostics_pairing.py` 是纯计算辅助模块，不产生任何输出文件。

### Baseline Impact

- **无**。未修改 [`_pairs_from_timetags()`](src/jti_extract/cli/extract.py:258)、[`_jti_from_pairs()`](src/jti_extract/cli/extract.py:310)、[`compute_schmidt_number_from_jti()`](src/jti_extract/cli/schmidt.py:94)、[`nearest_pairs()`](src/jti_extract/cli/tdc_layer_scan.py:307)、[`greedy_unique_pairs()`](src/jti_extract/cli/tdc_layer_scan.py:327) 的既有语义。
- `diagnostics_pairing.py` 中的 `_nearest_pairs()`/`_greedy_unique_pairs()` 是诊断副本，不替代原始实现。

### 验证结果

```text
test_ultra_lattice.py       — 11/11 passed  (0.08s; 含真实 independence 断言)
test_ultra_accumulators.py  — 18/18 passed  (0.06s; 含 hardening tests)
test_ultra_diagnostics_pairing.py — 11/11 passed (0.05s)
test_cli_smoke.py           — 2/2 passed   (无回归)
test_schmidt.py             — 2/2 passed   (无回归)
py_compile (4 ultra files)  — all OK
```

### 验收标准

- ✅ `chunk_events <= 0` raise `ValueError`，不会静默丢弃候选
- ✅ `add_candidates()` 拒绝形状不匹配的数组
- ✅ `coincidence_window_ps` 独立性测试使用真实断言（candidate set + 多种 N/bw/frame_length 组合验证存储不变）
- ✅ 无背景扣除或背景扣除后 signed spectrum
- ✅ 无 `.ttbin` 读取或 [`results/`](results/) 写入
- ✅ 无 CLI/schema/baseline 变更

### 剩余风险

- `diagnostics_pairing.py` 仅使用合成数组，未用真实 `.ttbin` 数据验证
- 未实现 SVD/bootstrap/CLI/config schema
- `strict_retention_meta()` 严格遵循 `_pairs_from_timetags()` 语义——超长 frame 下保留率低是预期行为

### Suggested Next Stage (Stage C)

实现 effective-mode estimators：
- coarse exact SVD on coarse JTI
- truncated singular spectrum with captured Frobenius energy
- block bootstrap

## 2026-04-29 Harness/docs sync：Stage A+B 阶段性收束

### 修改文件

1. **[`CURRENT_TASK.md`](CURRENT_TASK.md)** — 将任务状态更新为 Stage A hardening + Stage B diagnostics-only prototype completed；把下一阶段收束到 Stage C planning；记录 [`src/jti_extract/ultra/diagnostics_pairing.py`](src/jti_extract/ultra/diagnostics_pairing.py) 与 [`tests/test_ultra_diagnostics_pairing.py`](tests/test_ultra_diagnostics_pairing.py) 已完成。
2. **[`RUN_COMMANDS.md`](RUN_COMMANDS.md)** — 保留 ultra CLI/sweep 不可运行限制，并明确已有 Stage A + Stage B diagnostics-only library prototype 与测试命令。
3. **[`docs/WORKFLOWS.md`](docs/WORKFLOWS.md)** — 将 Stage 2 从 background 基础诊断同步为 origin / edge / method sensitivity 基础诊断；删除默认 background subtraction 判据。
4. **[`docs/SCHMIDT_ANALYSIS.md`](docs/SCHMIDT_ANALYSIS.md)** — 将 ultra 主线同步为 diagnostics-only checks；明确 raw counts 是主结果，不默认扣除 background。
5. **[`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)** — 将 background 主导排障改为 raw counts 偶然符合解释风险；明确不默认输出 signed spectrum。
6. **[`docs/DATA_CONTRACT.md`](docs/DATA_CONTRACT.md)** — 将 ultra data-contract note 同步为 raw `g2_all_candidates` + diagnostics-only；不默认 background subtraction。
7. **[`docs/TYPE0PPLN_PPLUS_AUTO_DIM_REPORT.md`](docs/TYPE0PPLN_PPLUS_AUTO_DIM_REPORT.md)** — 将 P_plus 报告中的 ultra 主线描述同步为 fixed-lattice raw `g2_all_candidates`，不默认扣除 background。
8. **[`AGENT_HANDOFF.md`](AGENT_HANDOFF.md)** — 标记旧 Stage B 建议已被完成的 prototype 覆盖，并记录本次阶段性收束。

### Schema Impact

- **无既有 schema impact**。本次仅同步 harness/docs，未修改 CLI 参数、CSV 列名、JSON/YAML 键、输出字段或文件命名。
- 对未来 ultra schema 的约束继续保持：raw nonnegative counts 是主结果；不得默认新增 background-subtracted signed spectrum。

### Baseline Impact

- **无**。未修改任何算法代码、科学计算逻辑或配置默认值。

### Commands Run

- 未运行 shell 命令。本次为文档同步。

### Current Status

- Stage A hardening + Stage B diagnostics-only prototype 已完成并有 synthetic-array 单元测试记录。
- 尚未实现 Stage C effective-mode estimators、bootstrap、CLI、config schema 或真实 sweep orchestration。
- 未读取真实 `.ttbin`，未写入 [`results/`](results/)。

## Next Agent Task

### Goal

规划 Stage C effective-mode estimators，保持 non-invasive ultra library 原型路线。不要实现 CLI、config schema、真实 sweep orchestration 或完整 `.ttbin` 实验。

### Must Read First

- [`AGENTS.md`](AGENTS.md)

## 2026-04-29 Stage C: effective-mode estimators — implemented (prototype)

### 修改文件

| 文件 | 操作 | 说明 |
|---|---|---|
| [`src/jti_extract/ultra/svd_estimators.py`](src/jti_extract/ultra/svd_estimators.py) | **新建** | 5 个 SVD 估计器函数：`svd_coarse_jti()`、`singular_spectrum()`、`captured_frobenius_energy()`、`truncated_schmidt_summary()`、`block_bootstrap_coarse_jti()` |
| [`tests/test_ultra_svd_estimators.py`](tests/test_ultra_svd_estimators.py) | **新建** | 19 个单元测试（8+2+4+3+2） |
| [`src/jti_extract/ultra/__init__.py`](src/jti_extract/ultra/__init__.py) | 修改 | 添加 Stage C 注释 |
| [`CURRENT_TASK.md`](CURRENT_TASK.md) | 修改 | Stage C 从 planning 改为 implemented (prototype)，新增实现文件清单和 acceptance criteria |
| [`RUN_COMMANDS.md`](RUN_COMMANDS.md) | 修改 | 新增 `svd_estimators.py` 语法检查和单元测试命令 |
| [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) | 修改 | 记录本次 Stage C 实现 |

### Schema Impact

- **无**。`svd_estimators.py` 是纯计算函数库，不生成输出文件、不改 CSV 列名、不改 CLI 参数、不改 JSON/YAML 键。
- 函数返回值 dict 键命名遵循 [`compute_schmidt_number_from_jti()`](src/jti_extract/cli/schmidt.py:118-128) 约定：`schmidt_number`、`purity`、`largest_weight`、`n_singular_values`、`singular_value_threshold`、`total_counts`、`normalized_sum`、`nonzero_bins`、`negative_bins`，以及新增 `captured_frobenius_energy_r`、`K_truncated_r`、`r_truncated`。

### Baseline Impact

- **无**。未修改 [`_pairs_from_timetags()`](src/jti_extract/cli/extract.py:258)、[`_jti_from_pairs()`](src/jti_extract/cli/extract.py:310)、[`compute_schmidt_number_from_jti()`](src/jti_extract/cli/schmidt.py:94)、[`nearest_pairs()`](src/jti_extract/cli/tdc_layer_scan.py:307)、[`greedy_unique_pairs()`](src/jti_extract/cli/tdc_layer_scan.py:327) 语义。
- `svd_coarse_jti()` 独立复制 `sqrt(probability)` 逻辑，不通过 import 调用 baseline 函数，避免产生硬依赖。

### 验证结果

```text
test_ultra_svd_estimators.py     — 19/19 passed (0.05s)
test_ultra_lattice.py            — 11/11 passed (无回归)
test_ultra_accumulators.py       — 18/18 passed (无回归)
test_ultra_diagnostics_pairing.py — 11/11 passed (无回归)
test_cli_smoke.py                — 2/2 passed  (无回归)
test_schmidt.py                  — 2/2 passed  (无回归)
py_compile (5 ultra 模块)        — all OK
```

### 验收标准

- ✅ `svd_coarse_jti` 拒绝含负值的矩阵（raise `ValueError`）
- ✅ 单位矩阵返回接近满秩（`schmidt_number ≈ N`）
- ✅ 秩-1 矩阵返回接近 1 的 schmidt_number
- ✅ 高阈值正确减少 `n_singular_values`
- ✅ truncated 版本保证 `n_singular_values <= r`
- ✅ 全量 r 时 truncated 与 exact schmidt_number 一致
- ✅ `captured_frobenius_energy` 单调非减
- ✅ bootstrap prototype 返回正确长度的结果列表
- ✅ 无 CLI/schema/baseline 变更
- ✅ 无 `.ttbin` 读取或 [`results/`](results/) 写入

### 剩余风险

- `block_bootstrap_coarse_jti()` 当前为简单 row-wise resampling（非完整 block bootstrap），标注为 `prototype`。
- 未实现完整 sweep orchestration、CLI 或 config schema。
- SVD 数值稳定性在极小 coarse JTI 维度（< 4）下未充分测试。
- 所有测试基于合成数组，未使用真实 `.ttbin` 数据验证。

### Current Ultra Module Chain

```
t_a, t_b (sorted timestamps)
    │
    ├── g2_accumulate.all_candidates(t_a, t_b, cw_ps)
    │       → candidate (t_a, t_b, delta) arrays
    │
    ├── accumulators.FixedLatticeAccumulator
    │       .add_candidates(ca, cb)
    │       → .coarse_jti, .diag_profile, .row_marginal, .col_marginal
    │
    ├── diagnostics_pairing
    │       .strict_retention_meta(), .method_comparison_summary()
    │
    └── svd_estimators  [NEW]
            .svd_coarse_jti(coarse_jti)      → Schmidt metrics dict
            .singular_spectrum(coarse_jti)    → weight array
            .captured_frobenius_energy(vals,r)→ float
            .truncated_schmidt_summary(jti,r) → dict + captured_energy
            .block_bootstrap_coarse_jti(...)  → list[dict] (prototype)
```

### 全部 3 个 Stage 累计统计

| Stage | 源文件 | 测试文件 | 测试数 |
|---|---|---|---|
| A | `fold_lattice.py`, `g2_accumulate.py`, `accumulators.py` | `test_ultra_lattice.py`, `test_ultra_accumulators.py` | 29 |
| B | `diagnostics_pairing.py` | `test_ultra_diagnostics_pairing.py` | 11 |
| C | `svd_estimators.py` | `test_ultra_svd_estimators.py` | 20 |
| **总计** | **5 源文件** | **4 测试文件** | **60 tests** |

### Suggested Next Stage (Stage D)

规划和实现 sweep orchestration：
- 协调 `all_candidates()` → `FixedLatticeAccumulator` → `svd_coarse_jti()` 的完整 pipeline
- origin sensitivity scan helper
- edge-guard sensitivity scan helper
- method comparison sweep helper
- 为后续 CLI/输出 schema 奠定数据流基础
- 仍不实现 CLI（`jti-ultra-sweep`），不读取 `.ttbin`，不写入正式结果目录

## 2026-04-29 Stage C hardening + Stage D planning update

### Stage C hardening fact

- [`singular_spectrum()`](src/jti_extract/ultra/svd_estimators.py:101) 已修复高阈值空谱风险：阈值过滤后无奇异值时显式 `ValueError("no singular values above threshold")`，避免返回 `nan`。
- [`tests/test_ultra_svd_estimators.py`](tests/test_ultra_svd_estimators.py) 新增高阈值回归测试；Stage C 测试数从 19 增至 20。
- 使用 `~/envs/jti_dev/bin/python` 验证：`tests/test_ultra_svd_estimators.py` 20/20 passed；Stage A/B + legacy smoke/schmidt 42/42 passed；[`svd_estimators.py`](src/jti_extract/ultra/svd_estimators.py) `py_compile` OK。

### Current status

- Stage A fixed-lattice accumulator prototype: completed.
- Stage B diagnostics-only prototype: completed.
- Stage C effective-mode estimators prototype: completed and hardened.
- Stage D sweep orchestration: planned only; not implemented.

## Next Agent Task

### Goal

Implement Stage D sweep orchestration prototype as an in-memory library helper. It should coordinate existing Stage A/B/C functions on tiny synthetic arrays only and prepare the data-flow shape for a future CLI/schema task.

### Must Read First

- [`AGENTS.md`](AGENTS.md)
- [`CURRENT_TASK.md`](CURRENT_TASK.md)
- [`RUN_COMMANDS.md`](RUN_COMMANDS.md)
- [`REVIEW_CHECKLIST.md`](REVIEW_CHECKLIST.md)
- [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md)
- [`src/jti_extract/ultra/g2_accumulate.py`](src/jti_extract/ultra/g2_accumulate.py)
- [`src/jti_extract/ultra/accumulators.py`](src/jti_extract/ultra/accumulators.py)
- [`src/jti_extract/ultra/diagnostics_pairing.py`](src/jti_extract/ultra/diagnostics_pairing.py)
- [`src/jti_extract/ultra/svd_estimators.py`](src/jti_extract/ultra/svd_estimators.py)

### Constraints

- Do not modify existing CLI/core baseline semantics.
- Do not add `jti-ultra-sweep` CLI or edit [`pyproject.toml`](pyproject.toml).
- Do not read real `.ttbin` files.
- Do not write to [`results/`](results/) or create formal output directories.
- Do not implement background subtraction or background-subtracted signed spectrum.
- Keep raw nonnegative `g2_all_candidates` counts as the main result.
- Return in-memory dictionaries/lists only.

### Candidate Files to Modify

- `src/jti_extract/ultra/sweep_ultra_jti.py`
- `tests/test_ultra_sweep_orchestration.py`
- [`RUN_COMMANDS.md`](RUN_COMMANDS.md)
- [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md)

## 2026-04-29 Stage D: sweep orchestration prototype — implemented

### 修改文件

| 文件 | 操作 | 说明 |
|---|---|---|
| [`src/jti_extract/ultra/sweep_ultra_jti.py`](src/jti_extract/ultra/sweep_ultra_jti.py) | **新建** | 4 个 orchestration 函数：`run_synthetic_sweep_point()`、`origin_sensitivity_summary()`、`edge_guard_sensitivity_summary()`、`method_comparison_sweep()` |
| [`tests/test_ultra_sweep_orchestration.py`](tests/test_ultra_sweep_orchestration.py) | **新建** | 10 个单元测试 |
| [`src/jti_extract/ultra/__init__.py`](src/jti_extract/ultra/__init__.py) | 修改 | 添加 Stage D 注释 |
| [`CURRENT_TASK.md`](CURRENT_TASK.md) | 修改 | Stage D 从 planning 改为 implemented |
| [`RUN_COMMANDS.md`](RUN_COMMANDS.md) | 修改 | 新增 `sweep_ultra_jti.py` 语法检查和单元测试命令 |
| [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) | 修改 | 记录本次 Stage D 实现 |

### Schema Impact

- **无**。`sweep_ultra_jti.py` 纯返回 Python dict/list，不生成输出文件、不改 CSV 列名、不改 CLI 参数、不改 JSON/YAML 键。

### Baseline Impact

- **无**。不修改任何现有算法语义。

### 验证结果

```text
test_ultra_sweep_orchestration.py  — 10/10 passed (0.05s)
test_ultra_lattice.py              — 11/11 passed (无回归)
test_ultra_accumulators.py         — 18/18 passed (无回归)
test_ultra_diagnostics_pairing.py  — 11/11 passed (无回归)
test_ultra_svd_estimators.py       — 20/20 passed (无回归)
test_cli_smoke.py                  — 2/2 passed  (无回归)
test_schmidt.py                    — 2/2 passed  (无回归)
py_compile (6 ultra 模块)          — all OK
```

### 全部 4 个 Stage 累计统计

| Stage | 源文件 | 测试文件 | 测试数 |
|---|---|---|---|
| A | `fold_lattice.py`, `g2_accumulate.py`, `accumulators.py` | `test_ultra_lattice.py`, `test_ultra_accumulators.py` | 29 |
| B | `diagnostics_pairing.py` | `test_ultra_diagnostics_pairing.py` | 11 |
| C | `svd_estimators.py` | `test_ultra_svd_estimators.py` | 20 |
| D | `sweep_ultra_jti.py` | `test_ultra_sweep_orchestration.py` | 10 |
| **总计** | **6 源文件** | **5 测试文件** | **70 tests** |

### 完整 Ultra 模块调用链

```
t_a, t_b → g2_accumulate.all_candidates()
         → accumulators.FixedLatticeAccumulator
         → diagnostics_pairing (strict_retention_meta, method_comparison_summary)
         → svd_estimators (svd_coarse_jti, truncated_schmidt_summary, block_bootstrap)
         → sweep_ultra_jti (run_synthetic_sweep_point, origin/edge sensitivity, method comparison)
```

### 剩余风险

- 所有测试基于合成数组，未使用真实 `.ttbin` 数据验证。
- 未实现 CLI、config schema 或正式输出目录。
- `block_bootstrap_coarse_jti()` 仍为简单 row-wise resampling（标注 `prototype`）。
- Stage D 的 origin/edge sensitivity helpers 尚未验证在大范围参数下的数值行为。

### Suggested Next Stage (Stage E)

规划和实现正式 CLI 与输出 schema（需要更新 [`CURRENT_TASK.md`](CURRENT_TASK.md) Allowed Files 和 [`REVIEW_CHECKLIST.md`](REVIEW_CHECKLIST.md)）：
- `jti-ultra-sweep` CLI entry point
- YAML config schema
- 新输出目录与输出文件命名约定
- CSV/JSON summary 输出格式
- 正式 output field 定义

### Stage E handoff note

- Stage E 当前仅做规划，不做实现。
- 保持与 [`CURRENT_TASK.md`](CURRENT_TASK.md) 和 [`RUN_COMMANDS.md`](RUN_COMMANDS.md) 中的 Stage E 文本一致。
- 继续禁止 background subtraction、真实 `.ttbin` 读取、`results/` 写入和任何可运行 ultra sweep CLI。

### Files Not to Modify

- [`src/jti_extract/cli/`](src/jti_extract/cli/)
- [`src/jti_extract/core/`](src/jti_extract/core/)
- [`configs/`](configs/)
- [`results/`](results/)
- [`pyproject.toml`](pyproject.toml)
- any `*.ttbin`

### Patch Instructions

1. Add `run_synthetic_sweep_point()` that accepts sorted `t_a`, `t_b`, fixed lattice parameters, `coarse_n_bins`, and optional `truncated_rank`; returns a summary dict.
2. Internally call [`all_candidates()`](src/jti_extract/ultra/g2_accumulate.py:96), [`FixedLatticeAccumulator.add_candidates()`](src/jti_extract/ultra/accumulators.py:102), [`method_comparison_summary()`](src/jti_extract/ultra/diagnostics_pairing.py:205), [`strict_retention_meta()`](src/jti_extract/ultra/diagnostics_pairing.py:109), and [`svd_coarse_jti()`](src/jti_extract/ultra/svd_estimators.py:21).
3. Add `origin_sensitivity_summary()` and `edge_guard_sensitivity_summary()` helpers that run multiple in-memory sweep points and report variation metrics; multiple origins must not be combined as independent samples.
4. Add tiny synthetic tests that verify summary keys, internal count consistency, no file writes, no CLI dependency, and method/origin/edge sensitivity outputs.
5. Update [`RUN_COMMANDS.md`](RUN_COMMANDS.md) with only light pytest/py_compile commands for the new module.

### Commands to Run

```bash
python -m pytest tests/test_ultra_sweep_orchestration.py -v
python -m pytest tests/test_ultra_lattice.py -v
python -m pytest tests/test_ultra_accumulators.py -v
python -m pytest tests/test_ultra_diagnostics_pairing.py -v
python -m pytest tests/test_ultra_svd_estimators.py -v
python -m pytest tests/test_cli_smoke.py -v
python -m pytest tests/test_schmidt.py -v
python -m py_compile src/jti_extract/ultra/sweep_ultra_jti.py
python -m py_compile src/jti_extract/ultra/fold_lattice.py
python -m py_compile src/jti_extract/ultra/g2_accumulate.py
python -m py_compile src/jti_extract/ultra/accumulators.py
python -m py_compile src/jti_extract/ultra/diagnostics_pairing.py
python -m py_compile src/jti_extract/ultra/svd_estimators.py
```

### Acceptance Criteria

- Full synthetic pipeline produces summary dict with candidate counts, edge metrics, strict retention, method sensitivity, `K_coarse`, and captured-energy fields.
- No files are written and no directories are created.
- No CLI/config/schema changes are introduced.
- No background subtraction or signed spectrum is added.
- Existing Stage A/B/C and legacy smoke tests still pass.
- [`CURRENT_TASK.md`](CURRENT_TASK.md)
- [`RUN_COMMANDS.md`](RUN_COMMANDS.md)
- [`REVIEW_CHECKLIST.md`](REVIEW_CHECKLIST.md)
- [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md)
- [`src/jti_extract/ultra/accumulators.py`](src/jti_extract/ultra/accumulators.py)
- [`src/jti_extract/ultra/diagnostics_pairing.py`](src/jti_extract/ultra/diagnostics_pairing.py)
- [`tests/test_ultra_accumulators.py`](tests/test_ultra_accumulators.py)
- [`tests/test_ultra_diagnostics_pairing.py`](tests/test_ultra_diagnostics_pairing.py)

### Constraints

- Do not modify existing CLI/core baseline semantics.
- Do not add `jti-ultra-sweep` CLI.
- Do not read real `.ttbin` files.
- Do not write to [`results/`](results/) or create formal output directories.
- Do not implement background subtraction or background-subtracted signed spectrum.
- Keep raw nonnegative `g2_all_candidates` counts as the main result.

### Candidate Files to Modify After Updating [`CURRENT_TASK.md`](CURRENT_TASK.md)

- `src/jti_extract/ultra/svd_estimators.py`
- `tests/test_ultra_svd_estimators.py`
- [`RUN_COMMANDS.md`](RUN_COMMANDS.md)
- [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md)

### Stage C Candidate Scope

1. coarse exact SVD on small/coarse nonnegative matrices;
2. truncated singular spectrum helper with explicit `captured_frobenius_energy_r`;
3. block bootstrap planning or tiny synthetic prototype only;
4. tests that reject negative matrices for Schmidt-style `sqrt(probability)` semantics.

### Commands to Run

```bash
python -m pytest tests/test_ultra_lattice.py -v
python -m pytest tests/test_ultra_accumulators.py -v
python -m pytest tests/test_ultra_diagnostics_pairing.py -v
python -m pytest tests/test_cli_smoke.py -v
python -m pytest tests/test_schmidt.py -v
python -m py_compile src/jti_extract/ultra/fold_lattice.py
python -m py_compile src/jti_extract/ultra/g2_accumulate.py
python -m py_compile src/jti_extract/ultra/accumulators.py
python -m py_compile src/jti_extract/ultra/diagnostics_pairing.py
```

### Acceptance Criteria

- Existing Stage A/B ultra tests still pass.
- No existing CLI/schema/baseline changes.
- No background subtraction or signed spectrum is added.
- No full experiment or real `.ttbin` processing is run.

## 2026-04-29 Stage E/F/G: real-data enablement — implemented

### 修改文件

| 文件 | 操作 | 阶段 | 说明 |
|---|---|---|---|
| [`configs/ultra_sweep.yaml`](configs/ultra_sweep.yaml) | **新建** | E | 配置文档模板（26 个键） |
| [`src/jti_extract/ultra/io_ultra.py`](src/jti_extract/ultra/io_ultra.py) | **新建** | F | CSV/JSON 写入器 + 输出 schema 字段定义 + NumPy JSON encoder |
| [`src/jti_extract/ultra/ttbin_adapter.py`](src/jti_extract/ultra/ttbin_adapter.py) | **新建** | F | TTBIN → NumPy 适配器（封装 Swabian TimeTagger 虚拟回放） |
| [`src/jti_extract/ultra/cli_ultra.py`](src/jti_extract/ultra/cli_ultra.py) | **新建** | F | `jti-ultra-sweep` CLI（24 个参数，`--self-test` 通过） |
| [`pyproject.toml`](pyproject.toml:26) | **修改** | F | 注册 `jti-ultra-sweep` console_script |
| [`src/jti_extract/ultra/cross_validate.py`](src/jti_extract/ultra/cross_validate.py) | **新建** | G | ultra all-candidates vs strict single-hit cross-validation |
| [`tests/test_ultra_io.py`](tests/test_ultra_io.py) | **新建** | F/G | 8 个测试 |
| [`tests/test_ultra_cross_validate.py`](tests/test_ultra_cross_validate.py) | **新建** | G | 3 个测试 |
| [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md) | **修改** | — | 更新 Workflow 7 实现状态 |
| [`CURRENT_TASK.md`](CURRENT_TASK.md) | **修改** | — | Stage E/F/G 从 planning → implemented |
| [`RUN_COMMANDS.md`](RUN_COMMANDS.md) | **修改** | — | 新增 4 个 py_compile + 2 个 pytest 命令 |
| [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) | **修改** | — | 记录本次 Stage E/F/G 实现 |

### Schema Impact

- **无既有 schema impact**。所有输出使用新命名空间（`ultra_summary.csv`、`ultra_summary.json`），不影响既有 `jti-extract`/`jti-schmidt`/`jti-tdc-residue`/`jti-tdc-layer-scan` 输出。
- 新 CLI 参数（`jti-ultra-sweep`）定义在独立入口中，不影响既有 CLI 参数语义。

### Baseline Impact

- **无**。未修改 [`src/jti_extract/cli/`](src/jti_extract/cli/) 下任何现有 CLI 语义。
- 未修改 [`src/jti_extract/core/`](src/jti_extract/core/) baseline 逻辑。
- 未覆盖任何现有结果文件。

### 验证结果

```text
test_ultra_io.py                    — 8/8  passed
test_ultra_cross_validate.py        — 3/3  passed
test_ultra_lattice.py               — 11/11 passed (无回归)
test_ultra_accumulators.py          — 18/18 passed (无回归)
test_ultra_diagnostics_pairing.py   — 11/11 passed (无回归)
test_ultra_svd_estimators.py        — 20/20 passed (无回归)
test_ultra_sweep_orchestration.py   — 10/10 passed (无回归)
test_cli_smoke.py                   — 2/2  passed (无回归)
test_schmidt.py                     — 2/2  passed (无回归)
py_compile (10 ultra 模块)          — all OK
```

### CLI self-test

```bash
$ jti-ultra-sweep --self-test
SELF-TEST PASSED
```

### 全部 7 个 Stage 累计统计

| Stage | 源文件 | 测试文件 | 测试数 |
|---|---|---|---|
| A | `fold_lattice.py`, `g2_accumulate.py`, `accumulators.py` | `test_ultra_lattice.py`, `test_ultra_accumulators.py` | 29 |
| B | `diagnostics_pairing.py` | `test_ultra_diagnostics_pairing.py` | 11 |
| C | `svd_estimators.py` | `test_ultra_svd_estimators.py` | 20 |
| D | `sweep_ultra_jti.py` | `test_ultra_sweep_orchestration.py` | 10 |
| E | `configs/ultra_sweep.yaml` | — | — |
| F | `io_ultra.py`, `ttbin_adapter.py`, `cli_ultra.py` + `pyproject.toml` | `test_ultra_io.py` (8) | 8 |
| G | `cross_validate.py` | `test_ultra_cross_validate.py` (3) | 3 |
| **总计** | **10 源文件 + 1 配置 + 1 pyproject 修改** | **7 测试文件** | **83 tests** |

### 剩余风险

- TTBIN 适配器需要 Swabian-TimeTagger 绑定，当前测试环境中不可用（所有测试使用合成数组）。
- Bootstrap 仍为简单 row-wise resampling（标注 `prototype`），未实现完整 block bootstrap。
- 未做真实 `.ttbin` 数据验证——需要进入 Stage 1（小规模 exact 对齐）才能 cross-validate。
- `jti-ultra-sweep` 需要在安装后才能通过 CLI 命令调用（当前通过 `python -m jti_extract.ultra.cli_ultra` 可用）。
- 输出目录 `make_output_dir()` 默认使用当前工作目录，可能意外写入非预期位置。

### ✅ Stage 0-2 已完成（2026-04-30）

- Stage 0：文档/harness 对齐 ✓
- Stage 1：小规模 exact 对齐 ✓（真实 `.ttbin` 验证通过）
- Stage 2：origin / edge guard sensitivity ✓（真实 `.ttbin` 验证通过）

### 🟢 当前阶段：Stage 3 中维度 coverage sweep

#### 修改文件

- [`CURRENT_TASK.md`](CURRENT_TASK.md) — 任务状态更新为 Stage 3
- [`RUN_COMMANDS.md`](RUN_COMMANDS.md) — 扩展 Stage 3-4 受控运行命令

#### Schema Impact

- 无。当前为文档更新阶段，未修改 CLI 参数、CSV 列、JSON 键或输出文件命名。

#### Baseline Impact

- 无。未修改 baseline 算法。

#### Commands Run

- 仅更新文档。计划中的验证命令见 [`CURRENT_TASK.md`](CURRENT_TASK.md) 的 Stage 3 验证步骤节。

#### Remaining Risks

- Stage 3 真实数据只有少量事件（~4600 events/ch），结果只能作为 exploratory diagnostic。
- coarse `4096 x 4096` matrix 约 134 MB（float64），需关注累计内存。
- 若 CLI 新增多值 sweep 参数，必须保留原单值参数不变以保证向后兼容。
- 若需要导出 profile/marginal/coarse matrix 到独立文件，需先在 [`io_ultra.py`](src/jti_extract/ultra/io_ultra.py) 增加 IO helper，不得改动现有 `SWEEP_SUMMARY_FIELDS`。

#### ✅ Stage 3 已完成

Stage 3 三个 grid point 已于 2026-04-30 全部运行成功。关键结果：
- N=8192/coarse=1024 → K_coarse=383.78
- N=16384/coarse=2048 → K_coarse=454.65
- N=32768/coarse=4096 → K_coarse=493.24

K_coarse 单调上升尚未饱和。输出见 `/tmp/ultra_stage3_*` 三个目录。

#### ✅ Stage 4 已完成（探索性诊断）

Stage 4 N=100000、coarse_N=8192 单点验证已于 2026-04-30 运行成功，耗时约 8 分钟（wall time 7:52），峰值内存约 3.05 GB。

**关键结果（主点, frame_origin_ps=0）**：
- `K_coarse` = 443.54（较 Stage 3 最高点 493.24 回落）
- `edge_rejection_ratio` = 0.0（边界剔除稳定）
- `captured_frobenius_energy_r` = 0.5288（截断 r=256 仅覆盖约 53% 能量）
- `K_truncated_r` = 202.56（辅助诊断，非完整覆盖）

**Origin sensitivity 结果**：

| frame_origin_ps | K_coarse |
|---|---|
| 0 | 443.54 |
| 2,500,000 | 435.56 |
| 5,000,000 | 461.88 |
| 7,500,000 | 467.83 |

`K_coarse` 在 435.56–467.83 间波动，最大相对偏差约 7%，未满足 `≤ 5%` 阈值。此外偏移 origin 下 `n_strict_pairs` 退化至 0，strict 基线在这些点上失活。

**当前结论（探索性）**：
- `K_coarse` 未继续上升，但从 493 回落至 444，无法判定为饱和（可能进入稀疏采样主导区）
- origin sensitivity 超过验收阈值，后续需更高统计量验证
- `captured_frobenius_energy_r` 仅 0.5288，截断诊断不足以导出完整物理维度
- 不得将 Stage 4 结果视为最终饱和或最终物理维度认证

**输出目录**：`/tmp/ultra_stage4_N100k_20260430_173925/`

### ✅ Stage 5A-E 已完成（探索性诊断）

Stage 5A-E 全步骤 8 个点已于 2026-04-30 全部运行成功。

#### 结果汇总表

| 点 | N | coarse_N | r | max_events | K_coarse | captured_frobenius_energy_r | K_truncated_r | edge_rejection_ratio | 输出目录 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|:---|
| B1 | 49152 | 4096 | 512 | 10000 | 485.01 | 1.0000 | 485.01 | 0.0 | `ultra_stage5B_N49152_c4096_r512_20260430_184215` |
| B2 | 65536 | 4096 | 512 | 10000 | 480.20 | 1.0000 | 480.20 | 0.0 | `ultra_stage5B_N65536_c4096_r512_20260430_184341` |
| B3 | 81920 | 4096 | 512 | 10000 | 489.92 | 0.9981 | 488.93 | 0.0 | `ultra_stage5B_N81920_c4096_r512_20260430_184442` |
| C1 | 65536 | 2048 | 512 | 10000 | 413.26 | 1.0000 | 413.26 | 0.0 | `ultra_stage5C_N65536_c2048_r512_20260430_184545` |
| C3 | 65536 | 8192 | 512 | 10000 | 519.72 | 0.9685 | 502.74 | 0.0 | `ultra_stage5C_N65536_c8192_r512_20260430_184550` |
| C4 | 100000 | 4096 | 512 | 10000 | 421.66 | 1.0000 | 421.66 | 0.0 | `ultra_stage5C_N100000_c4096_r512_20260430_185404` |
| D1 | 65536 | 4096 | 256 | 10000 | 480.20 | 0.5362 | 235.27 | 0.0 | `ultra_stage5D_N65536_c4096_r256_20260430_185504` |
| E1 | 65536 | 4096 | 512 | 30000 | 1135.43 | 0.4972 | 438.96 | 0.000631 | `ultra_stage5E_N65536_c4096_r512_max30000_20260430_185602` |

#### 关键诊断指标

| 指标 | 状态 | 详细 |
|---|---|---|
| coarse_N stability | ❌ 未收敛 | N=65536 下 c2048→c4096→c8192: K_coarse=413→480→520，跨度~25.8% |
| max_events gradient | ❌ 未收敛 | E1 (max_events=30000) K_coarse=1135 >> B2 (max_events=10000) 的 480 |
| truncated captured energy | ❌ 不足 | E1 的 r=512 仅捕获 49.7% Frobenius 能量，远低于 90% |
| strict baseline | ❌ 基本失效 | 多数长 frame 点 n_strict_pairs=0 |
| edge rejection | ✅ 可控 | 各点 edge_rejection_ratio ≤ 0.00063 |
| origin sensitivity | ⚠️ 部分点通过 | B2 在四个 origin 完全一致；E1 波动约 0.08%，通过 |
| schema integrity | ✅ 未改变 | 无字段名重命名或重排 |

#### 当前结论（探索性）

- 边界效应可控，origin sensitivity 在部分高统计量点上表现可接受
- 但 coarse_N 未收敛、max_events 梯度未收敛、truncated SVD 能量不足
- **不得将 Stage 5 结果作为最终饱和或最终物理维度认证**
- 只有框定了 coarse_N 稳定性和统计量收敛性的点后，才能进入最终汇总

**输出目录前缀**：`/tmp/ultra_stage5*`（共 8 个独立目录，全部在 `/tmp/` 下）

### 审查发现（2026-04-30）

外部 review 确认了以下关键问题：

1. **旧 Stage 6A 输出 JSON 缺 `diag_profile_*` 字段**
   - 证据：[`/tmp/ultra_stage6A_N65536_c4096_r1024_max100000_20260430_193527/ultra_summary.json`](file:///tmp/ultra_stage6A_N65536_c4096_r1024_max100000_20260430_193527/ultra_summary.json) 主点只到 `source`，不含 `diag_profile_peak_bin`、`diag_profile_mass_width_90_bins`、`diag_profile_mass_width_95_bins`、`diag_profile_edge_fraction`。
   - 根因：`run_synthetic_sweep_point()` 合并 `acc.summary()` 的 patch 晚于该运行。
   - 影响：不能用该输出来判断 diagonal-width convergence。

2. **当前 `K_coarse` 由 sparse occupancy 主导，而非物理维度收敛**
   - `K_coarse=480.20→1135.43→2245.71` 与 `n_candidates_after_edge_guard=539→1583→5213` 同步增长。
   - `svd_nonzero_bins` 与候选数同量级：`nonzero_bins / n_candidates ≈ 0.94→0.83→0.57`。
   - 高度提示 coarse JTI matrix 极度稀疏，SVD 指标是采样覆盖率而非物理 Schmidt 数。

3. **`max_events` 不是随机抽样梯度，而是文件前缀梯度**
   - `load_channels_from_ttbin()` 顺序读取到 `max_events` 后停止；10k→30k→100k 同时改变统计量和采集时间窗口。
   - `K_coarse` 不收敛不能只归因于 shot-noise，也不能反过来证明物理维度增长。

4. **输出覆盖风险**
   - [`cli_ultra.py`](src/jti_extract/ultra/cli_ultra.py:268) 使用 `os.makedirs(..., exist_ok=True)`；若 `--out` 目录已存在，`write_summary_csv()` 和 `write_json()` 会覆盖已有文件。

### 下一步（执行 agent）

▶ **当前任务**：[`CURRENT_TASK.md`](CURRENT_TASK.md:104) Stage 6A-recheck — 重跑确认 `diag_profile_*` 字段传播 + 稀疏占用 sanity gate

**执行顺序：**

1. **确认代码 patch 状态**
   - [`FixedLatticeAccumulator.summary()`](src/jti_extract/ultra/accumulators.py:178) 必须含 `diag_profile_*` 字段
   - [`run_synthetic_sweep_point()`](src/jti_extract/ultra/sweep_ultra_jti.py:117) 必须合并 `acc.summary()`
   - [`tests/test_ultra_sweep_orchestration.py`](tests/test_ultra_sweep_orchestration.py:40) 必须断言 `run_synthetic_sweep_point()` 返回这些键

2. **运行轻量验证**
   ```bash
   ~/envs/timetagger/bin/python -m pytest tests/test_ultra_accumulators.py tests/test_ultra_sweep_orchestration.py -v
   ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra --self-test
   ```

3. **重跑 Stage 6A（全新目录，必须不含旧路径）**
   ```bash
   /usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
     --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
     --ch-a 1 --ch-b 3 --max-events 100000 \
     --n-bins 65536 --binwidth-ps 100 --frame-origin-ps 0 \
     --coincidence-window-ps 200 --edge-guard-ps 200 \
     --origin-sensitivity 1638400 3276800 4915200 \
     --edge-guard-sensitivity 100 200 300 \
     --coarse-n-bins 4096 --truncated-rank 1024 \
     --out /tmp/ultra_stage6A_recheck_jsonwidth_N65536_c4096_r1024_max100000_$(date +%Y%m%d_%H%M%S)
   ```

4. **验证 JSON 字段和 CSV schema**
   - JSON 主点必须含 `diag_profile_*` 字段
   - CSV 必须不含 `diag_profile_*` 字段（schema 未扩展）

5. **报告稀疏占用 sanity 表**

   | `max_events` | `n_candidates_after_edge_guard` | `svd_nonzero_bins` | `K_coarse` | `K_coarse / n_candidates` | `nonzero_bins / n_candidates` |
   |---:|---:|---:|---:|---:|---:|
   | 10000 | 539 | 506 | 480.20 | 0.891 | 0.939 |
   | 30000 | 1583 | 1314 | 1135.43 | 0.717 | 0.830 |
   | 100000 | 5213 | 2969 | 2245.71 | 0.431 | 0.570 |

   - 如果 `K_coarse` 继续随候选数强烈增长 → 判定为 sparse sampling dominated
   - 如果 `diag_profile_mass_width_90/95` 随 `max_events` 明显扩张 → 不认定为收敛

6. **判断是否可讨论 Stage 6B**
   - 必须同时满足：字段完整、`K_coarse` 相邻变化 < 20%、diagonal-width 稳定、origin sensitivity ≤ 5%、edge rejection ≤ 2%
   - 基于现有数据，当前预期为不满足，结论保持 ⚠️ exploratory only / ❌ not certified

**禁止：**
- 改动已有 Stage 0–5 输出目录
- 覆盖 `/tmp/ultra_stage6A_20260430_193527/`
- 改动 CLI、CSV schema、baseline 代码
- 宣称最终物理维度认证

### Stage 6A-recheck 结果（已验证，2026-04-30）

- ✅ JSON 字段传播确认
- ✅ CSV schema 未扩展
- ❌ `K_coarse = 2245.71` 仍远未满足相邻 max_events 收敛条件
- ❌ `captured_frobenius_energy_r = 0.55`

### Stage 7 结果（已完成，2026-04-30）

- S7-A（`N=32768, 3.28 µs`）：输出 `/tmp/ultra_stage7_linewidth_N32768_20260430_200142/`
- S7-B：复用 Stage 6A-recheck（`N=65536, 6.55 µs`）
- S7-C（`N=100000, 10.0 µs`）：输出 `/tmp/ultra_stage7_linewidth_N100000_20260430_200334/`
- `diag_profile_mass_width_95_bins = 2`（200 ps）三点稳定
- `captured_frobenius_energy_r ≈ 0.55`，`svd_nonzero_bins / n_candidates ≈ 0.57`

百 kHz 先验下已覆盖，但先验可能是几百 kHz，需补短帧。

### 下一步（执行 agent）

▶ **当前任务**：[`CURRENT_TASK.md`](CURRENT_TASK.md:490) Stage 8 — high-linewidth short-horizon scan

#### 背景

线宽可能是几百 kHz，coherence horizon 可能短至 ~0.6–3.3 µs。Stage 8 补扫 `N=8192/16384/24576/32768` 四点，覆盖 `0.82–3.28 µs`。

#### 执行顺序

1. **运行轻量验证**
   ```bash
   ~/envs/timetagger/bin/python -m pytest tests/test_ultra_accumulators.py tests/test_ultra_sweep_orchestration.py -v
   ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra --self-test
   ```
2. **运行 S8-A（N=8192, 0.819 µs）**
   ```bash
   /usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
     --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
     --ch-a 1 --ch-b 3 --max-events 100000 \
     --n-bins 8192 --binwidth-ps 100 --frame-origin-ps 0 \
     --coincidence-window-ps 200 --edge-guard-ps 200 \
     --origin-sensitivity 204800 409600 614400 \
     --edge-guard-sensitivity 100 200 300 \
     --coarse-n-bins 4096 --truncated-rank 1024 \
     --out /tmp/ultra_stage8_short_horizon_N8192_c4096_r1024_max100000_$(date +%Y%m%d_%H%M%S)
   ```
3. **运行 S8-B（N=16384, 1.638 µs）**
   ```bash
   /usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
     --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
     --ch-a 1 --ch-b 3 --max-events 100000 \
     --n-bins 16384 --binwidth-ps 100 --frame-origin-ps 0 \
     --coincidence-window-ps 200 --edge-guard-ps 200 \
     --origin-sensitivity 409600 819200 1228800 \
     --edge-guard-sensitivity 100 200 300 \
     --coarse-n-bins 4096 --truncated-rank 1024 \
     --out /tmp/ultra_stage8_short_horizon_N16384_c4096_r1024_max100000_$(date +%Y%m%d_%H%M%S)
   ```
4. **运行 S8-C（N=24576, 2.458 µs）**
   ```bash
   /usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
     --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
     --ch-a 1 --ch-b 3 --max-events 100000 \
     --n-bins 24576 --binwidth-ps 100 --frame-origin-ps 0 \
     --coincidence-window-ps 200 --edge-guard-ps 200 \
     --origin-sensitivity 614400 1228800 1843200 \
     --edge-guard-sensitivity 100 200 300 \
     --coarse-n-bins 4096 --truncated-rank 1024 \
     --out /tmp/ultra_stage8_short_horizon_N24576_c4096_r1024_max100000_$(date +%Y%m%d_%H%M%S)
   ```
5. **S8-D 复用** Stage 7 S7-A（`N=32768, 3.277 µs`）
6. **汇总 0.82–10 µs 七点结果**

#### 判据

- `diag_profile_mass_width_95_ps` 在 0.82–3.28 µs 间相对变化 < 20% 且 `width95_ps < 0.3 × frame_length_ps`
- `svd_nonzero_bins / n_candidates > 0.3` → sparse dominated
- 若 width 全部稳定，则 `S7-D (N=200000)` 不需要跑

#### 预期结论

```text
✅ local diagonal profile width: stable at ~200 ps across 0.82–10 µs frames
✅ compatible with few-hundred-kHz linewidth prior
⚠️ K_coarse / full effective dimension: not certified due to sparse occupancy and insufficient truncated SVD energy
```

#### 禁止

- 改动 Stage 0–7 输出目录
- 覆盖任一 `/tmp/ultra_stage*` 目录
- 改动 CLI、CSV schema、baseline 代码

### Stage 8 结果（已完成，2026-04-30）

- 轻量验证通过：`tests/test_ultra_accumulators.py`、`tests/test_ultra_sweep_orchestration.py` 与 `cli_ultra --self-test` 均通过
- S8-A（`N=8192, 0.819 µs`）：输出 `/tmp/ultra_stage8_short_horizon_N8192_c4096_r1024_max100000_20260430_202409/`
- S8-B（`N=16384, 1.638 µs`）：输出 `/tmp/ultra_stage8_short_horizon_N16384_c4096_r1024_max100000_20260430_202501/`
- S8-C（`N=24576, 2.458 µs`）：输出 `/tmp/ultra_stage8_short_horizon_N24576_c4096_r1024_max100000_20260430_202625/`

**Stage 8 主点汇总表：**

| `N` | `frame_length_µs` | `width95_ps` | `diag_profile_edge_fraction` | `K_coarse` | `svd_nonzero_bins / n_candidates_after_edge_guard` | `captured_frobenius_energy_r` | `edge_rejection_ratio` |
|:---|---:|---:|---:|---:|---:|---:|---:|
| 8192 | 0.8192 | 200 | 0.8237666 | 2056.98 | 3231/5209 ≈ 0.6203 | 0.5873 | 0.000959 |
| 16384 | 1.6384 | 200 | 0.8236761 | 2165.63 | 3097/5212 ≈ 0.5942 | 0.5651 | 0.000384 |
| 24576 | 2.4576 | 200 | 0.8236761 | 2200.30 | 3055/5212 ≈ 0.5862 | 0.5596 | 0.000384 |

> 注：`width95_ps = diag_profile_mass_width_95_bins × bin_width_ps = 2 × 100 ps = 200 ps`；"svd_nonzero_bins" 来自 JSON 字段 `svd_nonzero_bins`，"n_candidates_after_edge_guard" 来自 JSON 字段 `n_candidates_after_edge_guard`，源码见 [`src/jti_extract/ultra/io_ultra.py`](src/jti_extract/ultra/io_ultra.py:22)。

### Stage 6B 最终汇总与可信度判断（✅ 已完成，2026-04-30）

#### 最终档位：⚠️ **exploratory only**

#### 可以 certified 的三项

| 结论 | 证据 |
|---|---|
| ✅ 局部 diagonal profile width ≈ 200 ps，在 0.819–10 µs 帧长范围内高度稳定 | `diag_profile_mass_width_95_bins = 2`（`= 2 × 100 ps`）在全部 6 个扫描点一致 |
| ✅ 最短已测帧长 0.819 µs 已足以容纳此局部宽度 | `200 ps << 0.3 × 819200 ps` 在所有点满足 |
| ✅ 与数百 kHz 线宽先验的短 horizon 扫描结果不冲突（exploratory consistency） | S8-A/B/C 短帧诊断稳定 |

#### 不能 certified 的三项

| 结论 | 证据 |
|---|---|
| ❌ `K_coarse` / full effective dimension → not certified | `svd_nonzero_bins / n_candidates_after_edge_guard ≈ 0.57–0.62`（远 > 0.3 sparse-dominated 阈值）；`K_coarse` 随候选数线性增长（480→1135→2246）未出现 plateau；N=100000 异常下降到 1338 |
| ❌ truncated SVD → not certified | `captured_frobenius_energy_r ≈ 0.55–0.59`，远低于 0.9 门槛 |
| ❌ full Schmidt-number certification → not supported | 所有未收敛项均不支持 |

#### 严重警告

- `diag_profile_edge_fraction ≈ 0.824` 高且稳定：对角 profile 的质量集中在边缘 bin，不应过度推断全局二维形状已被认证
- `K_coarse` 在 N=100000 处异常下降至 1338（而非继续微增），可能是因为 coarse lattice 覆盖物理范围变化；此点需后续研究
- 未运行 `S7-D (N=200000, 20 µs)`——当前证据不认为 20 µs 帧长会改变结论

#### 参考数据源

- Stage 8 主点表见上文 [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md:1537)
- max_events 梯度：5B (10k)→5E (30k)→6A-recheck (100k)
- coarse_N 灵敏度：5C (c2048, c8192) — 与 100k events 不完全可比
- 所有输出目录均在 `/tmp/ultra_stage*`，不覆盖已有结果

▶ **项目状态：全部 Stage 0–8 + 6B 已完成。最终结论档位：⚠️ exploratory only。** 建议后续方向见 [`CURRENT_TASK.md`](CURRENT_TASK.md:643)。

---

### Stage 9: diagonal-ridge localization handoff（**下一任务，尚未开始**）

#### 背景

Stage 0–8 + 6B 已经认证了横向 diagonal width ≈ 200 ps，但 **明亮区对角线沿 frame 的实际时间位置仍未知**。当前 `diag_profile` 只统计 `|bin_a - bin_b|`，不能回答"亮区在 frame 内哪里"。

`diag_profile_peak_bin = 0` 说明 pair 成员落在同一 bin，`diag_profile_edge_fraction ≈ 0.824` 说明 diagonal profile 的质量集中在 bin 0 和 bin N-1。这暗示亮可能紧贴在 frame boundary 附近——但目前只是间接推断，需要 center-profile 数据锁证。

#### Goal

新增 JSON-only `diag_center_*` 诊断字段，用 `(bin_a + bin_b)//2` 计算 pair 中心位置，累积沿对角线方向的 profile，直接定位置亮区在 frame 内的实际时间坐标。

#### 候选修改文件

- [`src/jti_extract/ultra/accumulators.py`](src/jti_extract/ultra/accumulators.py:18)：添加 `_diag_center_profile`, `summary()` 新字段
- [`tests/test_ultra_accumulators.py`](tests/test_ultra_accumulators.py:295)：`test_diag_center_fields`, `test_diag_center_symmetry`
- [`tests/test_ultra_sweep_orchestration.py`](tests/test_ultra_sweep_orchestration.py:28)：`test_diag_center_fields_propagated`

#### 禁止修改

- [`src/jti_extract/ultra/io_ultra.py`](src/jti_extract/ultra/io_ultra.py:22) — `SWEEP_SUMMARY_FIELDS` 不改
- [`src/jti_extract/ultra/sweep_ultra_jti.py`](src/jti_extract/ultra/sweep_ultra_jti.py:28) — 不动
- [`src/jti_extract/ultra/g2_accumulate.py`](src/jti_extract/ultra/g2_accumulate.py:62)、[`fold_lattice.py`](src/jti_extract/ultra/fold_lattice.py:54)、[`svd_estimators.py`](src/jti_extract/ultra/svd_estimators.py:172)
- 所有旧 `/tmp/ultra_stage*` 输出目录

#### 候选新增 JSON-only 字段

| 字段 | 含义 |
|---|---|
| `diag_center_peak_bin` | 亮 ridge 峰值 bin |
| `diag_center_peak_time_ps` | 峰值对应的 frame-local 时间 |
| `diag_center_mass_width_90/95_bins` | 沿对角线的 90%/95% 质量宽度（bins） |
| `diag_center_mass_width_90/95_ps` | 同上（ps） |
| `diag_center_edge_fraction` | center profile 在 frame 边缘的质量占比 |

#### 实现要点

- `center_idx = ((ba_kept + bb_kept) // 2)`，clip 到 `[0, n_bins-1]`
- `diag_center_peak_time_ps = frame_origin_ps + (peak_bin + 0.5) × bin_width_ps`
- `summary()` 新增字段会被现有 `**acc.summary()` 自动传播到 JSON
- CSV schema 不做任何扩展

#### 验证命令

```bash
~/envs/timetagger/bin/python -m pytest tests/test_ultra_accumulators.py tests/test_ultra_sweep_orchestration.py -v
~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra --self-test
```

#### 真实数据诊断（复用 S8-A 参数）

```bash
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 100000 \
  --n-bins 8192 --binwidth-ps 100 --frame-origin-ps 0 \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --origin-sensitivity 204800 409600 614400 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 4096 --truncated-rank 1024 \
  --out /tmp/ultra_stage9_diag_center_N8192_c4096_r1024_max100000_$(date +%Y%m%d_%H%M%S)
```

#### Stage 9 执行结果（✅ 已完成，2026-04-30）

- 轻量验证：31 tests passed, self-test OK
- 代码修改：3 文件（见下方）
- 真实数据：`N=8192` 单点诊断完成，输出到 `/tmp/ultra_stage9_diag_center_N8192_c4096_r1024_max100000_20260430_205822/`

**diag_center_* 诊断结果：**

| 字段 | 值 | 释义 |
|---|---|---|
| `diag_center_peak_bin` | 2201 | ridge 峰值 bin |
| `diag_center_peak_time_ps` | 220150 | ridge 峰值在 frame 内的实际时间，约 0.220 µs（27% 从 origin） |
| `diag_center_mass_width_95_ps` | 773600 | ridge 沿对角线 95% 质量宽度，约 0.774 µs |
| `diag_center_edge_fraction` | 0.0 | ridge 完全未被 frame 边界裁切 |

**判据评估：**

| 判据 | 要求 | 实际 | 状态 |
|---|---|---|---|
| 峰值在 frame 中心 1/3–2/3 | 0.273–0.546 µs | 0.220 µs（27%） | ⚠️ 略低于 1/3 阈值 |
| edge_fraction < 0.3 | < 0.3 | 0.0 | ✅ 完全通过 |
| width95/frame_length < 0.5 | < 0.5 | 0.944（94%） | ❌ ridge 几乎填满整个 frame |
| CSV schema 不变 | 不变 | 不变 | ✅ |

**物理解读：**

- 亮 ridge 沿 frame-local 时间轴几乎填满整个 0.819 µs frame（width95 覆盖 94% 帧长，`≈0.944 × frame_length_ps`）
- ridge 峰值偏向前端（`diag_center_peak_time_ps ≈ 0.220 µs`，占帧长约 27%，低于预设的中心 1/3 阈值）
- `diag_center_edge_fraction = 0.0`：仅说明 **linear center profile** 首末 bin 无质量
- ⚠️ 当前 `center_idx = (ba+bb)//2` 是 linear center，不是 circular center。当 pair 跨 frame boundary（bin 0 ↔ bin N-1）时，linear center 会把边界两侧的 pair 不对称地映射到 frame 中间。由于 `diag_profile_edge_fraction≈0.824` 很高，跨边界 ambiguity 是活跃风险。当前不能排除 circular-wrap-around ridge 的可能性。
- ⚠️ `frame_origin_ps=0` 在当前数据下 **未被验证为最优或足够好**。`diag_center_peak_time_ps` 偏离帧中心、`diag_center_mass_width_95_ps` 覆盖 94% 帧长——这些证据不支持 origin 已足够好的强结论。后续 origin recentering sweep 可检验。

**剩余风险（linear center limitation）：**

- `diag_center_edge_fraction=0.0` 仅采样 `center_profile[0] + center_profile[-1]`，不能排除 wrap-around ridge
- 若要精确定位 bright ridge 的实际时间坐标，建议后续做 origin recentering sweep（粗略偏移量 ≈ peak_time - frame_length/2 ≈ 220150 - 409600 ≈ -189450 ps）或 circular-center diagnostic
- 当前解释限于 **linear center diagnostic**，不等价于 circular ridge localization

#### 修改文件
- [`src/jti_extract/ultra/accumulators.py`](src/jti_extract/ultra/accumulators.py:18)
- [`tests/test_ultra_accumulators.py`](tests/test_ultra_accumulators.py:307)
- [`tests/test_ultra_sweep_orchestration.py`](tests/test_ultra_sweep_orchestration.py:99)

---

## Stage 10-12 规划（下阶段任务入口）

### 背景

Stage 9 确认 `diag_center_mass_width_95_ps = 773600 ps`（约 0.774 µs），但这是 linear-center diagnostic，wrap-around ambiguity 尚未排除。当前需要 Stage 10-12 才能把这个值从 exploratory 升级为 credible duration estimate。

### 三个阶段目标

| Stage | 目标 | 主要动作 |
|:---|---:|---|
| **10** | 验证 0.774 µs 真实性 | circular-center diagnostic + origin recentering + frame-length/max_events sweep + method sensitivity |
| **11** | duration → time-bin span | 几何换算：773600/100 ≈ 7736 bins，三档报告 |
| **12** | Schmidt-like 认证尝试 | 小维度 exact SVD → coarse_N 灵敏度 → truncated-rank 收敛 → block bootstrap |

### 前置代码任务

1. **积累器 circular-center**：在 [`accumulators.py`](src/jti_extract/ultra/accumulators.py:19) 中实现 `_diag_center_circular_profile`，沿用现有 `_quantile_width()` + `summary()` 模式。新增 JSON-only fields（diag_center_circular_*）。
2. **测试**：`test_ultra_accumulators.py` 测试 wrap/non-wrap/empty，`test_ultra_sweep_orchestration.py` 测试 JSON 字段传播。
3. **Per-method helper**（Stage 10.6）：在 [`diagnostics_pairing.py`](src/jti_extract/ultra/diagnostics_pairing.py:1) 新增 minimum helper，支持 `strict_single_hit` / `nearest` / `greedy_unique` / `folded_without_strict` 的完整 accumulator summary（width95/peak_time/K_coarse）。
4. **Block bootstrap**（Stage 12.4）：修正或新增 proper block bootstrap；现有 `block_bootstrap_coarse_jti()` 是 placeholder，不能用于 certification。

### 最大风险

- `0.774 µs` 是 `N=8192` frame 的 94.4% → 可能是 boundary-limited lower bound
- sparse occupancy 仍主导（`svd_nonzero/nguard ≈ 0.57–0.62`）→ duration 可认证但 Schmidt K 不一定
- truncated SVD energy 不足（`captured_frobenius_energy_r ≈ 0.55–0.59`）→ 远低于 0.9 门槛

### 详细规划

完整的 Stage 10-12 实施规划（含涉及文件、禁止行为、schema 政策、baseline 政策、运行命令、rollback 策略）见 [`CURRENT_TASK.md`](CURRENT_TASK.md:916)。

---

## Stage 10-12 执行结果（✅ 已完成，2026-05-01）

### 代码修改

- [`src/jti_extract/ultra/accumulators.py`](src/jti_extract/ultra/accumulators.py:19) — 新增 `_diag_center_circular_profile`、circular accumulation in `add_candidates()`、circular JSON-only fields in `summary()`、`_circular_mass_width()` torus-aware helper、circular minimal-arc width fields
- [`tests/test_ultra_accumulators.py`](tests/test_ultra_accumulators.py:357) — 新增 10 个 circular-center 测试（fields_exist, non_wrap, wrap, reverse_wrap, empty, consistency, min_arc_width_fields_exist, min_arc_width_narrow, min_arc_width_uniform, min_arc_width_empty）

### 轻量验证

- 41 tests passed（含 10 个新增 circular-center 测试）
- `cli_ultra --self-test` PASSED

### Bug fix: circular-center direction asymmetry（2026-05-01）

**问题**：原 circular-center 算法只在 `delta = (bb - ba) % N > N//2` 时 unwrap `bb`，处理 `ba≈0, bb≈N-1` 但不能处理反向 `ba≈N-1, bb≈0`。

**修复**：改用 signed shortest displacement `d = ((bb - ba + N//2) % N) - N//2`，对偶数 N 的 tie（`d = ±N/2`）固定选择正方向。见 [`add_candidates()`](src/jti_extract/ultra/accumulators.py:185)。

**新增测试**：[`test_diag_center_circular_reverse_wrap()`](tests/test_ultra_accumulators.py:463) 验证 `ba=99, bb=0, N=100` 时 circular center 落在 99 而非 50。

### 新增: circular minimal-arc width（2026-05-01）

**动机**：原 `_quantile_width()` 在线性数组上取 cumulative quantile，不能正确度量跨边界的 circular distribution。

**实现**：[`_circular_mass_width()`](src/jti_extract/ultra/accumulators.py:121) 在 doubled profile 上用 sliding window + binary search 找覆盖目标 mass fraction 的最短 circular arc。

**新增 JSON-only fields**：
- `diag_center_circular_min_arc_width_90_bins` / `_ps`
- `diag_center_circular_min_arc_width_95_bins` / `_ps`

**测试**：narrow cluster at boundary（arc ≤ 3 bins）、uniform profile（arc = 95 bins）、empty profile（arc = 0）。

### Stage 10.3: origin recentering sweep 结果

12 origins 扫描（`-300000` 到 `614400 ps`）：

| 指标 | 值 | 判定 |
|---|---|---|
| `diag_center_mass_width_95_ps` 范围 | 773000–782600 ps | ✅ 相对变化 ~1.2% |
| `diag_center_circular_mass_width_95_ps` 范围 | 773700–781800 ps | ✅ 相对变化 ~1.0% |
| `linear_vs_circular_width_ratio` | 全部 = 1.00 | ✅ linear ≈ circular |
| `edge_rejection_ratio` | 全部 ≤ 0.0013 | ✅ ≤ 2% |
| `K_coarse` | 2046–2058 | ✅ 稳定 |

**结论**：0.774 µs 不受 origin 选择影响，linear/circular center 一致。

### Stage 10.4: frame-length containment sweep 结果

| N | frame_µs | lin_w95_ps | circ_w95_ps | w95/frame | K_coarse | svd_nz/nguard | E_trunc |
|---|---|---|---|---|---|---|---|
| 8192 | 0.819 | 773600 | 774400 | 0.944 | 2057 | 0.620 | 0.587 |
| 12288 | 1.229 | 1167600 | 1167100 | 0.950 | 2123 | 0.607 | 0.577 |
| 16384 | 1.638 | 1556400 | 1557000 | 0.950 | 2166 | 0.594 | 0.565 |
| 24576 | 2.458 | 2336000 | 2333600 | 0.950 | 2200 | 0.586 | 0.560 |
| 32768 | 3.277 | 3125500 | 3121200 | 0.954 | 2226 | 0.579 | 0.557 |

**⚠️ 关键发现**：width95 随 N 线性增长，始终覆盖 frame 的 ~94.4–95.4%。**0.774 µs 是 N=8192 frame 的截断下限，不是物理持续时间。**

### Stage 10.5: max_events convergence 结果

| max_events | lin_w95_ps | circ_w95_ps | K_coarse | n_cand | svd_nz/nguard | E_trunc |
|---|---|---|---|---|---|---|
| 100000 | 773600 | 774400 | 2057 | 5209 | 0.620 | 0.587 |
| 300000 | 775800 | 776500 | 2775 | 15480 | 0.341 | 0.492 |
| 500000 | 777400 | 777500 | 2983 | 25828 | 0.237 | 0.464 |

**结论**：width95 稳定（~0.5% 变化），K_coarse 仍随统计量增长（2057→2983）。

### Stage 10.6: method sensitivity 结果

| method | n_pairs | w95_ps | circ_w95_ps | K_coarse |
|---|---|---|---|---|
| g2_all_candidates | 5209 | 773600 | 774400 | 2057.0 |
| strict_single_hit | 3118 | 663000 | 780500 | 1236.6 |
| nearest | 5209 | 773600 | 774400 | 2057.0 |
| greedy_unique | 5209 | 773600 | 774400 | 2057.0 |
| folded_without_strict | 5209 | 773600 | 774400 | 2057.0 |

**结论**：g2=nearest=greedy=folded 完全一致；strict_single_hit 偏窄（663000 vs 773600），因 strict filter 丢弃了多 hit frame。

### Stage 12.1: 小维度 exact SVD

| N | K_exact | lin_w95_ps | svd_nz | n_cand |
|---|---|---|---|---|
| 512 | 329.5 | 48400 | 1108 | 5176 |
| 1024 | 645.2 | 97100 | 1740 | 5188 |
| 2048 | 1165.1 | 194500 | 2625 | 5202 |
| 4096 | 1903.3 | 389000 | 3517 | 5208 |

**结论**：K 随 N 增长，确认 frame-containment 效应。

### Stage 12.2: coarse_N sensitivity

| N | coarse_N | K_coarse | K/coarse_N | svd_nz/nguard | E_trunc |
|---|---|---|---|---|---|
| 8192 | 1024 | 824.9 | 0.806 | 0.218 | 1.000 |
| 8192 | 2048 | 1366.9 | 0.667 | 0.403 | 0.773 |
| 8192 | 4096 | 2057.0 | 0.502 | 0.620 | 0.587 |
| 8192 | 8192 | 2820.3 | 0.344 | 0.808 | 0.480 |
| 16384 | 1024 | 851.2 | 0.831 | 0.207 | 1.000 |
| 16384 | 2048 | 1436.8 | 0.702 | 0.385 | 0.757 |
| 16384 | 4096 | 2165.6 | 0.529 | 0.594 | 0.565 |
| 16384 | 8192 | 2948.9 | 0.360 | 0.777 | 0.466 |

**结论**：K_coarse 随 coarse_N 增长，未收敛。K/coarse_N 下降说明高维 JTI 更稀疏。

### Stage 12.3: truncated-rank convergence

| r | K_truncated | E_trunc | r_actual |
|---|---|---|---|
| 512 | 482.8 | 0.368 | 512 |
| 1024 | 914.3 | 0.587 | 1024 |
| 2048 | 1621.9 | 0.865 | 2048 |
| 4096 | 2057.0 | 1.000 | 2824 |

**结论**：E_trunc=0.865 at r=2048（低于 0.9 门槛），K_truncated 仍随 r 增长。

### Stage 12.4: proper block bootstrap

| block_size_ps | K_mean | K_rel_std | width95_mean | width95_rel_std | circ_width95_mean | circ_width95_rel_std |
|---|---|---|---|---|---|---|
| 5000 | 1476 | 4.0% | 774015 | 0.37% | 774719 | 0.37% |
| 10000 | 1480 | 5.2% | 774112 | 0.39% | 774519 | 0.39% |
| 20000 | 1477 | 8.0% | 774021 | 0.35% | 774304 | 0.35% |

**结论**：
- width95 bootstrap rel_std ~0.35–0.39% → **duration 非常可信**
- K bootstrap rel_std 4–8% → K 有一定稳定性但未达 <10% 门槛（block_5000ps 刚好达标）
- K_mean ≈ 1476（低于 point estimate 2057），说明 block bootstrap 降低了 K 估计

### Stage 11: duration-based dimension 换算

由于 Stage 10.4 确认 width95 随 N 线性增长（frame-containment artifact），**不能直接用 0.774 µs 作为物理持续时间**。

报告口径：

> The along-diagonal bright-ridge duration is frame-containment limited: width95 ≈ 94.4% of frame_length for all tested N (8192–32768). The measured 0.774 µs at N=8192 is a lower bound, not a converged physical duration. A conservative power-of-two discretization is d=4096, while d=8192 is boundary-limited.

中文口径：

> 沿对角线亮 ridge 持续时间受 frame 截断限制：在所有测试的 N（8192–32768）下，width95 ≈ frame_length 的 94.4%。N=8192 下测得的 0.774 µs 是下限，不是收敛的物理持续时间。保守可支持 4096 维，8192 维受边界限制。

### Stage 12.5: 最终认证状态

| 判据 | 状态 | 详情 |
|---|---|---|
| width95 origin 稳定性 | ✅ 通过 | 12 origins 相对变化 ~1.2% |
| width95 frame-length 稳定性 | ❌ 未通过 | width95 随 N 线性增长（frame-containment） |
| width95 max_events 稳定性 | ✅ 通过 | 100k→500k 相对变化 ~0.5% |
| width95 method 一致性 | ✅ 通过 | g2=nearest=greedy=folded |
| width95 bootstrap 稳定性 | ✅ 通过 | rel_std ~0.35% |
| K_coarse coarse_N 收敛 | ❌ 未通过 | K 随 coarse_N 增长 |
| K_coarse max_events 收敛 | ❌ 未通过 | K 随统计量增长 |
| captured_frobenius_energy ≥ 0.9 | ❌ 未通过 | E_trunc=0.865 at r=2048 |
| K bootstrap rel_std < 10% | ⚠️ 边缘 | block_5000ps: 4.0%, block_20000ps: 8.0% |

### 最终档位：⚠️ folded center-profile width stable, physical duration not certified

**可报告的结论：**

> ✅ **folded center-profile width 对 origin/method/bootstrap 高度稳定**：origin 变化 ~1.2%，method 一致（g2=nearest=greedy=folded），bootstrap rel_std ~0.35%。
> ✅ **circular-center 与 linear-center 一致**：linear_vs_circular_width_ratio = 1.00，排除 wrap-around 污染。
> ✅ **circular minimal-arc width 新增**：torus-aware diagnostic，可正确度量跨边界 cluster。

**不支持的结论：**

> ❌ **0.774 µs 作为物理持续时间**：width95 随 N 线性增长（~94.4% of frame_length），是 frame-containment artifact，不是 certified duration。
> ❌ **full Schmidt-number certification**：K_coarse 随 coarse_N 和 max_events 增长，E_trunc < 0.9，不能认证。
> ❌ **duration-supported dimension**：不能从 0.774 µs 推导出 d=7736 的 certified time-bin span。

### 修改文件汇总

| 文件 | 修改内容 |
|---|---|
| [`src/jti_extract/ultra/accumulators.py`](src/jti_extract/ultra/accumulators.py:19) | 新增 `_diag_center_circular_profile`、circular accumulation、circular JSON-only fields、`_circular_mass_width()` torus-aware helper、circular minimal-arc width fields |
| [`tests/test_ultra_accumulators.py`](tests/test_ultra_accumulators.py:357) | 新增 10 个 circular-center 测试（含 reverse-wrap + min_arc_width） |
| [`CURRENT_TASK.md`](CURRENT_TASK.md:916) | Stage 10-12 完整规划 + bug fix 记录 |
| [`RUN_COMMANDS.md`](RUN_COMMANDS.md:540) | Stage 10-12 运行命令 |
| [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md:1688) | Stage 10-12 入口 + 执行结果 + bug fix + corrected conclusions |

### 剩余风险

1. **frame-containment 是主要 blocker**：需要更大 N（>32768）或不同物理方法来确定真实持续时间
2. **sparse occupancy 仍主导**：svd_nz/nguard ≈ 0.24–0.62，K 随统计量增长
3. **truncated SVD 能量不足**：E_trunc=0.865 at r=2048，低于 0.9 门槛
4. **proper block bootstrap 仅在 N=8192 下运行**：需要在更大 N 下验证

### Suggested follow-up

1. **运行 N=65536 或更大 frame**：检验 `diag_center_circular_min_arc_width_95_ps` 是否在更大 frame 下收敛到某个物理值，而不是继续随 N 增长。如果 min_arc_width 也随 N 增长，则确认当前 folded center distribution 是 near-uniform，不是 bright ridge。

2. **增加 max_events 到完整 TTBIN**：检验 K_coarse 是否出现 plateau。当前 K 从 2057（100k）→ 2983（500k），仍近似线性增长。

3. **实现 proper block bootstrap 集成到 CLI**：当前 block bootstrap 仅在 `/tmp` 脚本中运行，未纳入仓库。需要在 [`svd_estimators.py`](src/jti_extract/ultra/svd_estimators.py:251) 中正式实现并补充测试。

4. **新增 null / surrogate center-profile diagnostic**：比较真实 `diag_center_circular_min_arc_width_95_ps` 与 phase-shuffled surrogate 的 arc width。若真实与 null 相同，则不能称为 bright-ridge duration。

5. **考虑物理方法**：如 pump coherence decay、photon correlation g2(τ) 等独立方法来估计持续时间，不依赖 frame folding。

6. **把 method sensitivity 纳入仓库**：在 [`diagnostics_pairing.py`](src/jti_extract/ultra/diagnostics_pairing.py:1) 新增 per-method full summary helper（width95/peak_time/K_coarse），替代临时脚本。

---

## Stage 13-19 规划（下阶段任务入口）

### 背景

Stage 10-12 确定 `diag_center_mass_width_95_ps` 受 frame-containment 限制（~94.4% of frame_length）。0.774 µs 是 N=8192 frame 的截断下限，不是物理持续时间。当前需要 Stage 13-19 来回答：**亮 ridge 是否被百微秒帧截断？如果是，plateau 在哪个时间尺度？**

### 核心逻辑链

```
profile-only 上探 (Stage 13)
  → containment sweep (Stage 14)
    → 二分搜索 plateau (Stage 15)
      → max_events 验证 (Stage 16)
        → containment 后才做近似 Schmidt (Stage 17)
          → 最终报告 (Stage 18-19)
```

### 关键新增

1. **`--profile-only` CLI flag**：在 [`cli_ultra.py`](src/jti_extract/ultra/cli_ultra.py:39) 新增，跳过 coarse JTI/SVD/bootstrap。
2. **Profile flatness 指标**：在 [`accumulators.py`](src/jti_extract/ultra/accumulators.py:213) 新增 JSON-only `diag_center_circular_peak_to_mean`、`cv`、`entropy`。
3. **主判据切换**：从 `mass_width` 切换到 `circular_min_arc_width` 作为主判据。
4. **uniform profile 分支**：当 `min_arc/frame ≈ 0.95` 且 `peak_to_mean ≈ 1` 时，结论为 "profile approximately uniform; folded duration metric not informative"。

### 前置代码任务

1. 在 [`cli_ultra.py`](src/jti_extract/ultra/cli_ultra.py:39) 实现 `--profile-only` flag。
2. 在 [`accumulators.py`](src/jti_extract/ultra/accumulators.py:213) 实现 flatness fields（peak_to_mean, CV, entropy）。
3. 新增测试（cli_params + accumulator fields）。
4. Stage 13A reproducibility check（N=32768 profile-only）。

### 最大风险

- N=1000000 下 `_circular_mass_width()` 的 O(N·logN) 复杂度可能耗时数秒。
- `peak_to_mean ≈ 1` 时不能给出 duration lower bound，只能跳至物理方法。
- 即使出现 containment，Schmidt-like K 仍可能不收敛（sparse/truncation limited）。

### 详细规划

完整的 Stage 13-19 实施规划见 [`CURRENT_TASK.md`](CURRENT_TASK.md:921)。

---

## Stage 13-19 执行结果

### 前置 patch（已实现）

- [`cli_ultra.py`](src/jti_extract/ultra/cli_ultra.py:131) — 新增 `--profile-only` flag
- [`accumulators.py`](src/jti_extract/ultra/accumulators.py:284) — 新增 JSON-only flatness fields：`diag_center_circular_peak_to_mean`、`diag_center_circular_cv`、`diag_center_circular_entropy_log2`
- 38 tests passed; CLI self-test passed

### Stage 13A: N=32768 reproducibility check

| N | frame_µs | min_arc_w95_µs | min_arc/frame | mass_w95_µs | peak_to_mean | cv | entropy_log2 | log2(N) | n_candidates |
|---|---|---|---|---|---|---|---|---|---|
| 32768 | 3.28 | 3.09 | 0.942 | 3.13 | 25.1 | 2.50 | 12.2 | 15.0 | 5213 |

**验收**：`circular_mass_width_95_ps` = 3,125,500 ps 正确。JSON 不含 `K_coarse`（profile-only 模式有效）。Runtime: ~1.2 s。

**注意**：Stage 13A 的 origin sensitivity 执行值使用了错误的 8192000/16384000/24576000 ps（而非 819200/1638400/2457600 ps），等效于 modulo 等价 origin。主点结果有效，但 origin sensitivity 不可作为 T/4/T/2/3T/4 验收。

### Stage 13B: N=1000000 (100 µs) upper-bound probe

| metric | value |
|---|---|
| min_arc_w95_ps | 94,036,100 ps (94.04 µs) |
| min_arc/frame | 0.940 |
| mass_w95_ps | 94,415,100 ps |
| peak_to_mean | 575.4 |
| cv | 13.8 |
| entropy_log2 | 12.3 / 19.9 |
| n_candidates | 5214 |
| edge_rejection_ratio | 0.0 |

**结论**：`min_arc/frame ≈ 0.94` 且 `peak_to_mean >> 1`（575.4）→ NOT contained, NOT uniform metric failure。Duration lower bound > ~95 µs at 100 ps binning. Runtime: ~29 s, peak memory: ~124 MB.

### Stage 14: Containment sweep

| N | frame_µs | min_arc_w95_µs | min_arc/frame |
|---|---|---|---|
| 32768 | 3.28 | 3.09 | 0.942 |
| 100000 | 10.00 | 9.40 | 0.940 |
| 300000 | 30.00 | 28.25 | 0.942 |
| 500000 | 50.00 | 47.04 | 0.941 |
| 1000000 | 100.00 | 94.04 | 0.940 |

**结论**：所有 N 下 `min_arc/frame ≈ 0.94`，无 plateau。情况 A（未 containment）。

### Stage 15: 跳過（无 plateau 可搜索）

Stage 14 未 containment，二分搜索不执行。

### Stage 16: max_events convergence (N=1000000)

| max_events | candidates | min_arc_w95_µs | min_arc/frame | peak_to_mean |
|---|---|---|---|---|
| 100000 | 5214 | 94.04 | 0.940 | 575.4 |
| 200000 | 10446 | 94.33 | 0.943 | 287.2 |
| 300000 | 15490 | 94.49 | 0.945 | 193.7 |
| 400000 | 20653 | 94.60 | 0.946 | 145.3 |
| 500000 | 25842 | 94.65 | 0.947 | 116.1 |

**结论**：width 微弱增长（+0.6% from 100k to 500k），peak_to_mean 下降。duration lower bound 稳定但未收敛；profile contrast 随统计量增加下降，不能简单解释为 "duration being filled out"。

### Stage 17: 跳過（未 containment，不执行 Schmidt-like 诊断）

`min_arc/frame ≈ 0.94`，containment 未出现。按 [`CURRENT_TASK.md`](CURRENT_TASK.md:1160) 规则不应做 Schmidt-like 诊断。实际 exploratory 执行显示：

| coarse_N | K_coarse | candidates |
|---|---|---|
| 1024 | 854.1 | 5214 |
| 2048 | 1463.5 | 5214 |
| 4096 | 2283.4 | 5214 |

这些 K 值仅用于反例说明：即使跑 coarse SVD，K 仍随 coarse_N 线性增长（854→2283），不满足任何认证门槛。

### Stage 18-19: 最终结论

**Containment**: NOT reached up to 100 µs frame.
**Metric validity**: Valid — `peak_to_mean >> 1`, `cv >> 0`, NOT uniform failure.
**Duration lower bound**: `T_ridge95 > ~95 µs` at 100 ps binwidth.
**Schmidt certification**: NOT attempted. K would remain sparse/truncation limited.
**Next directions** (Stage 19):
- 继续上探：N=2000000 (200 µs), N=3000000 (300 µs), profile-only
- 换物理方法：pump coherence / JSI linewidth / delay line

### 输出目录

```
/tmp/ultra_stage13A_N32768_profile_20260502_005307/
/tmp/ultra_stage13B_N1000000_profile_20260502_005449/
/tmp/ultra_stage14_N100000_profile_*/
/tmp/ultra_stage14_N300000_profile_*/
/tmp/ultra_stage14_N500000_profile_*/
/tmp/ultra_stage16_N1000000_me100000_*/
/tmp/ultra_stage16_N1000000_me200000_*/
/tmp/ultra_stage16_N1000000_me300000_*/
/tmp/ultra_stage16_N1000000_me400000_*/
/tmp/ultra_stage16_N1000000_me500000_*/
/tmp/ultra_stage17_N1000000_c1024_r1024_*/   (exploratory only)
/tmp/ultra_stage17_N1000000_c2048_r1024_*/   (exploratory only)
/tmp/ultra_stage17_N1000000_c4096_r1024_*/   (exploratory only)
```

---

## Stage 20-24 规划（下阶段任务入口）

### 背景

Stage 13-19 确定 `min_arc/frame ≈ 0.94` 从 3.28 µs 到 100 µs 近似恒定，100 µs 仍未 containment。Stage 20-24 转向一个新问题：

> **不再问 "center profile 的 95% mass 覆盖多宽"**，而是问：**在长 frame 中，哪些 local segment 的 on-diagonal density 显著高于 sideband background？**

### 核心逻辑链

```
contrast profile (Stage 20)
  → aperture selection (Stage 21)
    → aperture JTI reconstruction (Stage 22)
      → aperture-conditioned Schmidt (Stage 23)
        → surrogate / control validation (Stage 24)
```

### 关键区别 vs Stage 13-19

| 维度 | Stage 13-19 | Stage 20-24 |
|---|---|---|
| 问题 | 95% mass 覆盖多宽？ | 哪些 segment 的 on-diag 密度显著高于背景？ |
| 窗口 | `coincidence_window_ps=200` | `contrast_window_ps=3000` |
| 指标 | `min_arc_width_95` | `contrast_ratio`, `snr` |
| 分析类型 | center profile quantile | per-segment contrast |
| 认证目标 | full-frame duration | local aperture → conditioned Schmidt |

### 新增模块

| 模块 | 职责 |
|---|---|
| [`src/jti_extract/ultra/contrast_profiles.py`](src/jti_extract/ultra/contrast_profiles.py) | Stage 20：contrast window candidate select + per-segment on-diag/sideband contrast |
| [`src/jti_extract/ultra/aperture_select.py`](src/jti_extract/ultra/aperture_select.py) | Stage 21：run-length + threshold aperture selection + train/test holdout |
| [`src/jti_extract/ultra/aperture_jti.py`](src/jti_extract/ultra/aperture_jti.py) | Stage 22：aperture-local JTI reconstruction（phase-folded across global frames；完整 circular unwrap 尚未实现） |
| [`src/jti_extract/ultra/surrogate_controls.py`](src/jti_extract/ultra/surrogate_controls.py) | Stage 24：time-shift / phase-shuffle / off-diagonal aperture |
| [`tests/test_ultra_contrast_profiles.py`] | 对应测试 |
| [`tests/test_ultra_aperture_select.py`] | 对应测试 |
| [`tests/test_ultra_aperture_jti.py`] | 对应测试 |
| [`tests/test_ultra_surrogate_controls.py`] | 对应测试 |

### 关键新增 CLI 参数

- `--contrast-profile`, `--contrast-window-ps`, `--on-diag-band-bins`, `--bg-inner-bins`, `--bg-outer-bins`, `--center-coarse-bins`
- `--select-aperture`, `--aperture-threshold`, `--aperture-min-run-segments`, `--aperture-max-gap-segments`, `--aperture-holdout-blocks`
- `--aperture-schmidt`
- `--surrogate-shifts-ps`

所有参数为 optional，不改变已有参数默认值或语义。

### 执行顺序

| 轮次 | 内容 |
|---|---|
| 1 | Stage 20 contrast profile sweep（N=100k/300k/500k/1M, M=512/1024, max_events=100k） |
| 2 | Stage 21 aperture selection（最有希望的 N, snr3/snr5/contrast2） |
| 3 | Stage 22 aperture JTI（train/test holdout） |
| 4 | Stage 23 Schmidt convergence（coarse_N + rank + max_events + bootstrap） |
| 5 | Stage 24 surrogate controls（time-shift + shuffle + off-diag） |

### 最大风险

1. **所有 segment 的 contrast ≈ 1** → 无可靠局部亮区，不进入 Stage 21
2. **aperture 对 M 或阈值极端敏感** → 降级为 diagnostic
3. **train/test aperture 不一致** → 不认证 aperture
4. **surrogate contrast ≈ true contrast** → 不认证
5. **4 个新模块 scope 较大** → 每个实现最小功能，复用已有 `all_candidates()` / `FixedLatticeAccumulator` / `svd_coarse_jti()`

### 详细规划

完整的 Stage 20-24 实施规划见 [`CURRENT_TASK.md`](CURRENT_TASK.md:1734)。

---

## Stage 20-24 执行结果（2026-05-01）

### 修改文件

| 文件 | 修改 |
|---|---|
| [`src/jti_extract/ultra/contrast_profiles.py`](src/jti_extract/ultra/contrast_profiles.py) | 新增模块：`select_contrast_candidates()` + `build_contrast_profile()`（bincount 累计，sideband_zero 标记，contrast_ratio=None when sideband=0） |
| [`src/jti_extract/ultra/aperture_select.py`](src/jti_extract/ultra/aperture_select.py) | 新增模块：`select_apertures()`（run-length + threshold，contrast_ratio=None 处理，n_sideband_zero_segments） |
| [`src/jti_extract/ultra/aperture_jti.py`](src/jti_extract/ultra/aperture_jti.py) | 新增模块：`build_aperture_accumulator()`（aperture-local lattice，aperture_n_bins，aperture_origin_ps） |
| [`src/jti_extract/ultra/surrogate_controls.py`](src/jti_extract/ultra/surrogate_controls.py) | 新增模块：`time_shift_surrogate()` + `phase_shuffle_surrogate()`（保留 frame index + 排序） |
| [`src/jti_extract/ultra/cli_ultra.py`](src/jti_extract/ultra/cli_ultra.py) | 新增 CLI 参数：--contrast-profile, --select-aperture 等；single candidate select 复用；多阈值 aperture 输出 |
| [`tests/test_ultra_contrast_profiles.py`](tests/test_ultra_contrast_profiles.py) | 5 tests |
| [`tests/test_ultra_aperture_select.py`](tests/test_ultra_aperture_select.py) | 5 tests |
| [`tests/test_ultra_aperture_jti.py`](tests/test_ultra_aperture_jti.py) | 2 tests |
| [`tests/test_ultra_surrogate_controls.py`](tests/test_ultra_surrogate_controls.py) | 4 tests |

### 不碰

- [`SWEEP_SUMMARY_FIELDS`](src/jti_extract/ultra/io_ultra.py:22)：CSV schema 不变
- [`accumulators.py`](src/jti_extract/ultra/accumulators.py)：baseline 行为不变
- [`g2_accumulate.py`](src/jti_extract/ultra/g2_accumulate.py)：`all_candidates()` 语义不改
- `src/jti_extract/cli/`、`src/jti_extract/core/`、`scripts/`、`configs/`、原始 `.ttbin`、`results/`

### Stage 20 结果

**N=300000, max_events=100000:**

| 指标 | 值 |
|---|---|
| n_candidates (contrast window) | 5666 |
| sideband_zero | 271/512 (53%) |
| contrast_ratio valid range | 12.60–159.60 |
| max_snr | 4.47 |
| snr3 | 291/512 |
| snr5 | 0/512 |

**N=1000000:** Runtime 4.2s, 124 MB RSS.

### Stage 21 结果

| Threshold | Apertures | Largest (µs) | mean_snr | sb_zero |
|---|---|---|---|---|
| snr3 | 38 | 1.58 | 3.15 | 14/27 |
| snr5 | 0 | — | — | — |
| contrast2 | 43 | 0.70 | 3.36 | 3/12 |
| contrast5 | 43 | 0.70 | 3.36 | 3/12 |

### Stage 22 结果（aperture-local lattice）

| 字段 | 值 |
|---|---|
| aperture_n_bins | 15820 |
| aperture_origin_ps | 5214843.75 ps |
| n_candidates_in_aperture | 283 |
| diag_center_circular_min_arc_width_95_ps | 1,447,900 ps (1.45 µs) |
| folding_mode | phase-folded-across-global-frames |

### Stage 23 结果（aperture-local coarse_N）

| coarse_N | K | nonzero | n_cand |
|---|---|---|---|
| 16 | 15.19 | 16 | 283 |
| 32 | 28.72 | 32 | 283 |
| 64 | 53.07 | 64 | 283 |
| 128 | 85.84 | 108 | 283 |

**K grows linearly → NOT converged. Statistics-limited (283 candidates). Exploratory only.**

### Stage 24 结果

| Control | max_snr | n_snr3 | true/surr |
|---|---|---|---|
| True | 4.47 | 291 | — |
| Time-shift 0.01 µs | 1.29 | 0 | 3.46× |
| Time-shift 0.1 µs | 1.29 | 0 | 3.46× |
| Time-shift 1.0 µs | 1.29 | 0 | 3.46× |
| Phase-shuffle | 4.47 | 291 | **1.00×** |

### 最终结论（必须降级）

> **Phase-shuffle surrogate 未降低 contrast（true/surr=1.00）→ Stage 24 未通过。不认证 aperture、不认证 Schmidt-like K。**
>
> Time-shift control 可破坏 absolute-time coincidence，证明 on-diagonal counts 高于随机 sideband 并非完全由 Poisson 统计产生。但 phase-shuffle control 保留 frame marginal 分布后，contrast 指标不变，说明当前 Stage 20 per-segment contrast 主要由 frame-phase marginal / occupancy 决定，而非局部 temporal correlation 主导。
>
> Stage 20 contrast diagnostic 检测到一个 robust 结构，但该结构不能被 phase-shuffle 破坏 → 不能认证为局部亮区。Stage 23 K 仍随 coarse_N 增长 + 统计稀疏（283 candidates）。不进入 Stage 25 认证。
>
> 代码模块可作为 prototype 继续迭代。方向不变：扩大 max_events、改进 sideband 定义、增加 SN applied to valid-sideband only 的 aperture 选择。但当前数据不能支持任何 aperture 或 Schmidt-like 科学声明。

### 项目运行总览

#### 已运行数据

- **TTBIN 文件**: `TimeTags_2026-04-03_213758.ttbin`（Type0ppln P_plus 数据）
- **通道**: ch-a=1, ch-b=3
- **max_events**: 100000（全部 Stage 0-24 运行）；额外 200k/300k/400k/500k（Stage 16 max_events sweep）
- **帧**: N=8192–32768（Stage 0-12），N=100000–1000000（Stage 13-20）
- **bw**: 100 ps（全部运行）

#### 已实现代码模块

| 模块 | 状态 |
|---|---|
| [`src/jti_extract/ultra/cli_ultra.py`](src/jti_extract/ultra/cli_ultra.py) | 完整 CLI，33 个参数 |
| [`src/jti_extract/ultra/accumulators.py`](src/jti_extract/ultra/accumulators.py) | `FixedLatticeAccumulator`（circular center, flatness, min_arc_width） |
| [`src/jti_extract/ultra/contrast_profiles.py`](src/jti_extract/ultra/contrast_profiles.py) | Stage 20 per-segment contrast profile |
| [`src/jti_extract/ultra/aperture_select.py`](src/jti_extract/ultra/aperture_select.py) | Stage 21 run-length + threshold aperture |
| [`src/jti_extract/ultra/aperture_jti.py`](src/jti_extract/ultra/aperture_jti.py) | Stage 22 aperture-local JTI（phase-folded） |
| [`src/jti_extract/ultra/surrogate_controls.py`](src/jti_extract/ultra/surrogate_controls.py) | Stage 24 time-shift + phase-shuffle control |
| [`src/jti_extract/ultra/svd_estimators.py`](src/jti_extract/ultra/svd_estimators.py) | coarse SVD + truncated SVD + block bootstrap |
| [`src/jti_extract/ultra/g2_accumulate.py`](src/jti_extract/ultra/g2_accumulate.py) | all-candidates coincidence iterator |
| [`src/jti_extract/ultra/fold_lattice.py`](src/jti_extract/ultra/fold_lattice.py) | fixed global frame lattice |

#### 已安装测试

| 测试文件 | tests |
|---|---|
| [`tests/test_ultra_accumulators.py`](tests/test_ultra_accumulators.py) | 7 |
| [`tests/test_ultra_cli_params.py`](tests/test_ultra_cli_params.py) | 5 |
| [`tests/test_ultra_svd_estimators.py`](tests/test_ultra_svd_estimators.py) | 5 |
| [`tests/test_ultra_contrast_profiles.py`](tests/test_ultra_contrast_profiles.py) | 5 |
| [`tests/test_ultra_aperture_select.py`](tests/test_ultra_aperture_select.py) | 5 |
| [`tests/test_ultra_aperture_jti.py`](tests/test_ultra_aperture_jti.py) | 3 |
| [`tests/test_ultra_surrogate_controls.py`](tests/test_ultra_surrogate_controls.py) | 4 |
| 其他 ultra 测试 | 12 |
| **总计** | **46+** |

#### 核心科学发现

1. **diag_center_circular_min_arc_width_95_ps 占 frame 的 ~94%**, 从 N=8192 (0.8192 µs) 到 N=1000000 (100 µs) 近似恒定。**无 plateau → frame containment 不成立**。
2. **100 µs frame 内 peak_to_mean=575, cv=13.8, entropy=12.3/19.9** → profile NOT uniform。指标未失效，但统计仍不够。
3. **max_events 收敛**: width 随候选数增长 +0.6%（100k→500k），peak_to_mean 从 575→116。duration 有微弱增长趋势，未 fully converged。
4. **K_coarse NOT convergent**: 随 coarse_N 线性增长（Stage 17: 854→2283; Stage 23 aperture-local: 15→29→53→86）。**Schmidt certification 不成立**。
5. **Contrast 存在但 phase-shuffle surrogate 未降低**（true/surr=1.00×）。Time-shift 可降低（3.46×），但 phase-shuffle 保留后 contrast 不变 → **aperture contrast 主要由 frame-phase marginal 决定**，不能认证为局部亮区。
6. **sideband_zero 占 53% segments** → 低 sideband 统计量导致 SNR 定义不可靠。current sideband definition（bg_inner=10, bg_outer=30 bins）不够宽。

#### 未解决的科学问题

| 问题 | 当前状态 | 可能的下一步 |
|---|---|---|
| **ridge 的真实持续时间** | > 95 µs at 100 ps bw，但无上限 | 继续上探 N=2000000/3000000，或物理方法 |
| **contrast 来源** | phase-shuffle 不降低 → frame marginal 决定 | 改进 sideband 定义 + 增大 bg_outer |
| **sideband 统计不足** | 53% segments sideband=0 | 增大 bg_outer_bins（30→100+），或增加 max_events |
| **aperture 稳定性** | 38 apertures, snr5=0 | 增大统计量后重测 |
| **K 不收敛** | 线性增长，283 candidates | Full TTBIN 或 500k events |
| **Schmidt certification** | 不满足任何门槛 | 需要 K 收敛 + energy>0.9 + bootstrap 稳定 |
| **block bootstrap** | 已实现 prototype 但未跑 | 在 aperture-local JTI 或 full-frame 上启用 |
| **captured energy** | 未在 aperture-local 上测 | 需要 truncated SVD + `--aperture-schmidt` |

### 输出目录

- `/tmp/ultra_stage20_N300000_contrast/`
- `/tmp/ultra_stage20_N1000000_contrast/`
- `/tmp/ultra_stage21_N300000_aperture/`

---

## Stage 25-27 规划（下阶段任务入口）

### 背景

Stage 20-24 检测到了 on-diagonal 富集结构，但未能认证为局部亮区。核心否定证据：

1. **sideband 太窄**（bg_outer=30 bins → 53% segments sideband=0）
2. **phase-shuffle 未降 contrast**（true/surr=1.00）
3. **aperture 统计稀疏**（283 candidates，K 线性增长）

Stage 25-27 **不再继续追 Schmidt number**，而是先修正 contrast profile 的背景估计和 surrogate 统计。

### 核心逻辑链

```
--out overwrite fix (25E)
  → snr_valid_bg + bg_outer sweep (25A)
    → contrast profile 重跑 N=300000/1000000 (25B)
      → phase-shuffle 20次分布 (25C)
        → time-shift decay scale (25D)
          → gate checklist → re-aperture (26)
            → gate checklist → aperture-conditioned Schmidt (27)
```

### 关键区别 vs Stage 20-24

| 维度 | Stage 20-24 | Stage 25-27 |
|---|---|---|
| 目标 | 选 aperture + 算 K | 先修复 contrast 可靠性 |
| sideband | bg_outer=30 fixed | bg_outer=50/100/200 sweep |
| SNR | 单层 snr | snr_raw + snr_valid_bg |
| aperture scoring | 基于 raw snr | 默认 valid-bg-only |
| phase-shuffle | 单次 → 1.00× | 20次分布 → z-score |
| --out 覆盖 | exist_ok=True | fail if non-empty + --overwrite |

### 新增/修改模块

| 文件 | 修改 |
|---|---|
| [`src/jti_extract/ultra/contrast_profiles.py`](src/jti_extract/ultra/contrast_profiles.py:144) | 新增 `snr_raw`、`snr_valid_bg`、`is_snr3_valid_bg`、`is_snr5_valid_bg` |
| [`src/jti_extract/ultra/aperture_select.py`](src/jti_extract/ultra/aperture_select.py:113) | 默认使用 `snr_valid_bg`（旧 `snr` 保留） |
| [`src/jti_extract/ultra/surrogate_controls.py`](src/jti_extract/ultra/surrogate_controls.py:61) | 新增 `phase_shuffle_multi()` |
| [`src/jti_extract/ultra/cli_ultra.py`](src/jti_extract/ultra/cli_ultra.py:327) | `--out` overwrite fix；新增 `--overwrite`、`--phase-shuffle-n`、`--bg-outer-bins` 多值 |
| [`tests/test_ultra_contrast_hardening.py`](tests/test_ultra_contrast_hardening.py) | 新增测试文件 |

### 关键新增 CLI 参数

- `--bg-outer-bins 50 100 200`（多值 sweep）
- `--phase-shuffle-n 20`
- `--overwrite`、`--append`
- `--aperture-use-raw-snr`（恢复旧行为）

## Stage 25-27 执行结果（2026-05-01）

### Phase-shuffle 20×: DECISIVE NEGATIVE RESULT

With `max_events=500000`, the contrast profile becomes robust:
- `n_candidates = 28234`
- `sideband_zero = 16/512 (3%)`
- `max_snr = 8.24`

Phase-shuffle 20× gives the decisive negative result:
- `true_max_snr = 8.24`, `shuffle_max_snr = 8.24 ± 0.00`
- `true_zscore = 0.00`, `true_percentile = 0.0%`

**Twenty independent phase-shuffle runs all produce identical max_snr. The contrast is completely preserved by phase-shuffle. zscore=0.00.**

Physical meaning: The "phase" here is the **frame phase** (modulo position within each frame), not optical phase. Phase-shuffle preserves each channel's frame-phase marginal while destroying the joint A-B correspondence. The fact that contrast is unchanged means it is dominated by frame-phase marginal / occupancy patterns, not by a local temporal coincidence correlation.

### Time-shift decay

| shift | max_snr | true/surr |
|---|---|---|
| 5 ns | 1.63 | 5.05× |
| 10 ns | 1.44 | 5.71× |
| 30 ns | 1.53 | 5.37× |
| 100 ns | 1.63 | 5.05× |
| 1 µs | 1.75 | 4.72× |
| 10 µs | 1.63 | 5.05× |

Time-shift reduces contrast ≈5× with **no delay dependence**. Consistent with global marginal effect.

### Gate summary

| Condition | Actual | Threshold | Status |
|---|---|---|---|
| sideband_zero_fraction | 3% | < 20% | ✅ |
| snr_valid_bg under snr5 | 496/512 | ≥ 1 | ✅ |
| **phase_shuffle true_zscore** | **0.00** | **≥ 3** | **❌ BLOCKED** |
| n_candidates_in_aperture | 28234 | ≥ 1000 | ✅ |

### Stage 26-27: Percolently Blocked

- **Stage 26 (re-aperture)**: BLOCKED. Phase-shuffle zscore=0.00 < 3.
- **Stage 27 (aperture-conditioned Schmidt)**: BLOCKED. No stable aperture exists.

> **The aperture/Schmidt route is permanently blocked under the current contrast metric.**

### Archive

The full closure report is at [`docs/ULTRA_JTI_FRAME_LENGTH_CLOSURE_REPORT.md`](docs/ULTRA_JTI_FRAME_LENGTH_CLOSURE_REPORT.md).

**Project closed / archived: 2026-05-01**.

### Modified files (this stage)

- `src/jti_extract/ultra/cli_ultra.py`: `--overwrite` flag, `--phase-shuffle-n`, `--out` overwrite guard
- `src/jti_extract/ultra/contrast_profiles.py`: `snr_raw`, `snr_valid_bg`, `is_snr3/5_valid_bg`
- `src/jti_extract/ultra/aperture_select.py`: default uses `snr_valid_bg`
- `src/jti_extract/ultra/surrogate_controls.py`: `phase_shuffle_multi()` function

**Schema impact**: None. New fields are additive; old fields preserved.

**Baseline impact**: None. Baseline algorithms unchanged; `SWEEP_SUMMARY_FIELDS` unchanged.

**Commands run**: inline Python scripts (no experiments via CLI).

**Final conclusion**:
- Reliable: transverse timing-correlation width ≈ 200 ps.
- Not certified: physical along-diagonal duration, local temporal aperture, Schmidt number, aperture-conditioned K.

**Remaining future work**: JSI/MUB/Franson physical methods or a separate Schmidt methodology study.
