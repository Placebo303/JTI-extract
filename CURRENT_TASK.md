# CURRENT_TASK.md

## 任务状态

- Stage 0–8: ✅ 全部完成
- Stage 6B: ✅ 已完成 — 最终汇总与可信度判断
- Stage 9: ✅ 已完成 — `diag_center_*` 字段实现 + 代码验证 + 真实数据诊断(linear center)
- **Stage 10: ✅ 已完成 — circular-center diagnostic + origin recentering + frame-length/max_events sweep + method sensitivity**
- **Stage 11: ✅ 已完成 — duration → time-bin span 换算（frame-containment limited）**
- **Stage 12: ✅ 已完成 — Schmidt-like 认证尝试（SVD/truncated/bootstrap）**
- **Bug fix: ✅ 已完成 — circular-center direction asymmetry 修复 + circular minimal-arc width 新增**

### 最终档位：⚠️ folded center-profile width stable, physical duration not certified

- ✅ local diagonal profile width ≈ 200 ps — credible diagnostic
- ✅ diag_center_* ridge localization — implemented + verified
- ✅ diag_center_circular_* — implemented + verified（含 reverse-wrap 修复）
- ✅ diag_center_circular_min_arc_width_* — torus-aware minimal arc width 新增
- ✅ folded center-profile width 对 origin/method/bootstrap 高度稳定
- ⚠️ width95 受 frame-containment 限制（~94.4% of frame_length）
- ⚠️ K_coarse / full effective dimension — not certified（sparse-dominated）
- ❌ full Schmidt-number certification — not supported by current data
- ❌ 0.774 µs 作为物理持续时间 — 是 frame-containment artifact，不是 certified duration
---

## Goal

完成整个项目的最终闭环：从高维 sweep 探索性结果推进到“能否给出可信的对角线长度范围 / effective dimension 判断”。

当前四个 blocker（源自 Stage 5A-E 验证结果；Stage 6A 审查对 diagonal width blocker 有更新）：

| blocker | 当前状态 | 位置 |
|---|---|---|
| `coarse_N` 未收敛 | 跨度约 25.8% | [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md:1344) |
| `max_events` 未收敛 | K 从 480 → 1135 → 2246 | [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md:1345) |
| truncated SVD 能量不足 | r=1024 仅 55.2% | [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md:1346) |
| diagonal width 字段代码已实现，但旧 Stage 6A 输出 JSON 缺字段（sweep 层传播 patch 后未重跑） | accumulator 已实现 `_quantile_width()` + `summary()` 新字段；`run_synthetic_sweep_point()` 已合并 `acc.summary()`；但旧 `/tmp/ultra_stage6A_20260430_193527/` 运行于 patch 之前，JSON 不含 `diag_profile_*` | 见审查结论 |
| **新发现：sparse occupancy 主导** | `K_coarse` 随 `n_candidates_after_edge_guard`（539→1583→5213）线性增长，`svd_nonzero_bins` 与候选数同量级，当前 regime 还不是物理维度收敛区间 | 见审查结论 |

Stage 6A code patch 已完成但旧实验输出缺 diagonal-width 字段——需要 Stage 6A-recheck 重跑确认 field propagation，再判断是否允许进入 Stage 6B。

---

## Key Scientific Decisions

1. **Fixed global frame lattice**: 主流程使用固定 `frame_origin_ps`，不允许 per-pair origin。
2. **Edge guard**: 主 JTI 使用 `edge_guard_ps` 剔除边界候选；边界诊断与 origin sensitivity 分开报告。
3. **G2-like all-candidate accumulation**: 主结果；strict / nearest / greedy 只作为 diagnostic。
4. **Background subtraction**: 主结果保持 raw nonnegative counts，不默认扣除 background。
5. **Coarse / truncated SVD**: 高维使用 coarse JTI（`coarse_n_bins` < `n_bins`）做 SVD；可选 truncated SVD + `captured_frobenius_energy_r` 报告。
6. **Bootstrap**: 使用 block bootstrap（`block_size` / `n_resamples`）估计 K 的不确定性。
7. **Diagonal profile width**: Stage 6A 新增 JSON-only `diag_profile_mass_width_90/95`，不改 CSV schema。
8. **`P_plus`**: 只作为 acquisition stability 辅助证据。

---

## Allowed Files

### Stage 6A 允许修改
- [`CURRENT_TASK.md`](CURRENT_TASK.md) — 本文件
- [`RUN_COMMANDS.md`](RUN_COMMANDS.md)
- [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md)
- [`src/jti_extract/ultra/accumulators.py`](src/jti_extract/ultra/accumulators.py:168) — summary 新增 JSON-only profile width diagnostic
- [`src/jti_extract/ultra/sweep_ultra_jti.py`](src/jti_extract/ultra/sweep_ultra_jti.py:28) — 在 sweep point summary 中附加 profile width
- [`tests/test_ultra_accumulators.py`](tests/test_ultra_accumulators.py:181) — 新增 profile width 测试
- [`tests/test_ultra_sweep_orchestration.py`](tests/test_ultra_sweep_orchestration.py:28) — 若 sweep summary 含新字段，补测试
- 真实 `.ttbin` 数据文件（只读）

### Stage 6B 允许修改
- [`CURRENT_TASK.md`](CURRENT_TASK.md) — 更新最终结论
- [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) — 最终结论
- [`docs/`](docs/) — 最终报告，但不改 schema

## Forbidden Files（两阶段均禁止）

- 任何 `*.ttbin` 原始数据文件
- [`results/`](results/) 下已有结果
- 任何已有时间戳输出目录
- [`src/jti_extract/cli/`](src/jti_extract/cli/) 下旧 baseline CLI
- [`src/jti_extract/core/`](src/jti_extract/core/) 下 baseline 算法
- [`scripts/run_type0ppln_pplus_auto_dim.py`](scripts/run_type0ppln_pplus_auto_dim.py)
- 旧配置文件

---

## Schema Policy

- 禁止静默改变 CLI 参数名称和语义
- 禁止静默改变 CSV 列名和顺序
- 禁止静默改变 JSON 既有键名
- 禁止改变输出文件命名约定
- 已存在的 `SWEEP_SUMMARY_FIELDS`（[`src/jti_extract/ultra/io_ultra.py`](src/jti_extract/ultra/io_ultra.py:22)）不得重命名或重排
- **允许** JSON-only optional 新增字段，且不要求 CSV 同步

---

## Baseline Policy

- 不改变 baseline 算法语义
- 不改变 `coincidence_window_ps`、`binwidth_ps`、`frame_origin_ps` 的物理含义
- 主分析使用 `g2_all_candidates`；strict / nearest / greedy 只作为 diagnostic

---

## 已完成阶段汇总

### Stage 3: 中维度 coverage sweep — ✅
### Stage 4: pump coherence horizon sweep — ✅（探索性诊断）
### Stage 5A-E: 全步骤一次执行 — ✅（探索性诊断）

完整输出目录列表见 [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md:1323)。

---

## Stage 6A: diagonal-profile-width diagnostic + max_events convergence（已完成）

### 6A.1 前置条件：实现 JSON-only diagonal profile width diagnostic

当前 `FixedLatticeAccumulator.summary()`（[`src/jti_extract/ultra/accumulators.py`](src/jti_extract/ultra/accumulators.py:168)）只输出 `diag_profile_sum`，缺少 profile width。Stage 6A 需要在 accumulator 或 sweep 层新增可选统计字段，且**仅写入 JSON，不改 CSV schema**。

#### 候选新增字段及定义（累积质量 cumulative mass 的 quantile-width）

| 字段 | 计算方式 | 说明 |
|---|---|---|
| `diag_profile_peak_bin` | `argmax(diag_profile)` | profile 峰值 bin 索引 |
| `diag_profile_mass_width_90_bins` | cumulative mass 归一化后 5%–95% quantile 对应的 bin 宽度 | 90% mass width |
| `diag_profile_mass_width_95_bins` | cumulative mass 归一化后 2.5%–97.5% quantile 对应的 bin 宽度 | 95% mass width |
| `diag_profile_edge_fraction` | profile 在 ends of domain 的质量比例 | 边界诊断 |

计算步骤：
1. `diag_profile` 归一化为概率质量（除以 `n_candidates_after_edge_guard`）。
2. 计算 cumulative sum。
3. 找到 `cumsum >= 0.025 / 0.05 / 0.95 / 0.975` 的 bin 索引。
4. `width_95 = hi_bin - lo_bin + 1`，`width_90` 类似。
5. 空 profile 或无候选时返回 `None` 或 `-1`。

涉及文件：
- [`src/jti_extract/ultra/accumulators.py`](src/jti_extract/ultra/accumulators.py:168) — `summary()` 方法新增字段
- [`src/jti_extract/ultra/sweep_ultra_jti.py`](src/jti_extract/ultra/sweep_ultra_jti.py:28) — 若需要在 sweep layer 额外附加
- [`tests/test_ultra_accumulators.py`](tests/test_ultra_accumulators.py:181) — 新测试

#### 测试要求

- 空 profile → width 为 0 或 `None`
- 单 bin profile → width_90 = width_95 = 1
- 已知 profile `[0, 1, 1, 1, 0]` → 可手算 quantile width
- summary 内总和仍等于 `n_candidates_after_edge_guard`

### 6A.2 max_events convergence sweep

固定核心配置：

```text
N = 65536
binwidth_ps = 100
coincidence_window_ps = 200
edge_guard_ps = 200
coarse_N = 4096
truncated_rank = 1024（若资源可控；否则降至 512 并标注不足）
origin_sensitivity = 1638400, 3276800, 4915200
edge_guard_sensitivity = 100, 200, 300
```

max_events 梯度三点（已有两点可复用，新增一点）：

| 点 | max_events | 输出来源 |
|---|---:|---|
| A1 | 10000 | 复用 Stage 5 B2（`/tmp/ultra_stage5B_N65536_c4096_r512_20260430_184341/`） |
| A2 | 30000 | 复用 Stage 5 E1（`/tmp/ultra_stage5E_N65536_c4096_r512_max30000_20260430_185602/`） |
| A3 | **100000** | **新增运行**，写入 `/tmp/ultra_stage6A_N65536_c4096_r1024_max100000_*` |

若 `r=1024` 因资源限制不可行，降级为 `r=512`，但报告必须明确标注 captured energy 不足风险。

#### 运行前验证

```bash
~/envs/timetagger/bin/python -m pytest tests/test_ultra_accumulators.py tests/test_ultra_sweep_orchestration.py -v
~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra --self-test
```

#### 新增运行命令

```bash
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 100000 \
  --n-bins 65536 --binwidth-ps 100 --frame-origin-ps 0 \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --origin-sensitivity 1638400 3276800 4915200 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 4096 --truncated-rank 1024 \
  --out /tmp/ultra_stage6A_N65536_c4096_r1024_max100000_$(date +%Y%m%d_%H%M%S)
```

### 6A.3 验收标准（进入 Stage 6B 的门槛）

必须**同时满足**：

- [ ] JSON-only profile width diagnostic 实现并测试通过
- [ ] `diag_profile_mass_width_90/95` 随 `max_events` 从 10000→30000→100000 的变化收敛（或可用物理解释）
- [ ] `K_coarse` 在任意两个相邻 `max_events` 之间的相对变化 < 20%
- [ ] origin sensitivity ≤ 5%（对各点分别判断）
- [ ] `edge_rejection_ratio` ≤ 2%
- [ ] 不产生 full dense `N x N` CSV 文件
- [ ] `SWEEP_SUMMARY_FIELDS` 未被重命名或重排
- [ ] 结果表述为 exploratory diagnostic（即使通过上述门槛，Stage 6A 本身不宣称 final certification）

**若不满足任何一个门槛，则不应进入 Stage 6B**。最终结论降格为 ⚠️ exploratory only，并在最终报告中明确标注未通过项。

### 6A.4 Risks for Stage 6A

- **JSON-only schema extension risk**: 新字段必须只作为 optional diagnostic，不得破坏 CSV 和既有 JSON 字段。若 accumulator 的 `summary()` 返回新 key，但已有 CSV writer 和 JSON writer 只输出匹配字段，则不会触发 schema creep 错误。
- **Diagonal width definition risk**: quantile-width 定义必须固定并记录，避免后续解释漂移。
- **Runtime risk**: `max_events=100000` 可能显著慢于 Stage 5 E1（约 1 分钟）。若超过 10 分钟无响应，降低 `truncated_rank` 或取消 SVD 部分。
- **Memory risk**: `truncated_rank=1024` 与约 5000–6000 候选对下的 SVD 可能占用更多内存。
- **Still-not-converged risk**: 如果 `max_events=100000` 后 `K_coarse` 继续增长，则项目最终结论只能是 exploratory / not certified。这是可预期的风险，不应在 Stage 6A 强制消除。

### 6A.5 Rollback

- 代码 patch 限于 accumulator + sweep orchestration + tests。失败可 revert 该 patch。
- 新实验只写 `/tmp/ultra_stage6A_*`，失败时删除目录即可。
- 不修改原始 `.ttbin`，不覆盖 Stage 0–5 输出。
- 不修改 baseline CLI/core。

---

## Stage 6A-recheck: JSON field propagation + sparse-occupancy sanity gate（当前任务）

### 背景

Stage 6A code patch 已在 [`FixedLatticeAccumulator.summary()`](src/jti_extract/ultra/accumulators.py:178) 实现 `diag_profile_*` 新字段，且 [`run_synthetic_sweep_point()`](src/jti_extract/ultra/sweep_ultra_jti.py:117) 已合并 [`acc.summary()`](src/jti_extract/ultra/sweep_ultra_jti.py:117)。但之前的 Stage 6A 运行（[`/tmp/ultra_stage6A_N65536_c4096_r1024_max100000_20260430_193527/`](file:///tmp/ultra_stage6A_N65536_c4096_r1024_max100000_20260430_193527/)）发生在 patch 之前，`ultra_summary.json` 不含 `diag_profile_*` 字段。

此外审查发现当前 `K_coarse` 随统计量强烈增长（480→1135→2246），且 `svd_nonzero_bins` 与候选数同量级，尚不能排除 sparse-occupancy regime。

### 目标

1. 用全新输出目录重跑 Stage 6A 运行，确认 `diag_profile_*` 字段真实进入 JSON 输出。
2. 确认 CSV schema 未扩展（`diag_profile_*` 不出现在 CSV 中）。
3. 报告稀疏占用 sanity 表，评估 `K_coarse` 是否仍由 sparse occupancy 主导。

### 允许修改文件

- [`CURRENT_TASK.md`](CURRENT_TASK.md)（本文件）
- [`RUN_COMMANDS.md`](RUN_COMMANDS.md)
- [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md)
- 既有的 accumulator/sweep patch 确认

### 禁止行为

- 改动旧 Stage 0–5 输出目录
- 覆盖旧 `/tmp/ultra_stage6A_*` 目录
- 改动 CLI、CSV schema、baseline 代码
- 宣称最终物理维度认证（本轮输出仍是 exploratory diagnostic）

### 新增运行命令

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

### JSON 字段确认

```bash
~/envs/timetagger/bin/python - <<'PY'
import json
from pathlib import Path
out = sorted(Path("/tmp").glob("ultra_stage6A_recheck_jsonwidth_N65536_c4096_r1024_max100000_*"))[-1]
data = json.loads((out / "ultra_summary.json").read_text())
main = data[0]
required = ["diag_profile_peak_bin","diag_profile_mass_width_90_bins","diag_profile_mass_width_95_bins","diag_profile_edge_fraction"]
missing = [key for key in required if key not in main]
print("out:", out)
print("missing:", missing)
for key in required: print(key, main.get(key))
print("K_coarse", main.get("K_coarse"))
print("n_candidates_after_edge_guard", main.get("n_candidates_after_edge_guard"))
print("svd_nonzero_bins", main.get("svd_nonzero_bins"))
print("captured_frobenius_energy_r", main.get("captured_frobenius_energy_r"))
raise SystemExit(1 if missing else 0)
PY
```

### CSV schema 确认

```bash
~/envs/timetagger/bin/python - <<'PY'
import csv
from pathlib import Path
out = sorted(Path("/tmp").glob("ultra_stage6A_recheck_jsonwidth_N65536_c4096_r1024_max100000_*"))[-1]
with (out / "ultra_summary.csv").open(newline="") as f:
    fields = next(csv.reader(f))
forbidden = ["diag_profile_peak_bin","diag_profile_mass_width_90_bins","diag_profile_mass_width_95_bins","diag_profile_edge_fraction"]
for f in forbidden:
    print(f, f in fields)
    if f in fields: raise SystemExit(1)
print("CSV schema OK")
PY
```

### 稀疏占用 sanity 报告模板

| `max_events` | `n_candidates_after_edge_guard` | `svd_nonzero_bins` | `K_coarse` | `K_coarse / n_candidates` | `nonzero_bins / n_candidates` |
|---:|---:|---:|---:|---:|---:|
| 10000 | 539 | 506 | 480.20 | 0.891 | 0.939 |
| 30000 | 1583 | 1314 | 1135.43 | 0.717 | 0.830 |
| 100000 | 5213 | 2969 | 2245.71 | 0.431 | 0.570 |

如果 `K_coarse` 继续随候选数强烈增长，默认判定为 sparse sampling dominated，不允许进入 Stage 6B。

### 重跑后判断

- 如果 JSON 缺字段 → 回归代码传播 bug，必须修复后再重跑。
- 如果 JSON 字段完整，但 `K_coarse` 相邻变化仍 > 20% → 维持 exploratory only，不进入 Stage 6B。
- 如果 `diag_profile_mass_width_90/95` 随 `max_events` 大幅扩张 → 不认定为收敛。
- 只有在 JSON 字段完整、`K_coarse` 相对变化 < 20%、`diag_profile_width` 稳定、origin sensitivity ≤ 5%、edge rejection ≤ 2% 全部满足时，才允许重新讨论 Stage 6B。

---

## Stage 7: linewidth-informed coherence-horizon sanity sweep（✅ 已完成）

> S7-A（N=32768, 3.28 µs）和 S7-C（N=100000, 10 µs）已于 2026-04-30 运行成功；S7-B 复用 [`Stage 6A-recheck`](CURRENT_TASK.md:218) 的 N=65536 点。
>
> 关键结果：
> - `diag_profile_mass_width_95_bins = 2`（200 ps）在三个 frame length 上高度稳定
> - `K_coarse`（2225→2246→1338）仍不满足相邻变化 < 20% 认证门槛
> - `captured_frobenius_energy_r ≈ 0.55`，远低于 0.9
> - `svd_nonzero_bins / n_candidates ≈ 0.57`，仍明显 sparse dominated
>
> **结论**：local diagonal width 稳定，但与几百 kHz 先验比较需补短帧扫描。

### 背景

截至本轮，`K_coarse` 仍随候选数强烈增长（480→1135→2246），且 `diag_profile_mass_width_90/95` 在 `N=65536`（6.55 µs）处只有 2 bins（200 ps），宽度远小于 frame length。这与已知的百 kHz 线宽激光器（coherence horizon 约 3–10 µs，参考 [`docs/SCHMIDT_ANALYSIS.md`](docs/SCHMIDT_ANALYSIS.md:69) 和 [`jti超高维sweep问题_原理与操作步骤_更新版.md`](jti超高维sweep问题_原理与操作步骤_更新版.md:735)）**并不矛盾**：

- `N=65536, bw=100 ps` → `frame_length=6.55 µs`：位于百 kHz loose coherence horizon（≈ 10 µs）的中间位置。
- `N=32768` → `3.28 µs`：接近 Lorenzian `1/(π·100 kHz)` 估计。
- `N=100000` → `10 µs`：接近 `1/(100 kHz)` 估计。

因此 `K_coarse` 在这个 sweep 范围内继续随采样增加而增长是可能且可预期的，不能当作 stage 6B 所需的收敛证据。

Stage 7 的目标是：
1. **用百 kHz 线宽先验设计 frame-length sweep**，包含 `3.28 µs / 6.55 µs / 10 µs` 三点，覆盖 coherence horizon 前后。
2. **分离两个问题**：
   - `diag_profile_width` 是否随 `frame_length_ps` 稳定？
   - `K_coarse` 是否仍由 sparse occupancy 主导（即随候选数增长）？
3. **给出物理综合判断**：是“对角线局部宽度已收敛但 full effective dimension 因 statistics/truncation 无法认证”还是“所有指标均不收敛”。

### 固定配置

- `binwidth_ps = 100 ps`
- `max_events = 100000`
- `coarse_n_bins = 4096`
- `truncated_rank = 1024`
- `coincidence_window_ps = 200 ps`
- `edge_guard_ps = 200 ps`

### Sweep 点

| 点 | N | frame_length | 物理意义 | 状态 |
|:---|---:|---:|---|:---|
| S7-A | 32768 | 3.28 µs | 接近 `1/(πΔν)` for 100 kHz | 需新增运行 |
| S7-B | 65536 | 6.55 µs | 已有 recheck 数据 | **复用** [`/tmp/ultra_stage6A_recheck_jsonwidth_N65536_c4096_r1024_max100000_20260430_195256/`](file:///tmp/ultra_stage6A_recheck_jsonwidth_N65536_c4096_r1024_max100000_20260430_195256/) |
| S7-C | 100000 | 10.0 µs | 接近 `1/Δν` for 100 kHz | 需新增运行 |
| S7-D | 200000 | 20.0 µs | loose horizon 上方 | **可选**，仅 S7-C 仍无法判断时再跑 |

### 允许修改文件

- [`CURRENT_TASK.md`](CURRENT_TASK.md)（本文件）
- [`RUN_COMMANDS.md`](RUN_COMMANDS.md)
- [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md)

### 禁止行为

- 改动旧 Stage 0–6 输出目录
- 覆盖任何 `/tmp/ultra_stage*` 目录
- 改动 CLI、CSV schema、baseline 代码
- 宣称最终物理维度认证（Stage 7 本身仍是 exploratory diagnostic）

### S7-A 命令

```bash
# S7-A: N=32768, frame_length=3.28 µs
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 100000 \
  --n-bins 32768 --binwidth-ps 100 --frame-origin-ps 0 \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --origin-sensitivity 819200 1638400 2457600 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 4096 --truncated-rank 1024 \
  --out /tmp/ultra_stage7_linewidth_N32768_c4096_r1024_max100000_$(date +%Y%m%d_%H%M%S)
```

### S7-C 命令

```bash
# S7-C: N=100000, frame_length=10.0 µs
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 100000 \
  --n-bins 100000 --binwidth-ps 100 --frame-origin-ps 0 \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --origin-sensitivity 2500000 5000000 7500000 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 4096 --truncated-rank 1024 \
  --out /tmp/ultra_stage7_linewidth_N100000_c4096_r1024_max100000_$(date +%Y%m%d_%H%M%S)
```

### S7-D 可选命令（不默认跑）

```bash
# S7-D: N=200000, frame_length=20.0 µs （仅在 S7-C 仍无法判断时执行）
/usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 100000 \
  --n-bins 200000 --binwidth-ps 100 --frame-origin-ps 0 \
  --coincidence-window-ps 200 --edge-guard-ps 200 \
  --origin-sensitivity 5000000 10000000 15000000 \
  --edge-guard-sensitivity 100 200 300 \
  --coarse-n-bins 4096 --truncated-rank 1024 \
  --out /tmp/ultra_stage7_linewidth_N200000_c4096_r1024_max100000_$(date +%Y%m%d_%H%M%S)
```

### 汇总脚本（每点必读）

每个输出目录的 `ultra_summary.json` 主点必须报告：

```text
N
frame_length_ps
n_candidates_after_edge_guard
svd_nonzero_bins
K_coarse
K_coarse / n_candidates_after_edge_guard
svd_nonzero_bins / n_candidates_after_edge_guard
diag_profile_mass_width_90_bins
diag_profile_mass_width_95_bins
diag_profile_mass_width_95_ps = width_95_bins * binwidth_ps
diag_profile_edge_fraction
captured_frobenius_energy_r
edge_rejection_ratio
origin_sensitivity_K_max_rel
```

### Stage 7 判据

#### A. Diagonal profile width 是否与百 kHz coherence horizon 一致？

- `diag_profile_mass_width_95_ps` 在相邻 `frame_length_ps` 之间相对变化 < 20%
- `width_95_ps < 0.3 × frame_length_ps`（说明宽度远小于帧长，profile 局部特征与长帧 decouple）
- 如果 width95 随 `frame_length_ps` 显著增长，或 width95 开始接近 `frame_length_ps`，说明 profile 受长程/偶然符合主导，不可认证。

#### B. 是否仍由 sparse occupancy 主导？

- 若 `svd_nonzero_bins / n_candidates_after_edge_guard > 0.3` 且 `K_coarse` 随 `n_candidates` 增长显著 → 判定为 sparse sampling dominated
- 必须报告 `n_candidates_after_edge_guard / coarse_n_bins^2`（当前 coarse_N=4096 时，分母为 16,777,216；当前候选数仅几千）

#### C. 是否允许进入 Stage 6B / final certification？

必须全部满足：

1. `diag_profile_mass_width_95_ps` 在 adjacent frame-length 间相对变化 < 20%
2. `K_coarse` 相邻变化 < 20%，或明确降级为 sparse diagnostic
3. `origin_sensitivity_K_max_rel ≤ 5%`
4. `edge_rejection_ratio ≤ 2%`
5. `captured_frobenius_energy_r ≥ 0.9`（若达不到则不能宣称 full Schmidt number）
6. CSV schema 不变，JSON-only 字段存在

#### 预期结论

基于现有结果，最可能的最终判断是：

```text
✅ 对角线局部 profile width 稳定且远小于 frame length
⚠️ 但 K_coarse / full effective dimension 不认证（sparse occupancy 未收敛、captured energy 不足）
```

### Stage 7 验收标准（进入下一个物理报告的阈值）

Stage 7 不要求“通过”，只要求“报告 3 点 sweep 结果 + 给出解释”。即使 `K_coarse` 仍不收敛，只要确认了 `diag_profile_width` 稳定且稀疏占用程度被明确量化，Stage 7 即可认为完成。

---

## Stage 8: high-linewidth short-horizon scan（当前任务）

### 背景

上一轮 [`Stage 7`](CURRENT_TASK.md:319) 的 `N=32768/65536/100000` 三点已确认 `diag_profile_mass_width_95=200 ps` 在 `3.28–10 µs` 范围内高度稳定，`K_coarse` 仍不收敛，`captured_frobenius_energy_r≈0.55`。

已知先验线宽可能为**几百 kHz** 范围——不局限于严格的 100 kHz。这意味着 coherence horizon 可能更短：

| 线宽 | `1/(πΔν)`（Lorentzian） | `1/Δν`（loose） |
|---:|---:|---:|
| 100 kHz | ~3.2 µs | ~10 µs |
| 300 kHz | ~1.1 µs | ~3.3 µs |
| 500 kHz | ~0.64 µs | ~2.0 µs |
| 1 MHz | ~0.32 µs | ~1.0 µs |

Stage 8 的目标是补扫 **0.8–3.3 µs 短帧梯度**，覆盖几百 kHz 先验范围，检验 `diag_profile_width` 是否在该区间内仍稳定，以及 `K_coarse` 是否在该区间有不同行为。

### 固定配置

- `binwidth_ps = 100 ps`
- `max_events = 100000`
- `coarse_n_bins = 4096`
- `truncated_rank = 1024`
- `coincidence_window_ps = 200 ps`
- `edge_guard_ps = 200 ps`

### Sweep 点

| 点 | N | frame_length | 物理意义 | 状态 |
|:---|---:|---:|---|---|
| S8-A | 8192 | 0.819 µs | 覆盖 500 kHz–1 MHz Lorentzian horizon 附近 | **新增运行** |
| S8-B | 16384 | 1.638 µs | 覆盖 300–500 kHz 中间 horizon | **新增运行** |
| S8-C | 24576 | 2.458 µs | 覆盖 300–500 kHz loose horizon 中间 | **新增运行** |
| S8-D | 32768 | 3.277 µs | 接近 300 kHz loose horizon | **复用** [`Stage 7 S7-A`](file:///tmp/ultra_stage7_linewidth_N32768_c4096_r1024_max100000_20260430_200142/) |

### 允许修改文件

- [`CURRENT_TASK.md`](CURRENT_TASK.md)（本文件）
- [`RUN_COMMANDS.md`](RUN_COMMANDS.md)
- [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md)

### 禁止行为

- 改动旧 Stage 0–7 输出目录
- 覆盖任何 `/tmp/ultra_stage*` 目录
- 改动 CLI、CSV schema、baseline 代码
- 宣称最终物理维度认证（Stage 8 仍是 exploratory diagnostic）

### S8-A 命令（N=8192, 0.819 µs）

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

### S8-B 命令（N=16384, 1.638 µs）

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

### S8-C 命令（N=24576, 2.458 µs）

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

### 汇总表

每点必须报告：

| `N` | `frame_length_µs` | `width95_ps` | `diag_profile_edge_fraction` | `K_coarse` | `svd_nonzero_bins / n_candidates` | `captured_frobenius_energy_r` | `origin_sensitivity_K_max_rel` |
|---:|---:|---:|---:|---:|---:|---:|---:|

与 [`Stage 7`](CURRENT_TASK.md:319) 的 `N=32768/65536/100000` 放在同一表里。

### Stage 8 判据

#### A. Local width 与几百 kHz 先验的一致性

- `diag_profile_mass_width_95_ps` 在 S8-A/B/C/D（0.819–3.277 µs）之间相对变化 < 20%
- `width95_ps < 0.3 × frame_length_ps` 在各点均满足
- 如果 width95 随 frame_length 急剧变化→表明 profile 在短帧约束下不稳定

#### B. Sparse occupancy 判定

- 若 `svd_nonzero_bins / n_candidates > 0.3` → sparse dominated
- 若 `K_coarse` 随 N 增长幅度明显大于局部宽度变化 → 认证结论只能给局部宽度

#### C. 是否需要继续扩展

- 若 S8-A/B/C/D 的 width95 全部稳定且 `diag_profile_edge_fraction` 无显著变化 → 不需要跑 `S7-D (N=200000, 20 µs)`
- 若 width95 仅在大 N 时才稳定 → 则可能需要更大 N

### 预期结论

Stage 8 验证后的数据确认：

```text
✅ local diagonal profile width: stable at ~200 ps across 0.82–10 µs frames
   → 最短已测帧长 0.819 µs 已足以容纳 width95≈200 ps 的局部明亮区对角线宽度
   → width95_ps << 0.3 × frame_length_ps 在所有扫描点满足
✅ compatible with few-hundred-kHz linewidth prior (exploratory, not certified)
⚠️ K_coarse / full effective dimension: not certified due to sparse occupancy
   and insufficient truncated SVD energy (captured_frobenius_energy_r≈0.56)
❌ full Schmidt-number certification: not supported by current data
```

> 注意区分：局部 diagonal profile width 覆盖被确认（0.819 µs 已足够），但全局 JTI 二维有效维度、完整 Schmidt number 未被认证。

---

## Stage 6B: 最终汇总与可信度判断（**✅ 已完成**）

### 禁止行为

- 不得改动 CLI、CSV schema、baseline 代码
- 不得覆盖已有 `/tmp/ultra_stage*` 输出目录
- 不得追加完整实验或运行重型命令
- 不得宣称 full Schmidt-number certification（当前证据不支持）

### 最终汇总表

#### 表 1：frame_length sweep（固定 max_events=100000, coarse_N=4096, r=1024）

| 数据来源 | `N` | `frame_µs` | `width95_ps` | `edge_frac` | `K_coarse` | `svd_nonzero/nguard` (ratio) | `E_trunc` |
|:---|---|---:|---:|---:|---:|---:|---:|
| S8-A | 8192 | 0.819 | 200 | 0.82377 | 2056.98 | 0.6203 | 0.5873 |
| S8-B | 16384 | 1.638 | 200 | 0.82368 | 2165.63 | 0.5942 | 0.5651 |
| S8-C | 24576 | 2.458 | 200 | 0.82368 | 2200.30 | 0.5862 | 0.5596 |
| S7-A | 32768 | 3.277 | 200 | 0.82371 | 2225.85 | 0.5786 | 0.5566 |
| 6A-recheck | 65536 | 6.554 | 200 | 0.82371 | 2245.71 | 0.5696 | 0.5517 |
| S7-C | 100000 | 10.000 | 200 | 0.82355 | 1337.88 | 0.5658 | 0.5579 |

> 数据来源：S8-A/B/C 见 [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md:1537)；6A-recheck 见 [`ultra_summary.json`](../../../tmp/ultra_stage6A_recheck_jsonwidth_N65536_c4096_r1024_max100000_20260430_195256/ultra_summary.json:34)；S7-A 见 [`ultra_summary.json`](../../../tmp/ultra_stage7_linewidth_N32768_c4096_r1024_max100000_20260430_200142/ultra_summary.json:34)；S7-C 见 [`ultra_summary.json`](../../../tmp/ultra_stage7_linewidth_N100000_c4096_r1024_max100000_20260430_200334/ultra_summary.json:34)

- `width95_ps = 200 ps` 在全部 6 点稳定，且 `200 ps << 0.3 × frame_length_ps` 在所有点满足
- `K_coarse` 在 N=8192–65536 间微增（2057→2246，变化 ~9%），但在 N=100000 处下降至 1338（异常点，可能因 coarse lattice 覆盖物理范围改变），不能视为已收敛
- `svd_nonzero_bins / n_candidates_after_edge_guard ≈ 0.57–0.62`，全部 > 0.3 → **sparse-dominated regime**
- `captured_frobenius_energy_r ≈ 0.55–0.59`，全部 < 0.9 → truncated SVD 能量不足
- `edge_rejection_ratio ≈ 0.0–0.001`，边界效应可控
- `diag_profile_edge_fraction ≈ 0.824` 高且稳定：profile 质量集中在边缘 bin

#### 表 2：max_events 梯度（N=65536, coarse_N=4096）

| `max_events` | `n_candidates_after_edge_guard` | `K_coarse` | `svd_nonzero/nguard` | 数据来源 |
|:---:|---:|---:|---:|:---|
| 10000 | 539 | 480.20 | 506/539=0.939 | [`Stage 5B`](AGENT_HANDOFF.md:1340) |
| 30000 | 1583 | 1135.43 | 1314/1583=0.830 | [`ultra_summary.json`](../../../tmp/ultra_stage5E_N65536_c4096_r512_max30000_20260430_185602/ultra_summary.json:30) |
| 100000 | 5213 | 2245.71 | 2969/5213=0.570 | 6A-recheck |

> `K_coarse` 与 `n_candidates` 呈近似线性增长，未出现收敛 plateau。sparse occupancy ratio 随候选数增多而下降，但仍 > 0.5。

#### 表 3：coarse_N 灵敏度（N=65536, max_events=10000）

| `coarse_N` | `K_coarse` | 数据来源 |
|:---:|---:|:---|
| 2048 | — | [`Stage 5C c2048`](AGENT_HANDOFF.md:1340) |
| 4096 | — | 6A-recheck 有 100k 数据 |
| 8192 | — | [`Stage 5C c8192`](AGENT_HANDOFF.md:1340) |

> coarse_N 灵敏度数据来自旧 Stage 5C，与当前 100k max_events 不完全可比，此处仅作参考。

### 最终结论

#### 已实现能力

- Fixed-lattice G2-like JTI sweep pipeline 完整可用，经过 Stage 0–8 全流程验证
- 边界效应可控（`edge_rejection_ratio ≤ 0.001`）
- 高维使用 coarse / truncated SVD + bootstrap 诊断
- 所有 Stage 输出目录均在 `/tmp/ultra_stage*` 下，不覆盖已有结果
- JSON-only diagonal profile width diagnostics（`diag_profile_*`）已实现并验证

#### 未收敛项

| 项 | 状态 | 详情 |
|---|---|---|
| `coarse_N` stability | ⚠️ 未完成收敛扫描 | 旧数据跨 coarse_N 2048/4096/8192，但 not consistently with 100k events |
| `max_events` gradient | ❌ 未收敛 | `K_coarse` 从 480→1135→2246，呈近似线性增长 |
| truncated SVD captured energy | ❌ 未收敛 | `captured_frobenius_energy_r ≈ 0.55–0.59`，远低于 0.9 门槛 |
| strict baseline | ❌ 基本失效 | 长 frame 下 `n_strict_pairs` 接近 0，仅作 diagnostic |

#### 最终档位：⚠️ exploratory only

**可报告的 certified 结论：**

> ✅ **局部 diagonal profile width**: 可信诊断，`width95 ≈ 200 ps`（`diag_profile_mass_width_95_bins = 2 × 100 ps binwidth`），在 `0.819–10 µs` 帧长范围内高度稳定
> ✅ **帧长覆盖**: 最短已测帧长 `0.819 µs` 已足以容纳此局部对角线宽度（`width95_ps << 0.3 × frame_length_ps`）
> ✅ **物理解释一致性**: 与数百 kHz 线宽先验的短 horizon 扫描结果不冲突（exploratory consistency）

**不支持的结论：**

> ❌ `K_coarse` / full effective dimension: 不能认证（sparse-dominated：`svd_nonzero/nguard ≈ 0.57–0.62`；`K_coarse` 随候选数线性增长而未收敛；truncated SVD `captured_frobenius_energy_r ≈ 0.55`）
> ❌ full Schmidt-number certification: 当前数据不支持

### 建议后续方向（如果 exploratory / not certified）

- `max_events` 扩大到 500k 或完整 TTBIN，检验 `K_coarse` 是否在更高统计量下出现收敛 plateau
- `truncated_rank` 从 1024 提高到 2048 或 4096，检查 `captured_frobenius_energy_r` 是否能跨过 0.9 门槛
- `coarse_N` 在统一 max_events=100k 下做完整 2048/4096/8192 灵敏度扫描
- `S7-D (N=200000, 20 µs)` 不紧急，但可作为 linewidth 覆盖完整性的补充参考点
- 以上均为 optional 研究方向，非认证必要步骤

---

## Stage 9: diagonal-ridge localization（**当前任务**）

### 背景

Stage 0–8 + 6B 已确认：

1. 局部横向 diagonal profile width ≈ 200 ps（`diag_profile_mass_width_95_bins = 2 × 100 ps`）
2. 最短已测帧长 0.819 µs 已足以容纳该宽度

但 **bright ridge 沿 frame-local 时间轴的实际位置**尚未被定位。当前 `diag_profile` 仅统计 `|bin_a - bin_b|`，只能回答“离对角线多远”，不能回答“亮区在 frame 内哪里”。

`diag_profile_peak_bin = 0` 说明峰值在 `|bin_a - bin_b| = 0`，即两路事件落在同一 frame-local bin。但这不意味着亮区在 frame 中心——它只说明 pair 成员间的 bin 差为零。

### Goal

新增 JSON-only `diag_center_*` diagnosis，用 `(bin_a + bin_b)//2` 计算 pair 在 frame 内的中心位置，累积沿对角线方向的 profile，由此回答：

- 明亮区对角线的质量集中在 frame 内的哪个时间位置？
- 该中心位置的时间宽度是否也受到 frame length 的约束？
- 亮区是否贴在 frame boundary 附近（`diag_center_edge_fraction` 高）？

### 关键定义

给定 frame-local bin indices `ba`, `bb`（来源：参见 [`fold_lattice.bin_indices()`](src/jti_extract/ultra/fold_lattice.py:54)）：

| 量 | 公式 | 含义 |
|---|---|---|
| `center_bin` | `(ba + bb) // 2` | pair 在 frame 内的中心 bin 位置 |
| `center_time_ps` | `frame_origin_ps + (center_bin + 0.5) × bin_width_ps` | 中心 bin 对应的实际 frame-local 时间 |
| `diag_center_profile[center_bin]` | 累积 `masked=True` 的 pairs | 沿对角线 bright ridge 的强度分布 |

### 候选新增字段（JSON-only, optional）

| 字段 | 含义 | 实现方式 |
|---|---|---|
| `diag_center_peak_bin` | 明亮 ridge 峰值所在的 bin | `np.argmax(diag_center_profile)` |
| `diag_center_peak_time_ps` | 峰值 bin 中心对应的实际 frame-local 时间 | `frame_origin_ps + (peak_bin + 0.5) × bin_width_ps` |
| `diag_center_mass_width_90_bins` | 沿对角线方向的 90% 质量宽度 | `_quantile_width(profile, 0.05, 0.95)` |
| `diag_center_mass_width_95_bins` | 沿对角线方向的 95% 质量宽度 | `_quantile_width(profile, 0.025, 0.975)` |
| `diag_center_mass_width_90_ps` | `diag_center_mass_width_90_bins × bin_width_ps` | 同上 |
| `diag_center_mass_width_95_ps` | `diag_center_mass_width_95_bins × bin_width_ps` | 同上 |
| `diag_center_edge_fraction` | 质量在 frame 边缘（bin 0 和 bin N-1）的占比 | `(profile[0] + profile[-1]) / total` |

与现有字段的关系：

| 维度 | 现有字段 | 新增字段 |
|---|---|---|
| 横向（perpendicular to diagonal） | `diag_profile_*` | — |
| 纵向（沿着 diagonal） | — | `diag_center_*` |

### 允许修改文件

- [`src/jti_extract/ultra/accumulators.py`](src/jti_extract/ultra/accumulators.py:18)：在 `FixedLatticeAccumulator` 中添加 `diag_center_profile` 和相关 summary 字段。
- [`tests/test_ultra_accumulators.py`](tests/test_ultra_accumulators.py:295)：添加 `diag_center_*` 字段存在性与正确性测试。
- [`tests/test_ultra_sweep_orchestration.py`](tests/test_ultra_sweep_orchestration.py:28)：添加字段传播测试。

### 禁止行为

- 不改 [`SWEEP_SUMMARY_FIELDS`](src/jti_extract/ultra/io_ultra.py:22) — CSV schema 保持不变。
- 不改 [`sweep_ultra_jti.run_synthetic_sweep_point()`](src/jti_extract/ultra/sweep_ultra_jti.py:28) — 诊断通过 `**acc.summary()` 自动传播。
- 不改 [`g2_accumulate.py`](src/jti_extract/ultra/g2_accumulate.py:62)、[`fold_lattice.py`](src/jti_extract/ultra/fold_lattice.py:54)、[`svd_estimators.py`](src/jti_extract/ultra/svd_estimators.py:172)。
- 不覆盖任何 `/tmp/ultra_stage*` 已有输出目录。

### Patch 指南

#### 1. 在 [`FixedLatticeAccumulator.__init__()`](src/jti_extract/ultra/accumulators.py:38) 中新增

```python
self._diag_center_profile: np.ndarray = np.zeros(int(n_bins), dtype=np.float64)
```

#### 2. 在 [`FixedLatticeAccumulator.add_candidates()`](src/jti_extract/ultra/accumulators.py:112) 中新增

在 `np.add.at(self._diag_profile, diag_idx, 1.0)` 之后：

```python
# diag-center (ridge localization)
center_idx = (
    (np.asarray(ba_kept, dtype=np.int64) + np.asarray(bb_kept, dtype=np.int64))
    // 2
)
center_idx = np.clip(center_idx, 0, self._n_bins - 1)
np.add.at(self._diag_center_profile, center_idx, 1.0)
```

#### 3. 在 [`FixedLatticeAccumulator.summary()`](src/jti_extract/ultra/accumulators.py:178) 中新增

在 `return` 的 dict 中添加：

```python
"diag_center_peak_bin": int(np.argmax(self._diag_center_profile))
    if np.sum(self._diag_center_profile) > 0 else -1,
"diag_center_peak_time_ps": (
    self._frame_origin_ps
    + (int(np.argmax(self._diag_center_profile)) + 0.5) * self._bin_width_ps
) if np.sum(self._diag_center_profile) > 0 else -1.0,
"diag_center_mass_width_90_bins": self._quantile_width(
    self._diag_center_profile, 0.05, 0.95
),
"diag_center_mass_width_95_bins": self._quantile_width(
    self._diag_center_profile, 0.025, 0.975
),
"diag_center_mass_width_90_ps": self._quantile_width(
    self._diag_center_profile, 0.05, 0.95
) * self._bin_width_ps,
"diag_center_mass_width_95_ps": self._quantile_width(
    self._diag_center_profile, 0.025, 0.975
) * self._bin_width_ps,
"diag_center_edge_fraction": (
    float(
        self._diag_center_profile[0]
        + self._diag_center_profile[self._n_bins - 1]
    )
    / float(np.sum(self._diag_center_profile))
    if np.sum(self._diag_center_profile) > 0
    else 0.0
),
```

#### 4. 测试

在 [`tests/test_ultra_accumulators.py`](tests/test_ultra_accumulators.py:295) 中新测试：

```python
def test_diag_center_fields(self) -> None:
    """diag_center_* fields exist, peak bin and peak time are correct."""
    ...

def test_diag_center_symmetry(self) -> None:
    """Symmetric input → center at frame midpoint."""
    ...
```

在 [`tests/test_ultra_sweep_orchestration.py`](tests/test_ultra_sweep_orchestration.py:28) 中扩展：

```python
def test_diag_center_fields_propagated(self) -> None:
    """run_synthetic_sweep_point propagates diag_center_* fields."""
    ...
```

### 验证命令

```bash
# 轻量验证
~/envs/timetagger/bin/python -m pytest tests/test_ultra_accumulators.py tests/test_ultra_sweep_orchestration.py -v
~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra --self-test

# 真实数据诊断（仅一个最小点，复用 S8-A 参数）
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

### 验收标准

- 测试全部 pass
- JSON 输出含 `diag_center_peak_bin`, `diag_center_peak_time_ps`, `diag_center_mass_width_*`, `diag_center_edge_fraction`
- CSV schema 不变（`SWEEP_SUMMARY_FIELDS` 无新增条目）
- 对真实 `.ttbin` 数据，诊断字段值合理：
  - `0 ≤ diag_center_peak_bin < n_bins`
  - `diag_center_peak_time_ps` 在 `[frame_origin_ps, frame_origin_ps + frame_length_ps)` 内
  - `diag_center_mass_width_95_ps ≤ 0.8 × frame_length_ps`
- 旧 Stage 输出目录未被覆盖

### 判据与预期结论

| 判据 | 含义 |
|---|---|
| `diag_center_peak_time_ps` 落在 frame 中心 1/3–2/3 区域 | ridge 未受 frame boundary 夹紧 |
| `diag_center_edge_fraction < 0.3` | ridge 未贴在 frame 边缘 |
| `diag_center_mass_width_95_ps / frame_length_ps < 0.5` | ridge 沿 frame 未被截断 |
| 以上三项均满足 | 可初步认定 frame origin 对 ridge 定位充分 |

### Risks

- `center_bin = (ba+bb)//2` 对跨 frame boundary 的 pairs 可能有 wrap 问题；首选方案是记录 `diag_center_edge_fraction` 并做 origin sensitivity 验证
- `diag_center_profile` 和 `diag_profile` 容易混淆——文档必须明确区分
- `diag_center_mass_width_95_ps` 解释为“ridge 沿 frame-local 时间轴的长度”，不能当做 effective dimension 或 Schmidt number

---

---

---

## Stage 13-19: 百微秒 Containment Workflow（第一阶段：profile-only 上探 + 归档报告）

本阶段的核心逻辑链：

```
profile-only 上探 (Stage 13)
  → containment sweep (Stage 14)
    → 二分搜索 plateau (Stage 15)
      → max_events 验证 (Stage 16)
        → containment 后才做近似 Schmidt (Stage 17)
          → 最终报告 (Stage 18-19)
```

**核心原则**：
- 超高维默认不生成完整 dense JTI；大维度 Schmidt 只能做 coarse/sparse/truncated 分层估计。
- 多个 origin 只做 sensitivity check，不叠加成更多样本。
- 主判据使用 `diag_center_circular_min_arc_width_95_ps`（最短 circular arc 宽度），而不是 linear quantile width。
- 必须同时报告 profile flatness 指标（peak_to_mean、CV、entropy），以区分 "ridge 真的超过百微秒" 与 "folded center profile 已近似均匀，duration 指标失效"。

---

## 前置 patch: 添加 `--profile-only` 标志

当前 CLI 没有专门的 profile-only 模式。需要 minimal patch：

### 允许修改

- [`src/jti_extract/ultra/cli_ultra.py`](src/jti_extract/ultra/cli_ultra.py:39) — 添加 `--profile-only` flag
- [`tests/test_ultra_cli_params.py`](tests/test_ultra_cli_params.py) — flag 解析测试

### 实现要点

在 `build_parser()` 中添加：
```python
parser.add_argument(
    "--profile-only", action="store_true", dest="profile_only",
    help="Profile-only mode: skip coarse JTI, SVD, and bootstrap",
)
```

在 `_run()` 中：若 `args.profile_only`，则传入 `run_synthetic_sweep_point(..., coarse_n_bins=0)`；跳过 truncated SVD 块和 bootstrap 块。不跳过 origin/edge guard sensitivity。

### 验证

```bash
~/envs/timetagger/bin/python -m pytest tests/test_ultra_cli_params.py -v
~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra --self-test
```

---

## Stage 13A: N=32768 profile-only reproducibility check

在进入 N=1000000 之前，先用已知点验证 profile-only 模式的正确性。

### 运行

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

### 验收

- `diag_center_circular_mass_width_95_ps` 与旧 Stage 8 S7-A（~3125500 ps）一致
- `diag_center_circular_min_arc_width_95_ps` 可作为新对比基准
- JSON 输出不含 `K_coarse` / `K_truncated_r` / `captured_frobenius_energy_r`

---

## Stage 13B: N=1000000（100 µs）profile-only probe

### 固定配置

```
N = 1000000
binwidth_ps = 100
frame_length_ps = 100000000 (= 100 µs)
coincidence_window_ps = 200
edge_guard_ps = 200
max_events = 100000
coarse_n_bins = 4096（只为 origin/edge sensitivity 保留；实际被 --profile-only 跳过）
method = g2_all_candidates
```

### 运行

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

### 必读输出字段

| 字段 | 用途 |
|---|---|
| `diag_center_circular_min_arc_width_95_ps` | **主判据**：最短 circular arc 覆盖 95% mass |
| `diag_center_circular_mass_width_95_ps` | 辅助：linear quantile width |
| `min_arc_width / frame_length` | 主判据比例 |
| `mass_width / frame_length` | 辅助比例 |
| `diag_center_peak_time_ps` | peak 位置 |
| `diag_center_edge_fraction` | 边界质量占比 |
| `diag_profile_mass_width_95_ps` | 横向厚度 |
| `edge_rejection_ratio` | 边界拒绝率 |
| `n_candidates_after_edge_guard` | 候选数 |
| `row_marginal_sum` / `col_marginal_sum` | 边际总质量 |

### 新增 flatness 指标（需要在 accumulator summary 中新增或从已有 profile 计算）

| 指标 | 定义 | 含义 |
|---|---|---|
| `diag_center_circular_peak_to_mean` | `max(profile) / mean(profile)` | 峰值对比度；≈1 表示近似均匀 |
| `diag_center_circular_cv` | `std(profile) / mean(profile)` | 变异系数；衡量 profile 平坦度 |
| `diag_center_circular_entropy` | `-Σ(p_i·log₂(p_i))` 其中 p_i 归一化 | profile 信息熵；log₂(N) 为最大值 |
| `diag_center_circular_peak_bin` | 已有 | — |
| `diag_center_circular_peak_time_ps` | 已有 | — |

#### 新增方法

在 [`FixedLatticeAccumulator.summary()`](src/jti_extract/ultra/accumulators.py:213) 中新增 JSON-only flatness fields：
```python
# circular profile flatness diagnostics
circ_profile = self._diag_center_circular_profile
circ_total = float(np.sum(circ_profile))
if circ_total > 0:
    p = np.asarray(circ_profile, dtype=np.float64) / circ_total
    circ_peak = float(np.max(p))
    circ_mean = 1.0 / float(self._n_bins)
    circ_peak_to_mean = circ_peak / circ_mean if circ_mean > 0 else 0.0
    circ_cv = float(np.std(p)) / circ_mean if circ_mean > 0 else 0.0
    # entropy (base 2)
    nonzero = p[p > 0]
    circ_entropy = float(-np.sum(nonzero * np.log2(nonzero)))
else:
    circ_peak_to_mean = 0.0
    circ_cv = 0.0
    circ_entropy = 0.0
```

#### 允许修改文件

- [`src/jti_extract/ultra/accumulators.py`](src/jti_extract/ultra/accumulators.py:213) — `summary()` 新增 JSON-only flatness fields
- [`tests/test_ultra_accumulators.py`](tests/test_ultra_accumulators.py) — flatness 字段存在性测试

### 判据

`diag_center_circular_min_arc_width_95_ps / frame_length_ps`：

| 比例 | peak_to_mean | 解释 |
|---|---|---|
| ~0.90–0.96 | 明显 > 1 | 未 containment，`T_ridge95 > ~95 µs` |
| ~0.90–0.96 | ≈ 1 | 已近似均匀分布，folded duration 指标失效 |
| < 0.50 且稳定 | — | 已 containment，进入 Stage 14 |
| 0.60–0.85 | — | 过渡区，谨慎进入 Stage 14 |

**关键区分**：如果 `min_arc/frame ≈ 0.95` 且 `peak_to_mean ≈ 1`，不能简单说 "T>100 µs"。这表示 folded center profile 已几乎均匀分布在整个 frame 上，当前 folded duration metric 无法提供有意义的下限。这种情况需要`方向 B`（换物理方法）。

---

## Stage 14: containment sweep（100000/300000/500000/1000000）

### 目标

扫描 10/30/50/100 µs 帧，观察 `circular_min_arc_width_95_ps` 是否出现 plateau。

### 运行表

| N | frame_µs | T/4 origin (ps) | T/2 origin (ps) | 3T/4 origin (ps) |
|---|---|---|---|---|
| 100000 | 10 µs | 2,500,000 | 5,000,000 | 7,500,000 |
| 300000 | 30 µs | 7,500,000 | 15,000,000 | 22,500,000 |
| 500000 | 50 µs | 12,500,000 | 25,000,000 | 37,500,000 |
| 1000000 | 100 µs | 25,000,000 | 50,000,000 | 75,000,000 |

### 每个点输出字段

- `diag_center_circular_min_arc_width_95_ps`
- `diag_center_circular_mass_width_95_ps`
- `min_arc / frame_length`
- `mass_width / frame_length`
- `diag_center_circular_peak_to_mean`
- `diag_center_circular_cv`
- `diag_center_circular_edge_fraction`
- `edge_rejection_ratio`
- `origin_sensitivity_center_width95_max_rel`（如有，从 origin rows 人工提取）
- `n_candidates_after_edge_guard`

### 判据

**情况 A**（`min_arc/frame ≈ 0.90–0.96` 且所有 N 均如此）：
→ 仍未 containment，结论：`T_ridge95 > ~95 µs under current metric`。跳至 Stage 19。

**情况 B**（`min_arc/frame < 0.50` 且相邻 N 间变化 < 10–20%）：
→ containment plateau 已出现，进入 Stage 15 二分搜索。

**情况 C**（`min_arc/frame ≈ 0.90–0.96` 且 `peak_to_mean ≈ 1`）：
→ profile 已近似均匀，folded center metric 失效。进入 Stage 19 方向 B。

**情况 D**（`mass_width` 与 `min_arc_width` 差异大）：
→ wrapping/multimodal 风险，不认证 duration。

---

## Stage 15: 二分搜索 containment duration

在 Stage 14 plateau 附近缩小范围。
假设 Stage 14 显示 30 µs 已 containment 但 10 µs 未 containment：

扫描 N = 150000（15 µs）、200000（20 µs）、250000（25 µs）、300000（30 µs），全部 profile-only。

### 最终估计

```
T_ridge95 ≈ XX µs (from plateau of circular min_arc_width under increasing frame length)
```

不是用某一个 N 的结果，而是用 plateau。

---

## Stage 16: 统计量提升

在候选 N 跑 `max_events = 100000, 300000, 500000`。

### 判据

- `diag_center_circular_min_arc_width_95_ps` 随 max_events 变化 < 10%
- `origin_sensitivity_center_width95_max_rel` < 5–10%
- `edge_rejection_ratio ≤ 2%`

---

## Stage 17: 近似 Schmidt 诊断（仅 containment 后）

### 17A: coarse_N sensitivity

```bash
for CN in 1024 2048 4096 8192; do
  /usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
    --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
    --ch-a 1 --ch-b 3 --max-events 100000 \
    --n-bins <CONTAINMENT_N> --binwidth-ps 100 --frame-origin-ps <APPROVED_ORIGIN> \
    --coincidence-window-ps 200 --edge-guard-ps 200 \
    --coarse-n-bins $CN --truncated-rank 1024 \
    --out /tmp/ultra_stage17_coarse_N${CONTAINMENT_N}_c${CN}_r1024_max100000_$(date +%Y%m%d_%H%M%S)
done
```

### 17B: truncated-rank convergence

```bash
for R in 512 1024 2048 4096; do
  /usr/bin/time -v ~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
    --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
    --ch-a 1 --ch-b 3 --max-events 100000 \
    --n-bins <CONTAINMENT_N> --binwidth-ps 100 --frame-origin-ps <APPROVED_ORIGIN> \
    --coincidence-window-ps 200 --edge-guard-ps 200 \
    --coarse-n-bins <BEST_COARSE_N> --truncated-rank $R \
    --out /tmp/ultra_stage17_trunc_r${R}_N${CONTAINMENT_N}_c${BEST_COARSE_N}_$(date +%Y%m%d_%H%M%S)
done
```

### 17C: block bootstrap（需 proper block bootstrap 集成到 CLI 后进行）

### 认证门槛

| 指标 | 门槛 |
|---|---|
| K_coarse 相邻 coarse_N 变化 | < 10–20% |
| captured_frobenius_energy_r | ≥ 0.9 |
| K_truncated_r 随 r 不再增长 | 可认定为 plateau |
| bootstrap_K_relative_std | < 10–20% |
| svd_nonzero_bins / n_candidates | < 0.3（非 sparse-dominated） |

**不满足则只报**：`Schmidt-like diagnostics remain sparse/truncation limited.`

---

## Stage 18: duration-supported dimension 与 Schmidt-like K 分开报告

### 18.1 duration-supported span

```
d_span ≈ T_ridge95 / bw ≈ XXX bins
conservative d = next lower power of two
radical d = next higher power of two (boundary-limited)
```

### 18.2 Schmidt-like estimate（如果认证门槛通过）

```
Schmidt-like effective mode estimate ≈ K
```

### 18.3 若不满足

```
Schmidt-like diagnostics remain sparse/truncation limited at the containment frame length.
```

---

## Stage 19: 如果 containment 仍未出现

**方向 A**：继续上探
```
N = 2000000 (200 µs)
N = 3000000 (300 µs)
pure profile-only, no SVD
```

**方向 B**：换物理方法
```
因为 folded center profile 已近似均匀，diag_center_width95 不再是有效的 duration 指标。
建议：
- unfolded t_center = (t_a + t_b) / 2 absolute-time profile
- pump coherence / linewidth independent measurement
- JSI linewidth-based estimate
- first-order correlation or Franson-type coherence scan
```

---

## 验收表（最终必须输出）

| N | frame_µs | min_arc_w95_µs | min_arc/frame | mass_w95_µs | peak_to_mean | CV | origin_rel | edge_rej | n_guard | interpretation |
|---|---|---|---|---|---|---|---|---|---|---|
| 32768 | 3.277 | ... | ... | ... | ... | ... | ... | ... | ... | reproducibility |
| 100000 | 10 | ... | ... | ... | ... | ... | ... | ... | ... | probe |
| 300000 | 30 | ... | ... | ... | ... | ... | ... | ... | ... | sweep |
| 500000 | 50 | ... | ... | ... | ... | ... | ... | ... | ... | sweep |
| 1000000 | 100 | ... | ... | ... | ... | ... | ... | ... | ... | upper bound |

**interpretation 规则**：

| 条件 | interpretation |
|---|---|
| `min_arc/frame < 0.5` 且相邻宽度稳定 | `containment observed` |
| `min_arc/frame ≈ 0.95` 且 `peak_to_mean` 高 | `not contained, lower bound` |
| `min_arc/frame ≈ 0.95` 且 `peak_to_mean ≈ 1` | `profile approximately uniform; folded duration metric not informative` |
| `mass_width` 与 `min_arc_width` 差异大 | `wrapping/multimodal risk; do not certify duration` |

---

## 允许修改文件总和（Stage 13-19）

### 算法文件

- [`src/jti_extract/ultra/cli_ultra.py`](src/jti_extract/ultra/cli_ultra.py:39) — `--profile-only` flag
- [`src/jti_extract/ultra/accumulators.py`](src/jti_extract/ultra/accumulators.py:213) — JSON-only flatness fields（peak_to_mean, CV, entropy）
- [`tests/test_ultra_cli_params.py`](tests/test_ultra_cli_params.py) — `--profile-only` 解析测试
- [`tests/test_ultra_accumulators.py`](tests/test_ultra_accumulators.py) — flatness 字段存在性测试

### 文档文件

- [`CURRENT_TASK.md`](CURRENT_TASK.md) — 本文件
- [`RUN_COMMANDS.md`](RUN_COMMANDS.md) — Stage 13-19 命令
- [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) — 阶段结果记录

## 禁止行为

- 不改 baseline CLI/core 代码
- 不改 CSV schema（`SWEEP_SUMMARY_FIELDS` 不变）
- 不改已有 JSON 字段名和语义
- 不改原始 `.ttbin` 数据
- 不改 `results/` 下已有结果
- 不改任何 `/tmp/ultra_stage*` 已有输出目录
- 不允许 cherry-pick best origin 当主结果

## Schema 政策

- JSON-only flatness fields（`diag_center_circular_peak_to_mean`、`diag_center_circular_cv`、`diag_center_circular_entropy`）允许新增
- CSV schema 不变
- `--profile-only` CLI flag 新增，不影响默认行为

## Baseline 政策

- 主分析仍用 `g2_all_candidates`
- strict/nearest/greedy 只作为 diagnostic
- 不改变物理变量含义

## Risks and Rollback

### 风险

| 风险 | 缓解 |
|---|---|
| N=1000000 下 `_circular_mass_width()` O(N²) 复杂度 | 当前实现 O(N·logN)：每个 start（100 万）套 binary search（~log₂1e6≈20），约 2000 万次操作，可能耗时数秒。若不可接受，可考虑用 two-pointer sliding window 降到 O(N) |
| N=1000000 下 `_diag_center_profile` 数组 ~8MB | 安全 |
| peak_to_mean≈1 时结论不满足 | 明确区分 "T>100 µs" 与 "metric失效"，不强制选择 |
| 用户可能跳过 Stage 13A 直接跑 13B | 建议先跑 13A 确认 profile-only 模式正确 |

### Rollback

- `--profile-only` patch 限于 `cli_ultra.py` + 测试，revert 即可
- Flatness fields patch 限于 `accumulators.py` + 测试，revert 即可
- 所有运行写入全新 `/tmp/ultra_stage13*` 等目录，失败可删除

目标不是再跑一个类似 Stage 9 的点，而是证明这个 0.774 µs 不是由 frame origin、linear-center 定义、wrap-around、edge guard 或统计稀疏造成的假象。

### 10.1 明确定义 duration 指标

三个固定指标：

| 字段 | 角色 |
|---|---|
| `diag_center_mass_width_90_ps` | 辅助报告 width90 |
| `diag_center_mass_width_95_ps` | 主报告宽度 |
| `diag_center_peak_time_ps` | peak 时间位置 |

已实现字段见 [`accumulators.py`](src/jti_extract/ultra/accumulators.py:226)。后续所有 sweep 都输出这三个字段。报告中明确区分 `diag_profile_width ≈ 200 ps`（横向厚度）与 `diag_center_width ≈ 0.774 µs`（沿对角线方向持续时间）。

### 10.2 实现 circular-center / wrapped-ridge diagnostic

当前 `center_idx = (ba+bb)//2` 在 `ba≈0, bb≈N-1` 时会错误地映射到 frame 中间。Stage 10.2 需要在 [`FixedLatticeAccumulator`](src/jti_extract/ultra/accumulators.py:19) 中新增 circular-center profile。

#### 算法建议

对每个 masked pair `(ba, bb)`：
1. 计算差值 `delta = (bb - ba) mod N`。
2. 若 `delta > N/2`，则 `bb_unwrapped = bb - N`；否则 `bb_unwrapped = bb`。
3. `circular_center_idx = (ba + bb_unwrapped) // 2`，clip 到 `[0, N-1]`。
4. 用 `np.add.at()` 累积到 `_diag_center_circular_profile`。

#### 候选新增字段（JSON-only, optional）

| 字段 | 含义 |
|---|---|
| `diag_center_circular_peak_bin` | circular center 峰值 bin |
| `diag_center_circular_peak_time_ps` | circular center 峰值时间 |
| `diag_center_circular_mass_width_90_bins` | circular center 90% 质量宽度（bins） |
| `diag_center_circular_mass_width_95_bins` | circular center 95% 质量宽度（bins） |
| `diag_center_circular_mass_width_90_ps` | 同上（ps） |
| `diag_center_circular_mass_width_95_ps` | 同上（ps） |
| `diag_center_circular_edge_fraction` | circular center profile 在 frame 边缘的质量占比 |
| `diag_center_linear_vs_circular_width_ratio` | `linear_width95 / circular_width95` |

#### 允许修改文件

- [`src/jti_extract/ultra/accumulators.py`](src/jti_extract/ultra/accumulators.py:19) — 新增 `_diag_center_circular_profile`、`add_candidates()` 中 circular accumulation、`summary()` 中 circular JSON-only fields
- [`tests/test_ultra_accumulators.py`](tests/test_ultra_accumulators.py) — 新增 circular-center 单元测试，包含非 wrap 和 wrap 场景
- [`tests/test_ultra_sweep_orchestration.py`](tests/test_ultra_sweep_orchestration.py) — 确认 circular JSON-only 字段通过 `run_synthetic_sweep_point()` 传播

#### 验收标准

- 非 wrap pair（`ba=100, bb=102`）：linear/circular center 接近一致
- Wrap pair（`ba=0, bb=N-1`）：linear center 落 `N/2`，circular center 应落边界附近
- 空 profile：所有 circular width 为 0、peak 为 -1
- CSV schema 不变（`SWEEP_SUMMARY_FIELDS` 无新增）
- 若 circular width 接近 0.774 µs，说明 Stage 9 的 0.774 µs 更可信；若 circular width 明显更小，则 linear result 受 wrap-around 展开污染

### 10.3 做 frame-origin recentering sweep

#### 固定参数

```
N = 8192
binwidth_ps = 100
frame_length_ps = 819200
max_events = 100000
coincidence_window_ps = 200
edge_guard_ps = 200
coarse_n_bins = 4096
truncated_rank = 1024
```

#### 扫描 origins

- 精扫：`-300000, -250000, -200000, -189450, -150000, -100000, -50000, 0, 50000 ps`
- 标准四点：`0, T/4, T/2, 3T/4`，其中 `T=819200 ps`，即 `0, 204800, 409600, 614400`

#### 输出与验收

每个 origin 点输出 JSON 含 circular center 字段。判断：

- `diag_center_circular_mass_width_95_ps` 在合理 origin 区间内相对变化 < 10–20%
- `diag_center_circular_peak_time_ps` 不长期贴近 frame 边缘
- `edge_rejection_ratio ≤ 2%`
- 若只有某一个 origin 给出 0.774 µs 而其他差异大 → 不能认证 0.774 µs
- 多个 origins 只做 sensitivity check，不叠加为独立样本

### 10.4 做 frame-length containment sweep

当前 0.774 µs 在 N=8192、frame length 0.8192 µs 下得到，覆盖了 frame 的 94.4%。需要更长 frame 检验。

#### 点位

```
N = 8192      # 0.8192 µs（复用，但需 circular fields 重跑）
N = 12288     # 1.2288 µs
N = 16384     # 1.6384 µs
N = 24576     # 2.4576 µs
N = 32768     # 3.2768 µs
```

#### 每个点输出

- `diag_center_linear_width95_ps`
- `diag_center_circular_width95_ps`
- `diag_center_peak_time_ps`
- `diag_center_edge_fraction`
- `diag_profile_mass_width95_ps`
- `K_coarse`
- `captured_frobenius_energy_r`
- `svd_nonzero_bins / n_candidates_after_edge_guard`
- `edge_rejection_ratio`

#### 验收标准

- `N=12288–32768` 中 `diag_center_circular_width95_ps` 稳定在 `0.7–0.9 µs` → 1.0.774 µs 可升级
- width 随 N 继续增长（如从 0.774 变到 1.2、1.8 µs）→ 0.774 µs 只是 N=8192 的截断下限
- width 在更长 frame 下明显变小 → Stage 9 受 wrap-around 或 origin 影响

### 10.5 做 max_events 收敛

#### 点位

```
N = 8192
N = 16384 或 24576（取 Stage 10.4 中更稳定的那个）
```

#### 每个 N 跑

```
max_events = 100000, 300000, 500000
```

若资源允许，再跑完整 TTBIN。

#### 验收标准

- `diag_center_circular_width95_ps` 随 max_events 变化 < 10–20%
- `K_coarse` 可报告是否仍随 `n_candidates_after_edge_guard` 增长（不要求 Stage 10 中 K 收敛）
- 若 duration 稳定但 K 不稳定 → 报告 "duration credible, Schmidt not certified"

### 10.6 做 method sensitivity

主结果以 `g2_all_candidates` 为准。对 `N=8192, 16384, 24576` 比较 `g2_all_candidates` / `strict_single_hit` / `nearest` / `greedy_unique` / `folded_without_strict`。

#### 实现建议

新增 diagnostics-only helper（不改 baseline），对每种方法生成 pairs → accumulator → 提取 `width95_ps`、`peak_time_ps`、`candidate_count`、`K_coarse`。输出 JSON-only sidecar，不污染主 summary。

#### 验收标准

- `g2_all_candidates` 与 `folded_without_strict` 接近而 `nearest/greedy` 偏窄 → hard-pairing 有 bias，主结果仍用 g2
- 所有方法差异很大 → duration 不能认证，只能作为 method-sensitive diagnostic

---

## Stage 11: 把 0.774 µs 转成 bw=100 ps 下的 duration-supported dimension

### 11.1 基础换算

若最终验证 `T_ridge_95 = 773600 ps`、`binwidth_ps = 100 ps`：

```
d_ridge_95 = floor(773600 / 100) = 7736 bins
```

### 11.2 三档报告

| 档位 | 维度 | 解释 |
|---|---|---|
| 几何上限 | ~7736 | 由 0.774 µs / 100 ps 得到，只是 duration-based span |
| 保守 2-power 维度 | 4096 | 完全小于 7736，比较稳妥 |
| 激进 2-power 维度 | 8192 | 对应 0.8192 µs，略大于 0.774 µs，需非常强的 origin/circular/edge 稳定性支持 |

### 11.3 推荐报告方式

> At binwidth = 100 ps, the measured along-diagonal 95%-mass ridge duration supports an effective time-bin span of approximately 7.7×10^3 bins. A conservative power-of-two discretization is d=4096, while d=8192 is close to the measured ridge extent and should be treated as boundary-limited unless further circular-origin validation is passed.

中文口径：

> 100 ps binwidth 下，0.774 µs 对应约 7700 个 time bins；保守可支持 4096 维，8192 维接近边界，需要额外验证。

---

## Stage 12: 用 Schmidt-like 方法评估维度是否能被认证

必须区分 duration-supported dimension（Stage 11 的 ~7736）与 Schmidt-like effective K（由奇异值谱得到）。

Schmidt 数的常用 effective mode 定义：

```
K = (Σ s_i²)² / (Σ s_i⁴)
```

### 12.1 小维度 exact SVD validation

#### 运行参数

```
N = 512, 1024, 2048, 4096
binwidth_ps = 100
method = g2_all_candidates
origin = Stage 10 通过的 recentered / circular-stable origin
coincidence_window_ps = 200
edge_guard_ps = 200
coarse_n_bins = N（即 exact dense）
truncated_rank = 0（用全 SVD）
```

#### 输出

- `K_exact_dense`
- `singular_spectrum`（可选，JSON sidecar）
- `diag_center_circular_width95_ps`
- `diag_profile_width95_ps`

#### 验收标准

- `K_exact_dense` 随 N 增长趋势合理
- N=4096 时 exact K 接近 4096 且谱较均匀 → 4096 维有希望
- 对角线结构在小 N 中可视化一致

### 12.2 中维度 coarse_N sensitivity

#### 对真实目标 N 扫描 coarse_N

```
N = 8192, 12288, 16384, 24576
coarse_N = 1024, 2048, 4096, 8192
```

#### 输出

- `K_coarse_1024` / `K_coarse_2048` / `K_coarse_4096` / `K_coarse_8192`
- `K_coarse / coarse_N`
- `svd_nonzero_bins / n_candidates_after_edge_guard`
- `captured_frobenius_energy_r`

#### 验收标准

- `K_coarse` 随 coarse_N 继续增长 → 不能认证
- `K_coarse` 在 coarse_N=4096/8192 附近稳定且非 sparse-dominated → 可作为 Schmidt-like 证据
- 历史数据不满足（`svd_nonzero/nguard ≈ 0.57–0.62`，`captured_frobenius_energy_r ≈ 0.55–0.59`）

### 12.3 truncated-rank convergence

#### 对关键点扫描

```
truncated_rank = 512, 1024, 2048, 4096
```

#### 输出

- `K_truncated_512` / `K_truncated_1024` / `K_truncated_2048` / `K_truncated_4096`
- `captured_frobenius_energy_512` / `..._1024` / `..._2048` / `..._4096`
- `K_convergence_vs_r`

#### 验收标准

- `captured_frobenius_energy_r ≥ 0.9` 才能考虑 truncated spectrum 捕获了主要能量
- 若 r=4096 仍只有 0.6–0.7 → 不能认证 full Schmidt number
- 若 `K_truncated_r` 随 r 继续上升 → 不能认证

### 12.4 bootstrap 稳定性

#### 风险警告

现有 [`block_bootstrap_coarse_jti()`](src/jti_extract/ultra/svd_estimators.py:251) 文档明确说明是 prototype, not a proper block bootstrap（`block_size` 被忽略）。在修正前不得用于 certification。

#### 实现建议

1. 按时间轴把 candidate timestamps 分成连续 blocks
2. 重采样 blocks 而非逐 candidate i.i.d.
3. 每个 resample 重新累积 coarse JTI 与 circular width
4. 输出 bootstrap 诊断字段

#### 输出

- `bootstrap_K_mean`
- `bootstrap_K_std`
- `bootstrap_K_relative_std`
- `bootstrap_width95_mean`
- `bootstrap_width95_std`

#### 验收标准

- `diag_center_circular_width95` bootstrap relative std < 5–10% → duration 可信
- `K` bootstrap relative std < 10–20% → Schmidt-like K 才有基本稳定性
- 若 duration 稳定但 K 不稳定 → 报告 duration，不报告 certified Schmidt number

### 12.5 duration-based lower-bound / upper-bound 报告

在 full Schmidt 不可算或不可收敛的情况下，给三类结果：

- **duration-supported span**: `d_span ≈ T_ridge95 / bw ≈ 7736`
- **conservative usable dimension**: `d_conservative = 4096`
- **not certified**: full Schmidt K, d=8192 certification

禁止写成 `Schmidt number = 7736`。

---

## Stage 13: 最终判据与报告口径

### 13.1 0.774 µs 真实性通过条件

必须同时满足：

1. circular-center width95 与 linear-center width95 一致，或差异有明确解释
2. origin recentering 后 width95 稳定，不能只在 origin=0 成立
3. frame-length sweep 中，N=12288/16384/24576 的 width95 不随 N 显著增长
4. max_events sweep 中，width95 不随统计量显著变化
5. method sensitivity 中，g2_all_candidates 与 folded_without_strict 趋势一致
6. edge_rejection_ratio ≤ 2%
7. bootstrap width95 relative std 可接受

> 通过后可写：The along-diagonal bright-ridge duration is approximately 0.77 µs at 95% mass under 100-ps binning.
>
> 未通过则只写：The current linear-center diagnostic gives 0.774 µs, but the value remains origin-/wrapping-sensitive and should be treated as exploratory.

### 13.2 Schmidt-like 认证通过条件

必须同时满足：

1. K_coarse 随 coarse_N 增大趋于稳定
2. K 不再随 max_events 近似线性增长
3. captured_frobenius_energy_r ≥ 0.9
4. bootstrap_K_relative_std 可接受
5. origin_sensitivity_K_max_rel ≤ 5%
6. svd_nonzero_bins / n_candidates 不再处于 sparse-dominated regime

当前项目状态不满足这些条件（见 [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md:1561)）。

---

## 允许修改文件（Stage 10-12）

### 算法/测试文件（可改，最小 patch）

- [`src/jti_extract/ultra/accumulators.py`](src/jti_extract/ultra/accumulators.py:19) — circular-center accumulation + summary fields
- [`tests/test_ultra_accumulators.py`](tests/test_ultra_accumulators.py) — circular-center 单元测试
- [`tests/test_ultra_sweep_orchestration.py`](tests/test_ultra_sweep_orchestration.py) — JSON 字段传播测试
- [`src/jti_extract/ultra/diagnostics_pairing.py`](src/jti_extract/ultra/diagnostics_pairing.py:1) — 新增 per-method full summary helper（最小 patch）
- [`src/jti_extract/ultra/sweep_ultra_jti.py`](src/jti_extract/ultra/sweep_ultra_jti.py:1) — 可选扩展 method_comparison_sweep 返回完整 width95/peak_time/K
- [`src/jti_extract/ultra/svd_estimators.py`](src/jti_extract/ultra/svd_estimators.py:1) — 可选修正/新增 proper block bootstrap

### 文档文件（可改）

- [`CURRENT_TASK.md`](CURRENT_TASK.md) — 本文件
- [`RUN_COMMANDS.md`](RUN_COMMANDS.md) — Stage 10-12 运行命令
- [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) — 阶段结果记录

## 禁止行为

- 不改 [`SWEEP_SUMMARY_FIELDS`](src/jti_extract/ultra/io_ultra.py:22) — CSV schema 保持不变
- 不改原始 `.ttbin` 数据文件
- 不改 `results/` 下已有结果
- 不改任何 `/tmp/ultra_stage*` 已有输出目录
- 不改 `src/jti_extract/cli/` 下旧 baseline CLI
- 不改 `src/jti_extract/core/` 下 baseline 算法
- 不改 `scripts/run_type0ppln_pplus_auto_dim.py`
- 不改旧配置文件
- 不允许 cherry-pick best origin 当主结果
- 不允许把多个 origins 叠加为独立样本
- 不允许用 placeholder bootstrap 硬报 certification

## Schema 政策

- JSON-only optional 新增字段允许——circular-center 字段、per-method 字段、bootstrap 字段
- CSV schema 不变（`SWEEP_SUMMARY_FIELDS` 已固定）
- 已存在的字段（`diag_center_*`）不重命名或改变语义
- `diag_center_linear_vs_circular_width_ratio` 作为 JSON-only diagnostic，无 CSV

## Baseline 政策

- 主分析仍用 `g2_all_candidates`
- strict / nearest / greedy / folded 只作为 diagnostic
- 不改变 `coincidence_window_ps`、`bin_width_ps`、`frame_origin_ps` 物理含义
- 不改变 Schmidt number 计算公式

## Risks and Rollback Strategy

### 全局风险

| 风险 | 缓解 |
|---|---|
| **Wrap-around 定义漂移** | circular-center midpoint 规则必须固定，Stage 10-12 中途不更换定义 |
| **Origin cherry-picking** | 多个 origins 只做 sensitivity check，不叠加为更多样本 |
| **Frame containment 不足** | 0.774 µs 已占 N=8192 frame 的 94.4%，很可能是 lower bound；Stage 10.4 是认证前的硬门槛 |
| **Sparse occupancy** | 历史数据 sparse-dominated；即使 duration 稳定也不能自动认证 Schmidt K |
| **Truncated SVD 能量不足** | 当前 captured_frobenius_energy_r≈0.55–0.59，远低于 0.9；不改善则 not certified |
| **Bootstrap 伪认证** | 现有 placeholder 在 proper block bootstrap 实现前不得用于 certification |
| **运行资源** | coarse_N=8192、truncated_rank=4096 可能显著增加内存/时间；所有运行写入全新 /tmp 目录 |
| **Schema creep** | 已通过 JSON-only + 固定 SWEEP_SUMMARY_FIELDS 控制 |

### Rollback

- Circular-center patch 限于 `src/jti_extract/ultra/accumulators.py` 与测试文件 → revert 即可
- Per-method helper 限于 `diagnostics_pairing.py` + `sweep_ultra_jti.py`，不碰 baseline
- Proper block bootstrap 不稳定时 → 降级为 "bootstrap not available for certification"
- 所有运行输出到全新 `/tmp/ultra_stage10_*`、`/tmp/ultra_stage12_*` → 删除即可
- 不覆盖任何已有结果

## Expected Agent Output

- 最小化 patch
- 不破坏现有测试
- 不改 baseline / schema / 已有输出
- 所有更改可通过 `REVIEW_CHECKLIST.md` 验证
- 完成后更新 `AGENT_HANDOFF.md`，并明确最终结论档位

---

## Stage 20-24: Local Contrast Profile → Aperture Selection → Aperture-Conditioned Schmidt

### 目标

回答三个递进问题：

1. **Stage 20**：在长 frame (10–100 µs) 中，哪些沿对角线方向的 local segment 的 on-diagonal density 显著高于 sideband background？不要求 95% mass 覆盖，只要求 contrast / SNR 统计显著。
2. **Stage 21**：从 Stage 20 的 contrast profile 自动选取有效 temporal aperture（亮区），并验证 aperture 的稳定性（M 一致性、阈值敏感性、train/test split）。
3. **Stage 22-24**：仅在稳定 aperture 内重构局部 JTI、做 Schmidt-like 收敛分析、用 surrogate/control 排除假阳性。

**不做的事**：不对全 frame 做 full SVD；不直接声称 full Schmidt number；不 cherry-pick aperture。

### 允许修改文件

#### 新建模块（最小实现，不碰 baseline）

| 模块 | 职责 |
|---|---|
| [`src/jti_extract/ultra/contrast_profiles.py`](src/jti_extract/ultra/contrast_profiles.py) | `select_contrast_candidates()` + `build_contrast_profile()` |
| [`src/jti_extract/ultra/aperture_select.py`](src/jti_extract/ultra/aperture_select.py) | `select_apertures()`（run-length + threshold） |
| [`src/jti_extract/ultra/aperture_jti.py`](src/jti_extract/ultra/aperture_jti.py) | `build_aperture_accumulator()`（aperture-local lattice） |
| [`src/jti_extract/ultra/surrogate_controls.py`](src/jti_extract/ultra/surrogate_controls.py) | `time_shift_surrogate()` + `phase_shuffle_surrogate()` |

#### 对应测试

| 测试文件 | 覆盖 |
|---|---|
| [`tests/test_ultra_contrast_profiles.py`](tests/test_ultra_contrast_profiles.py) | 5 tests |
| [`tests/test_ultra_aperture_select.py`](tests/test_ultra_aperture_select.py) | 5 tests |
| [`tests/test_ultra_aperture_jti.py`](tests/test_ultra_aperture_jti.py) | 2 tests |
| [`tests/test_ultra_surrogate_controls.py`](tests/test_ultra_surrogate_controls.py) | 4 tests |

#### CLI 新增参数

| 参数 | 默认 | 用途 |
|---|---|---|
| `--contrast-profile` | store_false | 启用 Stage 20 |
| `--contrast-window-ps` | 3000 | 扩大对比度窗口 |
| `--on-diag-band-bins` | 2 | on-diagonal band (bins) |
| `--bg-inner-bins` | 10 | sideband 内边界 |
| `--bg-outer-bins` | 30 | sideband 外边界 |
| `--center-coarse-bins` | [512, 1024] | M 值 |
| `--select-aperture` | store_false | 启用 Stage 21 |
| `--aperture-threshold` | snr3 | snr3/snr5/contrast2/contrast5 |
| `--aperture-min-run-segments` | 3 | 连续达标最小段数 |
| `--aperture-max-gap-segments` | 1 | 合并允许的最大间隔 |

所有参数为 optional，不改变已有参数默认值或语义。

### 禁止行为

- 不改 [`SWEEP_SUMMARY_FIELDS`](src/jti_extract/ultra/io_ultra.py:22) — CSV schema 保持不变
- 不改 [`accumulators.py`](src/jti_extract/ultra/accumulators.py) — baseline 行为不变
- 不改 [`g2_accumulate.py`](src/jti_extract/ultra/g2_accumulate.py) — `all_candidates()` 语义不改
- 不改 `src/jti_extract/cli/`、`src/jti_extract/core/`、`scripts/`、`configs/`
- 不改原始 `.ttbin`、`results/`、已有 `/tmp/ultra_stage*` 输出目录

### Schema 政策

- New-stage CSV/JSON 写入独立文件（`diag_contrast_profile_*.csv`、`effective_aperture_summary.csv`），不加入现有 `ultra_summary.csv`
- 现有 `SWEEP_SUMMARY_FIELDS` 不变
- `coarse_jti` 矩阵不写入 CSV/JSON，只用于内存 SVD

### Baseline 政策

- `all_candidates()` 仍用 `coincidence_window_ps=200`
- Contrast profile 用独立 `contrast_window_ps=3000` 做扩大窗口选择
- 主分析仍用 `g2_all_candidates`
- Schmidt number 计算公式不变

### Stage 20 实施要点

```python
def select_contrast_candidates(t_a, t_b, contrast_window_ps) -> (ca, cb, delta):
    """返回 |t_a - t_b| <= contrast_window_ps 的 candidate"""

def build_contrast_profile(ca, cb, delta, ...) -> dict:
    """bincount per-segment; sideband_zero → contrast_ratio=None; SNR=sqrt(on) when sb=0"""
```

固定参数：`binwidth=100, cw=3000, on_diag_band=2, bg_inner=10, bg_outer=30, max_events=100000`。扫描 `N = 100000, 300000, 500000, 1000000`。输出 `diag_contrast_profile_N{N}_M{M}.csv`。

### Stage 21 验收

对所有阈值 `snr3/snr5/contrast2/contrast5` 输出 aperture 列表。检查 M=512 与 M=1024 位置一致性。报告 `n_sideband_zero_segments`。

### Stage 22 要点

aperture-local lattice: `aperture_n_bins = floor(duration / binwidth)`, `aperture_origin_ps = start_ps`。输出 `aperture_folding_mode = "phase-folded-across-global-frames"`。

### Stage 23 要点

扫 `coarse_N = 16, 32, 64, 128`（不超过 `aperture_n_bins`）。输出 `K_coarse`、`nonzero_bins`、`n_candidates_in_aperture`。

**不认证**：K 线性增长或统计稀疏 → "exploratory only"

### Stage 24 要点

Time-shift: shift B by 10 ns, 100 ns, 1 µs（absolute-time coincidence 破坏检查）。Phase-shuffle: preserve frame index, shuffle frame phase（frame marginal 检查）。

### 认证门槛

Stage 20-24 的结果必须在**全部满足**以下条件时才可升级为科学声明。

1. **Phase-shuffle surrogate** `max(SNR) / max(SNR_surr) >= 1.5`。
2. **Aperture selection** `snr3` 与 `snr5` 在 M=512 和 M=1024 下位置大体一致。
3. **Aperture 内** `n_sideband_zero_segments / n_segments < 0.5`。
4. **coarse_N sensitivity** `K_coarse` 相邻 coarse_N 变化 < 20%。
5. **统计量** `n_candidates_in_aperture >= 1000`。
6. 满足前述 5 条后才进入 Stage 23B rank/bootstrap 认证。

### 已知剩余问题（当前未满足 gate）

| 问题 | 状态 |
|---|---|
| phase-shuffle surrogate 未降低 contrast | ❌ 1.00× |
| sideband_zero 占 53% aperture | ❌ 最大 aperture 52% |
| aperture 统计稀疏，283 candidates | ❌ K 线性增长 |
| coarse 映射非整除 | ⚠️ 末端 clip |
| `--out` 覆盖风险 | ❌ `exist_ok=True` |

### Risks and Rollback

所有新文件独立于已有模块，删除即可。CLI 参数全部为 optional。不修改已有 schema/baseline。

---

## Stage 25-27: Contrast Diagnostic Hardening → Re-aperture → Schmidt（仅 gate 通过后）

### 1. 背景

Stage 20-24 发现了一个 robust 的 on-diagonal 富集结构，但未能认证为局部亮区。三个核心否定证据：

| 问题 | 数据 | 影响 |
|---|---|---|
| **sideband 太窄** | bg_outer=30 bins (3 ns) → 53% segments sideband=0 | SNR 和 contrast 被 sideband 稀疏污染 |
| **phase-shuffle 未降 contrast** | true/surr=1.00 | contrast 由 frame-phase marginal 决定 |
| **aperture 统计稀疏** | 283 candidates，K 线性增长 | Schmidt 认证不成立 |

Stage 25-27 的目标是**不再继续追 Schmidt number**，而是先修正 contrast profile 的背景估计和 surrogate 统计，把 Stage 20 的 contrast 变成一个更可靠的可解释量。

### 2. 进入 Stage 26（re-aperture）的门槛

以下条件**必须全部满足**才进入 Stage 26：

| 条件 | 门槛 |
|---|---|
| sideband_zero_fraction | < 20% |
| phase-shuffle z-score | ≥ 3 或 percentile ≥ 95% |
| snr_valid_bg 下连续 aperture | 至少存在 1 个 |
| M=512 vs M=1024 位置一致 | 人工审查一致 |
| n_candidates_in_aperture | ≥ 1000 |

**如果 phase-shuffle 多次分布后仍不显著低于 true，则永久停止 aperture/Schmidt 路线。**

### 3. 允许修改文件

#### 修改文件（最小 patch）

| 文件 | 修改内容 |
|---|---|
| [`src/jti_extract/ultra/contrast_profiles.py`](src/jti_extract/ultra/contrast_profiles.py:144) | 新增 `snr_raw` / `snr_valid_bg` 字段；sideband=0 时 `snr_valid_bg=None` |
| [`src/jti_extract/ultra/aperture_select.py`](src/jti_extract/ultra/aperture_select.py:113) | 默认使用 `snr_valid_bg`；新增 `--aperture-use-raw-snr` 保留旧行为 |
| [`src/jti_extract/ultra/surrogate_controls.py`](src/jti_extract/ultra/surrogate_controls.py:61) | 新增 `phase_shuffle_multi()`：N 次 shuffle 返回分布统计 |
| [`src/jti_extract/ultra/cli_ultra.py`](src/jti_extract/ultra/cli_ultra.py:327) | 修复 `--out` 覆盖风险；新增 `--overwrite`、`--phase-shuffle-n`、`--bg-outer-bins` 多值 |

#### 新建文件

| 文件 | 职责 |
|---|---|
| [`tests/test_ultra_contrast_hardening.py`](tests/test_ultra_contrast_hardening.py) | snr_valid_bg + phase_shuffle_multi 测试 |

### 4. 禁止行为

- 不改 [`SWEEP_SUMMARY_FIELDS`](src/jti_extract/ultra/io_ultra.py:22) — CSV schema 不变
- 不改 [`accumulators.py`](src/jti_extract/ultra/accumulators.py) — baseline 行为不变
- 不改 [`g2_accumulate.py`](src/jti_extract/ultra/g2_accumulate.py) — `all_candidates()` 语义不改
- 不改 `src/jti_extract/cli/`、`src/jti_extract/core/`、`scripts/`、`configs/`
- 不改原始 `.ttbin`、`results/`、已有 `/tmp/ultra_stage*` 输出目录

### 5. Schema 政策

- `diag_contrast_profile_*.csv` 新增列：`snr_raw`、`snr_valid_bg`、`is_snr3_valid_bg`、`is_snr5_valid_bg`。旧列 `snr`、`is_snr3`、`is_snr5` 保留不变。
- JSON-only 新增 `phase_shuffle_max_snr_mean`、`phase_shuffle_max_snr_std`、`true_zscore_vs_shuffle`、`true_percentile_vs_shuffle`。
- CLI 新增参数全部 optional。现有参数默认值/语义不变。

### 6. Stage 25 实施步骤

#### Stage 25A: 扩大 sideband + snr_valid_bg

在 [`contrast_profiles.py`](src/jti_extract/ultra/contrast_profiles.py:144) 新增：
```python
"snr_raw": float(snr_raw[seg]),         # 当前 snr（不改）
"snr_valid_bg": float(...),              # sideband=0 → None
"is_snr3_valid_bg": bool(...),
"is_snr5_valid_bg": bool(...),
```

在 [`aperture_select.py`](src/jti_extract/ultra/aperture_select.py:113) 中，`snr3`/`snr5` threshold 默认读取 `snr_valid_bg`（若存在）而非 `snr`。

CLI 支持 `--bg-outer-bins 50 100 200`（多值 sweep）：

```bash
~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 100000 \
  --n-bins 300000 --binwidth-ps 100 \
  --contrast-profile --contrast-window-ps 3000 \
  --on-diag-band-bins 2 --bg-inner-bins 10 \
  --bg-outer-bins 50 100 200 \
  --center-coarse-bins 256 512 1024 \
  --profile-only \
  --out /tmp/ultra_stage25A_N300000_bgwide_$(date +%Y%m%d_%H%M%S)
```

**判据**：
- `sideband_zero_fraction < 0.2` 基本可用
- `sideband_zero_fraction < 0.1` 较好
- 如果扩大 sideband 后 contrast 大幅降低，说明之前的 aperture 是 sideband 稀疏伪影

#### Stage 25B: 重跑 Stage 20（扩大 bg_outer）

仅两个最有信息量的 N：**N=300000 和 N=1000000**。全部参数同上。

#### Stage 25C: phase-shuffle 多次分布

在 [`surrogate_controls.py`](src/jti_extract/ultra/surrogate_controls.py:61) 新增：
```python
def phase_shuffle_multi(t_a, t_b, n_shuffles=20, seed=42, **params) -> dict:
    """Run n_shuffles times, return distribution stats."""
    # Returns: max_snr_mean, max_snr_std, true_zscore, true_percentile
```

CLI 新增 `--phase-shuffle-n 20`。

**认证门槛**：`true_zscore_vs_shuffle >= 3` 或 `true_percentile_vs_shuffle >= 95%`。

```bash
~/envs/timetagger/bin/python -m jti_extract.ultra.cli_ultra \
  --ttbin "/home/karel_303/data/Type0ppln JTI/TimeTags_2026-04-03_213758.ttbin" \
  --ch-a 1 --ch-b 3 --max-events 100000 \
  --n-bins 300000 --binwidth-ps 100 \
  --contrast-profile --contrast-window-ps 3000 \
  --on-diag-band-bins 2 --bg-inner-bins 10 --bg-outer-bins 50 \
  --center-coarse-bins 512 \
  --phase-shuffle-n 20 \
  --profile-only \
  --out /tmp/ultra_stage25C_N300000_pshuffle20_$(date +%Y%m%d_%H%M%S)
```

#### Stage 25D: time-shift 扩大范围

**目的**：看 contrast 消失的 delay scale，找局部 timing correlation 的特征时间。

**参数**：`shift_ps = 5000, 10000, 30000, 100000, 1000000, 10000000`

**输出**：`contrast_decay_vs_shift.csv`

#### Stage 25E: 修复 --out 覆盖风险

在 [`cli_ultra.py`](src/jti_extract/ultra/cli_ultra.py:327) 中：
- 默认：`--out` 若目录已存在且非空 → `FileExistsError`
- 新增 `--overwrite` flag：允许覆盖
- 新增 `--append` flag：允许追加到已有目录

### 7. Stage 26: Re-aperture selection（仅 gate 通过后）

重复 Stage 21，使用 `snr_valid_bg` + `--aperture-require-sideband`。输出 snr3/snr5/contrast2/contrast5 四档 aperture。验收 M=256/512/1024 下位置一致性。

### 8. Stage 27: Aperture-conditioned Schmidt（仅 stable aperture 存在后）

只在 Stage 26 筛出稳定 aperture 后执行。重复 Stage 23，但必须满足：
- `coarse_N` 16/32/64/128/256 相邻 K 变化 < 20%
- `n_candidates_in_aperture ≥ 1000`
- `captured_frobenius_energy_r ≥ 0.9`
- `bootstrap_K_relative_std < 10–20%`

### 9. 执行顺序

| 优先级 | Stage | 内容 |
|---|---|---|
| 最高 | 25E | 修复 `--out` 覆盖风险 |
| 高 | 25A | snr_valid_bg 字段 + `--bg-outer-bins` 多值 |
| 高 | 25B | 重跑 N=300000/1000000 contrast profile（bg_outer=50/100/200） |
| 高 | 25C | phase-shuffle 20 次分布 |
| 中 | 25D | time-shift decay scale |
| — | 26 | **BLOCKED** — phase-shuffle zscore=0.00 (< 3), gate not satisfied |
| — | 27 | **BLOCKED** — no stable aperture exists after Stage 25 gate failure |

---

## Current Status (Archived)

Project archived: **2026-05-01**.

### Final conclusion

- **Reliable result**: Transverse JTI timing-correlation width ≈ 200 ps (`diag_profile_mass_width_95_bins = 2` at 100 ps binning).
- **Not certified**: Physical along-diagonal temporal duration (0.774 µs was frame-containment artifact; `min_arc_width/frame ≈ 0.94` across all frames up to 100 µs, no plateau).
- **Not certified**: Local temporal aperture (phase-shuffle 20× reproduced contrast identically, zscore=0.00. Aperture/Schmidt route is **permanently blocked** under the current contrast metric.)
- **Not certified**: Full Schmidt number (K not convergent; sparse occupancy dominated).
- **Not certified**: Aperture-conditioned Schmidt-like K (aperture gate failed first).

### Gate summary (Stage 25-27)

| Condition | Actual | Threshold | Status |
|---|---|---|---|
| sideband_zero_fraction (500k events) | 3% | < 20% | ✅ |
| snr_valid_bg under snr5 (500k events) | 496/512 | ≥ 1 | ✅ |
| **phase_shuffle true_zscore (20×)** | **0.00** | **≥ 3** | **❌ BLOCKED** |
| M=512 vs M=1024 aperture consistency | n/a | consistent | — |
| n_candidates_in_aperture | 28234 | ≥ 1000 | ✅ |

**Phase-shuffle gate failed (zscore=0.00). Stage 26 (re-aperture) and Stage 27 (aperture-conditioned Schmidt) are permanently blocked.**

### Next directions

Future work should move to:
1. **Physical methods**: JSI/MUB/Franson/delay-line/pump coherence (complementary-basis certification).
2. **Synthetic Schmidt methodology**: Separate study of coarse/truncated SVD convergence under known ground truth.

Refer to [`docs/ULTRA_JTI_FRAME_LENGTH_CLOSURE_REPORT.md`](docs/ULTRA_JTI_FRAME_LENGTH_CLOSURE_REPORT.md) for the full closure report.
