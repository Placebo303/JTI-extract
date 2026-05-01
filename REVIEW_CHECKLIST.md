# REVIEW_CHECKLIST.md

## 审查格式

每个项目必须标记：✅ 通过 / ⚠️ 需要注意 / ❌ 未通过 / N/A 不适用

**审查者必须在每一项后面填写简要说明**

---

### 1. Schema Impact

- [ ] CLI 参数名称和语义未改变
  - 说明：
- [ ] CSV 列名和顺序未改变
  - 说明：
- [ ] JSON/YAML 配置键未改变
  - 说明：
- [ ] 函数签名未改变（尤其是 [`run_extract()`](src/jti_extract/cli/extract.py) 及 core 模块公共 API）
  - 说明：
- [ ] 输出文件命名约定未改变
  - 说明：
- [ ] Type0ppln CSV 列定义未改变（[`SUMMARY_FIELDS`](scripts/run_type0ppln_pplus_auto_dim.py:34)、[`FILE_SUMMARY_FIELDS`](scripts/run_type0ppln_pplus_auto_dim.py:76)、[`DEDUPE_FIELDS`](scripts/run_type0ppln_pplus_auto_dim.py:93)、[`AUTO_DECISION_FIELDS`](scripts/run_type0ppln_pplus_auto_dim.py:104)）
  - 说明：

### 2. Baseline Impact

- [ ] JTI 提取算法语义未改变
  - 说明：
- [ ] Schmidt 分析算法语义未改变
  - 说明：
- [ ] TDC 诊断算法语义未改变
  - 说明：
- [ ] Type0ppln `P_plus` 分析算法语义未改变
  - 说明：
- [ ] 科学计算结果的含义未改变
  - 说明：
- [ ] 高维 `P_plus` 仍使用稀疏 profile 逻辑（未引入 dense 矩阵）
  - 说明：

### 3. Raw Data Overwrite Risk

- [ ] 不修改任何 `*.ttbin` 原始数据文件
  - 说明：
- [ ] 不修改外部原始数据目录
  - 说明：
- [ ] 路径使用合理的写入保护机制
  - 说明：

### 4. Result Overwrite Risk

- [ ] 不覆盖 `results/` 目录下已有生成物
  - 说明：
- [ ] 不覆盖时间戳命名的输出目录（如 `pplus_auto_dim_*`）
  - 说明：
- [ ] 新输出使用唯一目录名称（推荐时间戳）
  - 说明：
- [ ] 不覆盖 `examples/tiny_run/expected_outputs/` 下的预期输出
  - 说明：

### 5. Path Mixing Risk

- [ ] 不使用硬编码的 Windows 绝对路径作为执行路径
  - 说明：
- [ ] Windows 历史路径已标注为 `legacy Windows path`
  - 说明：
- [ ] 所有新命令使用 POSIX 路径格式
  - 说明：
- [ ] 路径处理支持空格和特殊字符
  - 说明：
- [ ] `scripts/run_type0ppln_pplus_auto_dim.py` 的 `DEFAULT_DATA_ROOT` 未被当作 WSL 默认路径
  - 说明：

### 6. Scope Creep

- [ ] 仅修改了 `CURRENT_TASK.md` 允许的文件
  - 说明：
- [ ] 没有进行不必要的大规模重构
  - 说明：
- [ ] 修改范围与任务目标一致
  - 说明：
- [ ] 未引入新的公共 API 或 CLI 参数
  - 说明：

### 7. Long-Running Command Risk

- [ ] 没有引入新的默认长运行命令
  - 说明：
- [ ] 重型命令已标记为 "Do not run by default"
  - 说明：
- [ ] 如有运行时间超过 5 分钟的命令，已在 [`RUN_COMMANDS.md`](RUN_COMMANDS.md) 中标注
  - 说明：
- [ ] 未将 `*.ttbin` 完整处理命令加入默认执行流程
  - 说明：

### 8. Scientific Semantic Drift

- [ ] Schmidt number 和 singular spectrum weights 含义保持不变
  - 说明：
- [ ] JTI raw counts CSV 数值保持不变
  - 说明：
- [ ] TDC residue histograms 语义保持不变
  - 说明：
- [ ] Type0ppln `P_plus_central_95_width_ps`、`width_ratio_95`、`edge_fraction`、`relative_change_W95`、`covered`、`final_status` 含义保持不变
  - 说明：
- [ ] Pairing rule 语义未改变（nearest-neighbor / greedy-unique）
  - 说明：
- [ ] `coincidence_window_ps` 与 `bin_width_ps` 的独立性未破坏
  - 说明：

### 9. Ultra-high-dimensional JTI Sweep Gates

- [ ] ultra 主流程基于 fixed global frame lattice，未使用 per-pair origin 构造 global JTI
  - 说明：
- [ ] `strict_single_hit`、`nearest`、`greedy_unique` 仅作为 diagnostics，未被写成主物理配对算法
  - 说明：
- [ ] `g2_all_candidates` 使用固定 physical `coincidence_window_ps`，未随 `frame_length_ps` 自动放大
  - 说明：
- [ ] 主 JTI 使用 edge guard，并输出或规划输出 `edge_rejection_ratio`
  - 说明：
- [ ] 多 `frame_origin_ps` 仅用于 sensitivity check，未叠加为独立样本
  - 说明：
- [ ] 超高维默认不输出 full dense `N x N` CSV，而使用 coarse / sparse / tiled / diagonal-profile 输出
  - 说明：
- [ ] ultra 主结果保持 raw nonnegative counts；未默认扣除 background，也未把 background-subtracted signed spectrum 写成主结果
  - 说明：
- [ ] truncated SVD 报告 captured energy；captured energy 不足时未声称 full Schmidt number
  - 说明：
- [ ] bootstrap stability 使用 block bootstrap 或明确说明采样假设
  - 说明：
- [ ] TTBIN offline loads use `TimeTagger.FileReader()` rather than `createTimeTaggerVirtual()` unless virtual replay license/hardware has been explicitly validated
  - 说明：

---

## 审查总结

- 审查者：
- 日期：
- 总体结论：✅ 可合并 / ⚠️ 需要修改 / ❌ 拒绝合并
- 修改建议：
