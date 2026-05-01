# AGENTS.md

## 项目级 Agent 总规则

> 本文件为 `jti-extract` 项目的 agent 操作总纲。所有 agent 在执行任务前必须阅读本文件并遵守全部规则。

---

### 1. 执行环境

- **优先 OS**: WSL/Linux (POSIX 环境)
- **Python 版本**: >= 3.9（见 [`pyproject.toml`](pyproject.toml:10)）
- **路径约定**: 使用 POSIX 路径；Windows 路径标注为 `legacy Windows path` 且不作为默认执行路径
- **包安装**: `python -m pip install -e ".[dev]"` 可编辑安装（含 pytest）；`python -m pip install -e ".[plotting,dev]"` 含 matplotlib
- **TimeTagger 绑定**: `*.ttbin` 读取需要 Swabian TimeTagger Python 绑定；本项目 WSL 环境使用 `~/envs/timetagger`，Python 可执行文件为 `~/envs/timetagger/bin/python`，pip 包名为 `Swabian-TimeTagger`
- **TimeTagger import 规则**: 只允许 `from Swabian import TimeTagger`；禁止使用 `import TimeTagger`；运行 TimeTagger 相关脚本前必须先 `source ~/envs/timetagger/bin/activate`，或直接使用 `~/envs/timetagger/bin/python path/to/script.py`
- **TTBIN 离线读取规则**: `.ttbin` 离线分析默认使用 `TimeTagger.FileReader()` 读取事件流并按通道筛选；不要默认使用 `createTimeTaggerVirtual()`，除非显式验证虚拟回放许可证/硬件环境可用

### 2. 核心约束原则

- **Minimal Patch Only**: 仅进行必要的最小化修改，禁止大规模重构
- **Schema Stability**: 禁止静默改变量名、配置项、CLI 参数、CSV 列名、JSON/YAML 键、输出字段和文件名
- **Baseline Stability**: 禁止改变基线算法语义，禁止影响科学计算结果
- **Raw Data/Result Protection**: 禁止修改原始数据和已有结果文件

### 3. 明确禁止行为

#### 3.1 静默修改接口

不得在没有显式迁移任务的情况下修改：

- CLI 参数名称和语义
- CSV 列名和顺序
- JSON/YAML 配置键
- 函数签名（尤其是 [`run_extract()`](src/jti_extract/cli/extract.py) 及 core 模块公共 API）
- 输出文件命名约定

#### 3.2 Broad Refactor

除非 `CURRENT_TASK.md` 显式允许，禁止大规模代码重构。

#### 3.3 Full Experiment

除非 `CURRENT_TASK.md` 显式允许，禁止运行完整实验。

#### 3.4 数据覆盖风险

- 禁止覆盖 `*.ttbin` 原始数据文件
- 禁止覆盖 `results/` 目录下已有生成物
- 禁止覆盖时间戳命名的输出目录（如 `pplus_auto_dim_*`）
- 禁止删除 `logs/`、`runs/`、`outputs/`、`checkpoints/` 目录（如存在）

### 4. 允许的安全操作

- 运行 `git status` / `git diff` 检查工作区状态
- 运行 pytest smoke 测试（[`tests/test_cli_smoke.py`](tests/test_cli_smoke.py) 等）
- 运行 CLI `--self-test` 或 `--dry-run` 模式
- 轻量级语法检查（`python -m py_compile`）
- 只修改 harness 和文档文件（AGENTS.md、CURRENT_TASK.md、RUN_COMMANDS.md、REVIEW_CHECKLIST.md、AGENT_HANDOFF.md、CHANGELOG_AGENT.md、`.roomodes`、`.roo/rules/*`、`.roo/skills/*`）

### 5. Schema 保护清单

以下内容必须保持兼容性，如需修改需显式任务：

#### 5.1 CLI 参数

| CLI 入口 | 参数来源 |
|---|---|
| `jti-extract` | [`src/jti_extract/cli/extract.py`](src/jti_extract/cli/extract.py:908) — `--data`, `--ttbin`, `--prefer-ttbin`, `--max-events`, `--raw-ch-a-id`, `--raw-ch-b-id`, `--ch-a`, `--ch-b`, `--binwidth-ps`, `--dimensions`, `--frame-origin-ps`, `--scan-frame-origin`, `--frame-origin-start-ps`, `--frame-origin-stop-ps`, `--frame-origin-step-ps`, `--out`, `--no-csv`, `--npz`, `--plot`, `--background-subtract`, `--peak-align`, `--align-mode`, `--normalize`, `--prefix`, `--quiet`, `--self-test` [repo-verified] |
| `jti-schmidt` | [`src/jti_extract/cli/schmidt.py`](src/jti_extract/cli/schmidt.py:288) — `--input`, `--pattern`, `--recursive`, `--output`, `--threshold`, `--self-test` [repo-verified] |
| `jti-tdc-residue` | [`src/jti_extract/cli/tdc_residue.py`](src/jti_extract/cli/tdc_residue.py:212) — `--ttbin`, `--out`, `--ch1`, `--ch3`, `--modulus-ps`, `--coincidence-window-ps`, `--max-events`, `--probe-live-calibration` [repo-verified] |
| `jti-tdc-layer-scan` | [`src/jti_extract/cli/tdc_layer_scan.py`](src/jti_extract/cli/tdc_layer_scan.py:670) — `--ttbin`, `--out`, `--ch-a`, `--ch-b`, `--window-ps`, `--period-start-ps`, `--period-stop-ps`, `--period-step-ps`, `--hist-bin-ps`, `--time-splits`, `--surrogate-block-ms`, `--surrogate-shifts`, `--seed`, `--bin-widths-ps`, `--dims`, `--frame-origin-ps`, `--max-events`, `--skip-surrogates`, `--skip-folding` [repo-verified] |
| `scripts/run_type0ppln_pplus_auto_dim.py` | [`scripts/run_type0ppln_pplus_auto_dim.py`](scripts/run_type0ppln_pplus_auto_dim.py:1361) — `--data-root`, `--channels`, `--pairing-rule`, `--coincidence-window-ps`, `--bin-width-ps`, `--dims`, `--auto-dim`, `--auto-stop`, `--start-dim`, `--max-dim`, `--dim-growth`, `--jobs`, `--dense-profile-max-bins`, `--continue-from-existing`, `--min-next-dim`, `--high-dim-max-dim`, `--profile-storage`, `--diag-band-bins`, `--edge-bins-fraction`, `--edge-fraction-threshold`, `--stop-width-ratio`, `--stop-width-change`, `--dedupe-ttbin`, `--dry-run`, `--output-dir` [repo-verified] |

#### 5.2 CSV 输出格式

- **JTI counts CSV**: 由 `jti-extract` 生成；首行和首列为 bin 索引 [repo-verified via `docs/OUTPUTS.md`]
- **Schmidt summary CSV**: 由 `jti-schmidt` 生成 [repo-verified]
- **Type0ppln CSV 列定义**（由 [`SUMMARY_FIELDS`](scripts/run_type0ppln_pplus_auto_dim.py:34)、[`FILE_SUMMARY_FIELDS`](scripts/run_type0ppln_pplus_auto_dim.py:76)、[`DEDUPE_FIELDS`](scripts/run_type0ppln_pplus_auto_dim.py:93)、[`AUTO_DECISION_FIELDS`](scripts/run_type0ppln_pplus_auto_dim.py:104) 定义）[repo-verified]

#### 5.3 配置文件键

- [`configs/smoke.yaml`](configs/smoke.yaml): `data`, `binwidth_ps`, `dimensions`, `frame_origin_ps`, `out` [repo-verified]
- [`configs/type0ppln.yaml`](configs/type0ppln.yaml): `ttbin`, `ch_a`, `ch_b`, `window_ps` [repo-verified]
- [`configs/type2.yaml`](configs/type2.yaml): `ttbin`, `ch_a`, `ch_b`, `window_ps` [repo-verified]
- **注意**: 配置文件键可能不完全反映 CLI 全部参数；CLI 参数为 source of truth [repo-verified via smoke.yaml header comment]

#### 5.4 输出文件命名模式

- JTI counts CSV：`<prefix>counts.csv` 或 `<prefix><dim>x<dim>.counts.csv` [需验证完整 flag 组合]
- Schmidt summary：`jti_schmidt_summary.csv`（默认） [repo-verified]
- Type0ppln 输出目录：`pplus_auto_dim_YYYYMMDD_HHMMSS` [memory-derived, 需验证]
- Type0ppln profile CSV：`P_plus_<safe_file_stem>_dim<dim>.csv`、`P_minus_<safe_file_stem>_dim<dim>.csv` [memory-derived, 需验证]

### 6. 科学语义保护

- Schmidt number 和 singular spectrum weights 含义必须保持不变 [repo-verified]
- JTI raw counts CSV 数值必须保持不变 [repo-verified]
- TDC residue histograms 和 pairing-layer summaries 语义必须保持不变 [repo-verified]
- Type0ppln `P_plus_central_95_width_ps`、`width_ratio_95`、`edge_fraction`、`relative_change_W95`、`covered`、`final_status` 含义必须保持不变 [memory-derived, 需验证]

### 7. 项目结构速查

```
src/jti_extract/           # 安装包根（src layout）
  cli/                     # CLI 实现
    extract.py             # jti-extract 入口
    schmidt.py             # jti-schmidt 入口
    tdc_residue.py         # jti-tdc-residue 入口
    tdc_layer_scan.py      # jti-tdc-layer-scan 入口
  core/                    # 核心逻辑：binning, diagnostics, pairing, residue, schmidt
  io/                      # IO：csv, json, npz, paths, ttbin
  plotting/                # 绘图：heatmaps, residue_plots
jti_extract/__init__.py    # 开发垫片（重定向到 src/jti_extract/）
scripts/
  run_type0ppln_pplus_auto_dim.py  # Type0ppln P_plus 直接提取 / auto-dim 脚本
configs/                   # YAML 配置模板
tests/                     # pytest 测试与 fixtures
docs/                      # 文档
examples/tiny_run/         # 小型示例运行
```

### 8. 高风险变量

修改以下变量可能影响科学结果，任何修改必须显式任务授权：

- Channel IDs 和 channel 语义 [repo-verified]
- `coincidence_window_ps`、`bin_width_ps`、`dimensions` / `dim`、`frame_origin_ps`、`tau0_ps` [repo-verified]
- Pairing rule 和 duplicate-recording dedupe method [memory-derived, 需验证]
- Background subtraction 和 peak alignment 标志 [repo-verified]

### 9. 已知环境约束

- `*.ttbin` 工作流依赖 TimeTagger 绑定；在本项目 WSL Ubuntu 环境中，应通过 `~/envs/timetagger` 使用 pip 包 `Swabian-TimeTagger` [user-provided]
- TimeTagger 正确导入方式为 `from Swabian import TimeTagger`；如果旧代码包含 `import TimeTagger`，应改为 `from Swabian import TimeTagger`，并保持其余 API 调用不变（如 `TimeTagger.createTimeTagger()`、`TimeTagger.createTimeTaggerVirtual("file.ttbin")`）[user-provided]
- 禁止使用系统 `python3` 运行 TimeTagger 相关脚本，除非脚本明确与 TimeTagger 环境无关 [user-provided]
- `.ttbin` 回放或离线分析优先将数据放在 WSL ext4 文件系统，例如 `~/data/timetagger/`；避免在非必要情况下直接从 `/mnt/c` 或 `/mnt/d` 做重型 `.ttbin` 解析 [user-provided]
- 高维 Type0ppln `P_plus` 分析必须使用稀疏 profile 逻辑；dense `dim x dim` JTI 矩阵在高维下不可行 [memory-derived, 需验证]
- 完整数据处理读取大型时间标签文件，不应作为默认 smoke 测试启动 [memory-derived]
- Windows PowerShell 终端可能将 UTF-8 Markdown 显示为乱码；这是显示问题，非文件损坏 [repo-observed]
