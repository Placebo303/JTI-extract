# 数据格式

## 输入

### .ttbin 文件（必需）

Swabian TimeTagger 原始事件文件，由 TimeTagger 软件采集。

- `--ttbin` 指向 **`.1.ttbin` 数据分片**；同目录下名为 `*.ttbin` 的 0 字节文件只是占位符，不能当输入。
- 读取依赖 Swabian 的 Python API（`TimeTagger.FileReader`），该 API 不在 PyPI 上，安装/配置见
  [TROUBLESHOOTING.md](TROUBLESHOOTING.md)。
- 只使用 event type = 0 的记录，按通道号拆成 A / B 两路时间标签。
- **通道号必须与数据一致**：`--raw-ch-a-id` / `--raw-ch-b-id` 默认 2 / 3；FP #1、FP #2（DF776.348）这批数据是
  **A=1 / B=3**。选错会报 `No events found for channel A=... / B=...`，并列出该文件里实际存在的通道号。
- 只要给了 `.ttbin`，`tau_align_ps` 就可以从两路时间标签的（加窗）互相关自动确定，
  **不需要额外的延时峰表**（算法见 [CLI.md](CLI.md)）。
- 事件的绝对数量和采集时长决定互相关峰的显著性：样本太少/没有符合时自动估计会告警（<5σ）
  或直接报错，这时改用 peaks CSV 或显式 `--tau-align-ps`。

### peaks CSV（可选）

只在需要“由最亮峰确定 `tau_align_ps`”时才需要提供；不给它就用互相关自动估计。

最少两列即可：

```csv
delay_ps,counts
-126.0,312.0
-106.0,180.0
-146.0,240.0
```

| 列 | 类型 | 说明 |
|---|---|---|
| `delay_ps` | float | 延时值（ps） |
| `counts` | float | 该延时处的计数 |

- 程序只取 `counts` 最大那一行的 `delay_ps` 作为 `tau_align_ps`（`tau_align_source = "brightest_peak"`）。
- 其余列（`smoothed_counts`、`relative_to_main`、`bin_index` 等）会被忽略。
- 因此**整条延时直方图 CSV 也能直接用**（每行一个 bin）：最亮那一行就是符合峰 bin 的中心，
  `tau_align_ps` 会量化到该直方图的分箱宽度（例如 10 ps 箱 → 10 ps 台阶）。
- 想复现历史“300 ps 平滑峰”的口径时，直方图最亮 bin 通常不够：把峰位算好后直接写一行
  `delay_ps,counts`，或改用 `--tau-align-ps`。
- 可由 `archived/diagnostics/analyze_interchannel_delay.py` 生成
  （参数与输出见 [该目录 README](../archived/diagnostics/README.md)），也可由任何能写出
  `delay_ps,counts` 两列的工具产生。
- 给了 `--peaks-csv` 但文件不存在、且没有被 `--tau-align-ps` / `--tau-auto` 短路 → `SystemExit`：
  `peaks CSV not found: ...`。去掉该参数即可改用互相关。
- 给了 `--peaks-csv` 但最亮 `counts <= 0`（空表/全零）→ `Cannot determine tau_align_ps: ...`，
  同样不会自动回退到互相关。

### 一致性要求

- **channels 必须与数据一致**：通道号是 TimeTagger 的逻辑通道，写错只会读到空数组（报错）或读到错的两路。
- 同一个 `.ttbin` + 相同通道 + 相同 `--max-events` 会命中 `_tag_cache`
  （`<out>/_tag_cache/tags_cache_ch{A}_ch{B}.npz`，key = ttbin 绝对路径 + 大小 + mtime + 通道 + `--max-events`）。
- 换 `--out` 目录、改 `--max-events`、改通道号，或 `.ttbin` 被覆盖/改名/mtime 变化，都会重新解析 ttbin。
- 调 `--tau-*` / `--delay-*` / `--binwidth-ps` 等参数不会让缓存失效（缓存里只有 A/B 时间标签），
  可以放心反复试参数。

## 输出文件

见 [OUTPUTS.md](OUTPUTS.md)。
