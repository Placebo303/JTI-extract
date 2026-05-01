# RUN_COMMANDS.md

> 当前状态：Stage A-G (ultra core + CLI + hardening) 已实现。进入 Stage 0-2 combined validation。

## 安全命令（默认允许运行）

### Git 状态检查

```bash
# 检查工作区状态
git status

# 查看当前修改
git diff

# 查看暂存区修改
git diff --cached
```

### 安装与依赖检查

```bash
# 以可编辑模式安装（含开发依赖）
python -m pip install -e ".[dev]"

# 含 plotting 依赖安装
python -m pip install -e ".[plotting,dev]"

# 验证安装
python -c "import jti_extract; print('OK')"
```

### Smoke 测试

```bash
# CLI self-test（不依赖 TimeTagger 硬件）
python -m jti_extract.cli.extract --self-test
python -m jti_extract.cli.schmidt --self-test

# pytest smoke 测试
python -m pytest tests/test_cli_smoke.py -v
python -m pytest tests/test_io_contract.py -v
python -m pytest tests/test_binning.py -v
python -m pytest tests/test_pairing.py -v
python -m pytest tests/test_schmidt.py -v

# 全量 pytest（轻量，不含 ttbin）
python -m pytest tests/ -v
```

### TimeTagger 环境验证

```bash
# TimeTagger 工作流必须使用 WSL 虚拟环境；不要用系统 python3
source ~/envs/timetagger/bin/activate
python - <<'PY'
from Swabian import TimeTagger
print("TimeTagger imported.")
print("Version:", TimeTagger.getVersion())
print("Has virtual:", hasattr(TimeTagger, "createTimeTaggerVirtual"))
PY
```

### 运行 TimeTagger 相关脚本

```bash
# 推荐：先激活 TimeTagger 虚拟环境
source ~/envs/timetagger/bin/activate
python path/to/script.py

# 可选：直接使用 TimeTagger 虚拟环境 Python
~/envs/timetagger/bin/python path/to/script.py
```

### Type0ppln 脚本 dry-run

```bash
# dry-run 模式（不处理实际数据，需要有效的 DATA_ROOT 路径）
python scripts/run_type0ppln_pplus_auto_dim.py --dry-run --data-root <DATA_ROOT>
```

### 语法检查

```bash
# 逐文件语法编译
python -m py_compile src/jti_extract/cli/extract.py
python -m py_compile src/jti_extract/cli/schmidt.py
python -m py_compile src/jti_extract/cli/tdc_residue.py
python -m py_compile src/jti_extract/cli/tdc_layer_scan.py
python -m py_compile src/jti_extract/core/binning.py
python -m py_compile src/jti_extract/core/diagnostics.py
python -m py_compile src/jti_extract/core/pairing.py
python -m py_compile src/jti_extract/core/residue.py
python -m py_compile src/jti_extract/core/schmidt.py
python -m py_compile src/jti_extract/io/csv.py
python -m py_compile src/jti_extract/io/json.py
python -m py_compile src/jti_extract/io/npz.py
python -m py_compile src/jti_extract/io/paths.py
python -m py_compile src/jti_extract/io/ttbin.py
```

### Ultra fixed-lattice G2-like 模块语法检查

```bash
python -m py_compile src/jti_extract/ultra/__init__.py
python -m py_compile src/jti_extract/ultra/fold_lattice.py
python -m py_compile src/jti_extract/ultra/g2_accumulate.py
python -m py_compile src/jti_extract/ultra/accumulators.py
python -m py_compile src/jti_extract/ultra/diagnostics_pairing.py
python -m py_compile src/jti_extract/ultra/svd_estimators.py
python -m py_compile src/jti_extract/ultra/sweep_ultra_jti.py
python -m py_compile src/jti_extract/ultra/io_ultra.py
python -m py_compile src/jti_extract/ultra/ttbin_adapter.py
python -m py_compile src/jti_extract/ultra/cli_ultra.py
python -m py_compile src/jti_extract/ultra/cross_validate.py
```

### Ultra fixed-lattice G2-like 模块单元测试

```bash
python -m pytest tests/test_ultra_lattice.py -v
python -m pytest tests/test_ultra_accumulators.py -v
python -m pytest tests/test_ultra_diagnostics_pairing.py -v
python -m pytest tests/test_ultra_svd_estimators.py -v
python -m pytest tests/test_ultra_sweep_orchestration.py -v
python -m pytest tests/test_ultra_io.py -v
python -m pytest tests/test_ultra_cross_validate.py -v
```

---

## Stage 0-2 combined validation

Stage E/F/G real-data enablement **已实现**。当前进入 Stage 0-2 的首轮受限验证。

### 语法检查

```bash
~/envs/jti_dev/bin/python -m py_compile src/jti_extract/ultra/cli_ultra.py
~/envs/jti_dev/bin/python -m py_compile src/jti_extract/ultra/cross_validate.py
~/envs/jti_dev/bin/python -m py_compile src/jti_extract/ultra/io_ultra.py
~/envs/jti_dev/bin/python -m py_compile src/jti_extract/ultra/ttbin_adapter.py
~/envs/jti_dev/bin/python -m py_compile src/jti_extract/ultra/sweep_ultra_jti.py
```

### Ultra 模块单元测试

```bash
~/envs/jti_dev/bin/python -m pytest tests/test_ultra_lattice.py tests/test_ultra_accumulators.py tests/test_ultra_diagnostics_pairing.py tests/test_ultra_svd_estimators.py tests/test_ultra_sweep_orchestration.py tests/test_ultra_io.py tests/test_ultra_cross_validate.py tests/test_ultra_cli_params.py -v
```

### CLI self-test

```bash
~/envs/jti_dev/bin/python -m jti_extract.ultra.cli_ultra --self-test
```

### TimeTagger FileReader 离线读取验证

```bash
# .ttbin 离线读取应使用 FileReader，而不是 createTimeTaggerVirtual
source ~/envs/timetagger/bin/activate
~/envs/timetagger/bin/python - <<'PY'
from Swabian import TimeTagger
reader = TimeTagger.FileReader('/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin')
print('FileReader hasData:', reader.hasData())
PY
```

### ultra TTBIN adapter 回归测试

```bash
# 验证 ttbin_adapter 使用 FileReader 并过滤 event_types == 0
~/envs/jti_dev/bin/python -m pytest tests/test_ultra_ttbin_adapter.py -q
```

### Stage 1: 小规模 exact 对齐（使用预加载 `.npy` 文件）

```bash
~/envs/jti_dev/bin/python -m jti_extract.ultra.cli_ultra \
  --t-a <T_A_NPY> \
  --t-b <T_B_NPY> \
  --n-bins 1024 \
  --binwidth-ps 100 \
  --frame-origin-ps 0 \
  --coincidence-window-ps 200 \
  --edge-guard-ps 200 \
  --coarse-n-bins 64 \
  --out <NEW_OUTPUT_DIR>
```

必须在 `--out` 指定全新目录；禁止覆盖已有结果。

### Stage 2: origin / edge guard 灵敏度验证

```bash
~/envs/jti_dev/bin/python -m jti_extract.ultra.cli_ultra \
  --t-a <T_A_NPY> \
  --t-b <T_B_NPY> \
  --n-bins 1024 \
  --binwidth-ps 100 \
  --frame-origin-ps 0 \
  --coincidence-window-ps 200 \
  --edge-guard-ps 200 \
  --origin-sensitivity 25600 51200 76800 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 64 \
  --out <NEW_OUTPUT_DIR>
```

### `.ttbin` 模式（仅确认 TimeTagger 环境后运行）

```bash
~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin <TTBIN_PATH> \
  --ch-a <CH_A> \
  --ch-b <CH_B> \
  --max-events <SMALL_LIMIT> \
  --n-bins 1024 \
  --binwidth-ps 100 \
  --coincidence-window-ps 200 \
  --edge-guard-ps 200 \
  --coarse-n-bins 64 \
  --out <NEW_OUTPUT_DIR>
```

---

### Stage 3: 中维度 coverage sweep（受控运行）

```bash
# Stage 3 smoke: N=8192, coarse_N=1024, 全新 /tmp 输出目录
~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 10000 \
  --n-bins 8192 --binwidth-ps 100 --frame-origin-ps 0 \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --origin-sensitivity 204800 409600 614400 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 1024 \
  --out /tmp/ultra_stage3_smoke_$(date +%Y%m%d_%H%M%S)

# Stage 3 grid point: N=16384, coarse_N=2048
~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 10000 \
  --n-bins 16384 --binwidth-ps 100 --frame-origin-ps 0 \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --origin-sensitivity 409600 819200 1228800 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 2048 \
  --out /tmp/ultra_stage3_N16384_$(date +%Y%m%d_%H%M%S)

# Stage 3 grid point: N=32768, coarse_N=4096
~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 10000 \
  --n-bins 32768 --binwidth-ps 100 --frame-origin-ps 0 \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --origin-sensitivity 819200 1638400 2457600 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 4096 \
  --out /tmp/ultra_stage3_N32768_$(date +%Y%m%d_%H%M%S)
```

必须在 `--out` 指定全新目录；禁止覆盖已有结果。

### Stage 4: pump coherence horizon sweep

基于 Stage 3 结果（`K_coarse` 在 N=32768 时约 493，尚未饱和），建议直接使用单点验证。

```bash
# Stage 4 single point: N=100000, coarse_N=8192, 直接检查运行时间、内存、K_coarse 趋势
~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 10000 \
  --n-bins 100000 --binwidth-ps 100 --frame-origin-ps 0 \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --origin-sensitivity 2500000 5000000 7500000 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 8192 --truncated-rank 256 \
  --out /tmp/ultra_stage4_N100k_$(date +%Y%m%d_%H%M%S)
```

注意：`N=300000`（coarse_N=16384）需要显式确认后才能运行，不属于默认验证范围。

### Stage 5A-E: 全步骤一次执行规划

基于 Stage 3–4 的 `K_coarse` 先上升后回落的趋势，在 `N=32768` 与 `N=100000` 之间填充精细网格，并检查 `coarse_N` 和 `truncated_rank` 稳定性。

**执行顺序（串行，每点独立 `/tmp/ultra_stage5*` 新目录）：**

```bash
# ===== 0. 运行前轻量验证 =====
~/envs/timetagger/bin/python -m pytest tests/test_ultra_lattice.py tests/test_ultra_accumulators.py tests/test_ultra_svd_estimators.py tests/test_ultra_sweep_orchestration.py tests/test_ultra_cli_params.py -v

~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra --self-test

# ===== B1. frame-length refinement: N=49152, c4096, r512 =====
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 10000 \
  --n-bins 49152 --binwidth-ps 100 --frame-origin-ps 0 \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --origin-sensitivity 1228800 2457600 3686400 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 4096 --truncated-rank 512 \
  --out /tmp/ultra_stage5B_N49152_c4096_r512_$(date +%Y%m%d_%H%M%S)

# ===== B2. frame-length refinement: N=65536, c4096, r512 =====
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 10000 \
  --n-bins 65536 --binwidth-ps 100 --frame-origin-ps 0 \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --origin-sensitivity 1638400 3276800 4915200 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 4096 --truncated-rank 512 \
  --out /tmp/ultra_stage5B_N65536_c4096_r512_$(date +%Y%m%d_%H%M%S)

# ===== B3. frame-length refinement: N=81920, c4096, r512 =====
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 10000 \
  --n-bins 81920 --binwidth-ps 100 --frame-origin-ps 0 \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --origin-sensitivity 2048000 4096000 6144000 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 4096 --truncated-rank 512 \
  --out /tmp/ultra_stage5B_N81920_c4096_r512_$(date +%Y%m%d_%H%M%S)

# ===== C1. coarse_N sensitivity: N=65536, c2048, r512 =====
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 10000 \
  --n-bins 65536 --binwidth-ps 100 --frame-origin-ps 0 \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --origin-sensitivity 1638400 3276800 4915200 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 2048 --truncated-rank 512 \
  --out /tmp/ultra_stage5C_N65536_c2048_r512_$(date +%Y%m%d_%H%M%S)

# ===== C3. coarse_N sensitivity: N=65536, c8192, r512 =====
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 10000 \
  --n-bins 65536 --binwidth-ps 100 --frame-origin-ps 0 \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --origin-sensitivity 1638400 3276800 4915200 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 8192 --truncated-rank 512 \
  --out /tmp/ultra_stage5C_N65536_c8192_r512_$(date +%Y%m%d_%H%M%S)

# ===== C4. coarse_N sensitivity: N=100000, c4096, r512 =====
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 10000 \
  --n-bins 100000 --binwidth-ps 100 --frame-origin-ps 0 \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --origin-sensitivity 2500000 5000000 7500000 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 4096 --truncated-rank 512 \
  --out /tmp/ultra_stage5C_N100000_c4096_r512_$(date +%Y%m%d_%H%M%S)

# ===== D1. truncated_rank sensitivity: N=65536, c4096, r256 =====
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 10000 \
  --n-bins 65536 --binwidth-ps 100 --frame-origin-ps 0 \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --origin-sensitivity 1638400 3276800 4915200 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 4096 --truncated-rank 256 \
  --out /tmp/ultra_stage5D_N65536_c4096_r256_$(date +%Y%m%d_%H%M%S)

# ===== E1. higher-statistics resource diag: N=65536, c4096, r512, max_events=30000 =====
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 30000 \
  --n-bins 65536 --binwidth-ps 100 --frame-origin-ps 0 \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --origin-sensitivity 1638400 3276800 4915200 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 4096 --truncated-rank 512 \
  --out /tmp/ultra_stage5E_N65536_c4096_r512_max30000_$(date +%Y%m%d_%H%M%S)
```

#### Stage 5A-E 已执行输出目录

| 点 | 输出目录 |
|---|---|
| B1 | `/tmp/ultra_stage5B_N49152_c4096_r512_20260430_184215/` |
| B2 | `/tmp/ultra_stage5B_N65536_c4096_r512_20260430_184341/` |
| B3 | `/tmp/ultra_stage5B_N81920_c4096_r512_20260430_184442/` |
| C1 | `/tmp/ultra_stage5C_N65536_c2048_r512_20260430_184545/` |
| C3 | `/tmp/ultra_stage5C_N65536_c8192_r512_20260430_184550/` |
| C4 | `/tmp/ultra_stage5C_N100000_c4096_r512_20260430_185404/` |
| D1 | `/tmp/ultra_stage5D_N65536_c4096_r256_20260430_185504/` |
| E1 | `/tmp/ultra_stage5E_N65536_c4096_r512_max30000_20260430_185602/` |

以上命令已执行，结果标记为 exploratory diagnostic。不得修改已有 Stage 4 命令、CLI 参数名、输出字段名或 schema。

### Stage 6A-recheck: JSON field propagation + sparse-occupancy sanity gate（✅ 已完成）

Stage 6A-recheck 已成功运行并验证：
- 输出目录：[`/tmp/ultra_stage6A_recheck_jsonwidth_N65536_c4096_r1024_max100000_20260430_195256/`](file:///tmp/ultra_stage6A_recheck_jsonwidth_N65536_c4096_r1024_max100000_20260430_195256/)
- JSON 主点含 `diag_profile_*` 字段：✅
- CSV schema 未扩展：✅
- `K_coarse=2245.71` 仍不满足收敛：❌

### Stage 7: linewidth-informed coherence-horizon sanity sweep（✅ 已完成）

> S7-A（N=32768, 3.28 µs）、S7-B（复用 Stage 6A-recheck）、S7-C（N=100000, 10 µs）已于 2026-04-30 全部运行成功。
>
> 关键结果：
> - `diag_profile_mass_width_95_bins = 2`（200 ps）三点稳定
> - `captured_frobenius_energy_r ≈ 0.55`
> - `svd_nonzero_bins / n_candidates ≈ 0.57`（sparse dominated）

### Stage 8: high-linewidth short-horizon scan（✅ 已完成）

基于几百 kHz 线宽先验（coherence horizon 可能短至 ~0.6–3.3 µs），需补扫短帧梯度。

**固定配置**：
- `binwidth_ps=100`、`max_events=100000`、`coarse_n_bins=4096`、`truncated_rank=1024`
- `coincidence_window_ps=200`、`edge_guard_ps=200`

**Sweep 点**：

| 点 | N | frame_length | 来源 |
|:---|---:|---|:---|
| S8-A | 8192 | 0.819 µs | **新增运行** |
| S8-B | 16384 | 1.638 µs | **新增运行** |
| S8-C | 24576 | 2.458 µs | **新增运行** |
| S8-D | 32768 | 3.277 µs | **复用** [`Stage 7 S7-A`](file:///tmp/ultra_stage7_linewidth_N32768_c4096_r1024_max100000_20260430_200142/) |

#### 运行前轻量验证

```bash
~/envs/timetagger/bin/python -m pytest tests/test_ultra_accumulators.py tests/test_ultra_sweep_orchestration.py -v
~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra --self-test
```

#### S8-A（N=8192, 0.819 µs）

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

#### S8-B（N=16384, 1.638 µs）

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

#### S8-C（N=24576, 2.458 µs）

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

#### Stage 8 判据

**A. Local width 与几百 kHz 先验的一致性**：`diag_profile_mass_width_95_ps` 在 0.819–3.277 µs 间相对变化 < 20% 且 `width95_ps < 0.3 × frame_length_ps`

**B. Sparse occupancy**：`svd_nonzero_bins / n_candidates > 0.3 → sparse dominated`

**C. Full certification 门槛**（必须全部满足才能进入 Stage 6B）：
1. `K_coarse` 相邻变化 < 20%
2. `origin_sensitivity_K_max_rel ≤ 5%`
3. `edge_rejection_ratio ≤ 2%`
4. `captured_frobenius_energy_r ≥ 0.9`
5. CSV schema 不变

#### 预期结论

```text
✅ local diagonal width: stable across 0.82–10 µs（符合几百 kHz 先验）
⚠️ K_coarse / full effective dimension: not certified（sparse + truncated energy）
```

任务定义见 [`CURRENT_TASK.md`](CURRENT_TASK.md:490) Stage 8 节。

### Stage 9: diagonal-ridge localization（✅ 已完成）

#### 运行前轻量验证

```bash
~/envs/timetagger/bin/python -m pytest tests/test_ultra_accumulators.py tests/test_ultra_sweep_orchestration.py -v
~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra --self-test
```

#### S9: real-data diag-center diagnostic（复用 S8-A 参数，N=8192）

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

#### 判据

- `diag_center_peak_time_ps` 在 frame 中心 1/3–2/3 区域
- `diag_center_edge_fraction < 0.3`
- `diag_center_mass_width_95_ps / frame_length_ps < 0.5`
- CSV schema 不变

任务定义见 [`CURRENT_TASK.md`](CURRENT_TASK.md:743) Stage 9 节。

---

## Stage 10-12 运行命令

### 运行前轻量验证

```bash
~/envs/timetagger/bin/python -m pytest tests/test_ultra_accumulators.py tests/test_ultra_sweep_orchestration.py -v
~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra --self-test
```

### Stage 10.3: origin recentering sweep

```bash
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 100000 \
  --n-bins 8192 --binwidth-ps 100 --frame-origin-ps 0 \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --origin-sensitivity -300000 -250000 -200000 -189450 -150000 -100000 -50000 50000 204800 409600 614400 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 4096 --truncated-rank 1024 \
  --out /tmp/ultra_stage10_origin_recenter_N8192_c4096_r1024_max100000_$(date +%Y%m%d_%H%M%S)
```

### Stage 10.4: frame-length containment sweep

对每个 N 单独运行：

```bash
# N=12288（1.2288 µs）
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 100000 \
  --n-bins 12288 --binwidth-ps 100 --frame-origin-ps <APPROVED_ORIGIN_PS> \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 4096 --truncated-rank 1024 \
  --out /tmp/ultra_stage10_frame_length_N12288_c4096_r1024_max100000_$(date +%Y%m%d_%H%M%S)

# N=16384（1.6384 µs）
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 100000 \
  --n-bins 16384 --binwidth-ps 100 --frame-origin-ps <APPROVED_ORIGIN_PS> \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 4096 --truncated-rank 1024 \
  --out /tmp/ultra_stage10_frame_length_N16384_c4096_r1024_max100000_$(date +%Y%m%d_%H%M%S)

# N=24576（2.4576 µs）
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 100000 \
  --n-bins 24576 --binwidth-ps 100 --frame-origin-ps <APPROVED_ORIGIN_PS> \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 4096 --truncated-rank 1024 \
  --out /tmp/ultra_stage10_frame_length_N24576_c4096_r1024_max100000_$(date +%Y%m%d_%H%M%S)

# N=32768（3.2768 µs）
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 100000 \
  --n-bins 32768 --binwidth-ps 100 --frame-origin-ps <APPROVED_ORIGIN_PS> \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 4096 --truncated-rank 1024 \
  --out /tmp/ultra_stage10_frame_length_N32768_c4096_r1024_max100000_$(date +%Y%m%d_%H%M%S)
```

### Stage 10.5: max_events convergence

```bash
# N=8192, max_events=300000
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 300000 \
  --n-bins 8192 --binwidth-ps 100 --frame-origin-ps <APPROVED_ORIGIN_PS> \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 4096 --truncated-rank 1024 \
  --out /tmp/ultra_stage10_maxevents_N8192_c4096_r1024_max300000_$(date +%Y%m%d_%H%M%S)

# N=16384, max_events=300000
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 300000 \
  --n-bins 16384 --binwidth-ps 100 --frame-origin-ps <APPROVED_ORIGIN_PS> \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 4096 --truncated-rank 1024 \
  --out /tmp/ultra_stage10_maxevents_N16384_c4096_r1024_max300000_$(date +%Y%m%d_%H%M%S)

# N=8192 max_events=500000
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 500000 \
  --n-bins 8192 --binwidth-ps 100 --frame-origin-ps <APPROVED_ORIGIN_PS> \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 4096 --truncated-rank 1024 \
  --out /tmp/ultra_stage10_maxevents_N8192_c4096_r1024_max500000_$(date +%Y%m%d_%H%M%S)

# N=16384 max_events=500000
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 500000 \
  --n-bins 16384 --binwidth-ps 100 --frame-origin-ps <APPROVED_ORIGIN_PS> \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 4096 --truncated-rank 1024 \
  --out /tmp/ultra_stage10_maxevents_N16384_c4096_r1024_max500000_$(date +%Y%m%d_%H%M%S)
```

### Stage 12.1: 小维度 exact SVD validation

```bash
# N=4096, exact dense (coarse_n_bins=N, truncated_rank=0)
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 100000 \
  --n-bins 4096 --binwidth-ps 100 --frame-origin-ps <APPROVED_ORIGIN_PS> \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --coarse-n-bins 4096 --truncated-rank 0 \
  --out /tmp/ultra_stage12_exact_N4096_c4096_max100000_$(date +%Y%m%d_%H%M%S)
```

### Stage 12.2: coarse_N sensitivity sample

```bash
# N=16384, coarse_N=8192
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 100000 \
  --n-bins 16384 --binwidth-ps 100 --frame-origin-ps <APPROVED_ORIGIN_PS> \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --coarse-n-bins 8192 --truncated-rank 1024 \
  --out /tmp/ultra_stage12_coarseN_N16384_c8192_r1024_max100000_$(date +%Y%m%d_%H%M%S)
```

### Stage 12 判据

- 主结果 duration：`diag_center_circular_mass_width_95_ps` 稳定不随 N/max_events/origin 大幅波动
- SVD 认证门槛：`captured_frobenius_energy_r ≥ 0.9`、`K_coarse` 趋于稳定、bootstrap_K_relative_std < 10–20%
- CSV schema 不变
- Bootstrap certification 必须等待 proper block bootstrap 实现后使用

---

## Stage 13-19 运行命令

### 运行前轻量验证

```bash
~/envs/timetagger/bin/python -m pytest tests/test_ultra_cli_params.py tests/test_ultra_accumulators.py -v
~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra --self-test
```

### Stage 13A: reproducibility check（N=32768 profile-only）

```bash
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 100000 \
  --n-bins 32768 --binwidth-ps 100 --frame-origin-ps 0 \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --origin-sensitivity 819200 1638400 2457600 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 4096 \
  --profile-only \
  --out /tmp/ultra_stage13A_repro_N32768_profile_$(date +%Y%m%d_%H%M%S)
```

**验收**：circular mass_width95 ≈ 3125500 ps，JSON 不含 K_coarse。

### Stage 13B: 100 µs upper-bound probe

```bash
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 100000 \
  --n-bins 1000000 --binwidth-ps 100 --frame-origin-ps 0 \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --origin-sensitivity 25000000 50000000 75000000 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 4096 \
  --profile-only \
  --out /tmp/ultra_stage13B_upper_bound_N1000000_profile_$(date +%Y%m%d_%H%M%S)
```

### Stage 14: containment sweep

```bash
# N=100000 (10 µs)
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 100000 \
  --n-bins 100000 --binwidth-ps 100 --frame-origin-ps 0 \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --origin-sensitivity 2500000 5000000 7500000 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 4096 \
  --profile-only \
  --out /tmp/ultra_stage14_containment_N100000_profile_$(date +%Y%m%d_%H%M%S)

# N=300000 (30 µs)
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 100000 \
  --n-bins 300000 --binwidth-ps 100 --frame-origin-ps 0 \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --origin-sensitivity 7500000 15000000 22500000 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 4096 \
  --profile-only \
  --out /tmp/ultra_stage14_containment_N300000_profile_$(date +%Y%m%d_%H%M%S)

# N=500000 (50 µs)
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 100000 \
  --n-bins 500000 --binwidth-ps 100 --frame-origin-ps 0 \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --origin-sensitivity 12500000 25000000 37500000 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 4096 \
  --profile-only \
  --out /tmp/ultra_stage14_containment_N500000_profile_$(date +%Y%m%d_%H%M%S)
```

### Stage 15: 二分搜索（示例 N=150000/200000/250000/300000）

```bash
for N in 150000 200000 250000 300000; do
  T4=$((N * 25))
  T2=$((N * 50))
  T34=$((N * 75))
  /usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
    --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
    --ch-a 1 --ch-b 3 --max-events 100000 \
    --n-bins $N --binwidth-ps 100 --frame-origin-ps 0 \
    --coincidence-window-ps 200 --edge-guard-ps 200 \
    --origin-sensitivity $T4 $T2 $T34 \
    --edge-guard-sensitivity 100 200 300 \
    --coarse-n-bins 4096 \
    --profile-only \
    --out /tmp/ultra_stage15_binary_N${N}_profile_$(date +%Y%m%d_%H%M%S)
done
```

### Stage 16: max_events convergence（在候选 N 下）

```bash
for ME in 300000 500000; do
  /usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
    --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
    --ch-a 1 --ch-b 3 --max-events $ME \
    --n-bins <CONTAINMENT_N> --binwidth-ps 100 --frame-origin-ps <APPROVED_ORIGIN> \
    --coincidence-window-ps 200 --edge-guard-ps 200 \
    --coarse-n-bins 4096 \
    --profile-only \
    --out /tmp/ultra_stage16_maxevents_N<CONTAINMENT_N>_max${ME}_$(date +%Y%m%d_%H%M%S)
done
```

### Stage 17A: coarse_N sensitivity（仅 containment 后）

```bash
for CN in 1024 2048 4096 8192; do
  /usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
    --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
    --ch-a 1 --ch-b 3 --max-events 100000 \
    --n-bins <CONTAINMENT_N> --binwidth-ps 100 --frame-origin-ps <APPROVED_ORIGIN> \
    --coincidence-window-ps 200 --edge-guard-ps 200 \
    --coarse-n-bins $CN --truncated-rank 1024 \
    --out /tmp/ultra_stage17_coarse_N<CONTAINMENT_N>_c${CN}_r1024_max100000_$(date +%Y%m%d_%H%M%S)
done
```

### Stage 17B: truncated-rank convergence

```bash
for R in 512 1024 2048 4096; do
  /usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
    --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
    --ch-a 1 --ch-b 3 --max-events 100000 \
    --n-bins <CONTAINMENT_N> --binwidth-ps 100 --frame-origin-ps <APPROVED_ORIGIN> \
    --coincidence-window-ps 200 --edge-guard-ps 200 \
    --coarse-n-bins <BEST_COARSE_N> --truncated-rank $R \
    --out /tmp/ultra_stage17_trunc_r${R}_N<CONTAINMENT_N>_c<BEST_COARSE_N>_$(date +%Y%m%d_%H%M%S)
done
```

### Stage 19: 若 100 µs 仍未 containment——继续上探

```bash
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 100000 \
  --n-bins 2000000 --binwidth-ps 100 --frame-origin-ps 0 \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --origin-sensitivity 50000000 100000000 150000000 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 4096 \
  --profile-only \
  --out /tmp/ultra_stage19_upper_N2000000_profile_$(date +%Y%m%d_%H%M%S)
```

---

## Stage 20-24 运行命令

### 前置验证

```bash
~/envs/timetagger/bin/python -m pytest tests/test_ultra_contrast_profiles.py \
  tests/test_ultra_aperture_select.py \
  tests/test_ultra_aperture_jti.py \
  tests/test_ultra_surrogate_controls.py -v
~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra --self-test
```

### Stage 20: contrast profile 第一轮（N=100k/300k/500k/1M, M=512/1024）

```bash
# N=300000 示例
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 100000 \
  --n-bins 300000 --binwidth-ps 100 --frame-origin-ps 0 \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --contrast-profile --contrast-window-ps 3000 \
  --on-diag-band-bins 2 --bg-inner-bins 10 --bg-outer-bins 30 \
  --center-coarse-bins 512 1024 \
  --profile-only \
  --out /tmp/ultra_stage20_N300000_contrast_$(date +%Y%m%d_%H%M%S)

# N=1000000 示例
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 100000 \
  --n-bins 1000000 --binwidth-ps 100 --frame-origin-ps 0 \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --contrast-profile --contrast-window-ps 3000 \
  --on-diag-band-bins 2 --bg-inner-bins 10 --bg-outer-bins 30 \
  --center-coarse-bins 512 1024 \
  --profile-only \
  --out /tmp/ultra_stage20_N1000000_contrast_$(date +%Y%m%d_%H%M%S)
```

### Stage 21: aperture selection（在最有希望的 N 上）

```bash
~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 100000 \
  --n-bins 300000 --binwidth-ps 100 --frame-origin-ps 0 \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --contrast-profile --contrast-window-ps 3000 \
  --on-diag-band-bins 2 --bg-inner-bins 10 --bg-outer-bins 30 \
  --center-coarse-bins 512 1024 \
  --select-aperture --aperture-threshold snr5 \
  --aperture-min-run-segments 3 --aperture-max-gap-segments 1 \
  --profile-only \
  --out /tmp/ultra_stage21_N300000_aperture_$(date +%Y%m%d_%H%M%S)
```

### Stage 22: aperture JTI reconstruction（仅在稳定 aperture 上执行，通过代码调用）

### Stage 23A: coarse_N sensitivity

```bash
for CN in 512 1024 2048 4096 8192; do
  /usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
    --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
    --ch-a 1 --ch-b 3 --max-events 100000 \
    --n-bins <APERTURE_N_BINS> --binwidth-ps 100 --frame-origin-ps <APERTURE_ORIGIN_PS> \
    --coincidence-window-ps 200 --edge-guard-ps 200 \
    --coarse-n-bins $CN --truncated-rank 1024 \
    --aperture-schmidt \
    --out /tmp/ultra_stage23_coarse_N<APERTURE_N>_c${CN}_$(date +%Y%m%d_%H%M%S)
done
```

### Stage 24: surrogate controls

```bash
# time-shift surrogate: shift=100 ns
~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 100000 \
  --n-bins 300000 --binwidth-ps 100 \
  --contrast-profile --contrast-window-ps 3000 \
  --on-diag-band-bins 2 --bg-inner-bins 10 --bg-outer-bins 30 \
  --center-coarse-bins 512 \
  --surrogate-shifts-ps 10000 100000 1000000 \
  --profile-only \
  --out /tmp/ultra_stage24_surrogate_N300000_$(date +%Y%m%d_%H%M%S)
```

---

## Do not run by default（重型命令，需显式确认后运行）

### JTI 提取（完整数据集）

```bash
# candidate command, verify before running
# 完整 JTI 提取（可能处理大文件，耗时较长）
jti-extract --data <DATASET_PATH> --binwidth-ps <BINWIDTH> --dimensions <DIM> --frame-origin-ps 0 --out <OUTPUT_DIR>
```

### Schmidt 分析（批量处理）

```bash
# candidate command, verify before running
# 递归 Schmidt 分析（可能处理大量文件）
jti-schmidt --input <RESULTS_DIR> --recursive --output <OUTPUT_CSV>
```

### TDC residue 诊断

```bash
# candidate command, verify before running
# TDC residue 诊断（需要 TimeTagger 绑定，可能处理大文件）
jti-tdc-residue --ttbin <TTBIN_PATH> --out <OUTPUT_DIR> --ch1 <CH1> --ch3 <CH3>
```

### TDC layer scan

```bash
# candidate command, verify before running
# TDC layer scan（含 surrogates，可能运行时间长）
jti-tdc-layer-scan --ttbin <TTBIN_PATH> --out <OUTPUT_DIR> --ch-a <CHA> --ch-b <CHB> --window-ps <WINDOW>
```

### Type0ppln P_plus auto-dim（完整运行）

```bash
# candidate command, verify before running
# 高维 P_plus 分析（可能运行数小时，输出大量文件）
python scripts/run_type0ppln_pplus_auto_dim.py \
    --data-root <DATA_ROOT> \
    --auto-dim \
    --high-dim-max-dim 65536 \
    --jobs <N_JOBS> \
    --output-dir <OUTPUT_DIR>
```

### Ultra-high-dimensional JTI sweep（ARCHIVED）

```bash
# ARCHIVED: The ultra JTI frame-length exploration is closed.
# Do not continue Stage 26/27 or aperture-conditioned Schmidt runs
# under the current contrast metric.
# See docs/ULTRA_JTI_FRAME_LENGTH_CLOSURE_REPORT.md for the full closure report.
# The diagnostic toolchain remains available for reuse, but any new experiment
# must be opened as a new task with a new task definition.
```

---

## 路径约定

- 使用 POSIX 路径格式
- `<DATA_ROOT>`：外部数据根目录（需确认 WSL 挂载路径）
- TimeTagger 虚拟环境：`~/envs/timetagger`；Python 可执行文件：`~/envs/timetagger/bin/python`
- `.ttbin` 回放或离线分析优先使用 WSL ext4 路径，例如 `~/data/timetagger/`
- 避免在非必要情况下直接从 `/mnt/c` 或 `/mnt/d` 做重型 `.ttbin` 解析
- 旧 Windows 路径（如 `D:\Data\Raw Data\Type0ppln JTI`）标注为 `legacy Windows path`，不作为默认执行路径
- 输出目录应使用时间戳命名，如 `pplus_auto_dim_YYYYMMDD_HHMMSS`
- `scripts/run_type0ppln_pplus_auto_dim.py` 的 `DEFAULT_DATA_ROOT` 为 Windows 路径，在 WSL 中必须显式传入 POSIX 路径
