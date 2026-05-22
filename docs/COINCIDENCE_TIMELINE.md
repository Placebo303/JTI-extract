# Coincidence Timeline and Folded-Time Diagnostics

This project includes a standalone diagnostic for checking how coincidence pairs are distributed over acquisition time. It is separate from dense JTI extraction.

## Absolute acquisition-time timeline

Use:

```bash
python scripts/analyze_ttbin_coincidence_timeline.py --input "<data.ttbin>" --channels 1 3 --coinc-window-ps 200 --pairing-mode all_pairs --time-bin-s 0.01 --output-dir results/coincidence_timeline
```

The script pairs channel events, computes each coincidence midpoint,

```text
t_c = (t_a + t_b) / 2
```

and histograms `t_c` across the full acquisition span. The default plot uses coincidence rate in counts per second.

Outputs:

- `coincidence_timeline.csv`
- `coincidence_timeline.png`
- `coincidence_timeline_summary.json`

The summary includes event counts, total coincidences, average rate, histogram statistics, and `std_counts_over_poisson`. Values near 1 indicate Poisson-limited fluctuations at the selected time-bin size.

## Optional diagonal-band filter

The timeline script can optionally keep only pairs that land near the frame-local JTI diagonal:

```bash
python scripts/analyze_ttbin_coincidence_timeline.py --input "<data.ttbin>" --channels 1 3 --coinc-window-ps 200 --pairing-mode all_pairs --time-bin-s 0.01 --jti-binwidth-ps 400 --frame-bins 4500 --diag-halfwidth-bins 1 --output-dir results/coincidence_timeline_diag
```

This filter is optional. By default the script analyzes all coincidence pairs in absolute acquisition time.

## Type0ppln observation from the accepted run

For `TimeTags_2026-04-03_213758.ttbin`, channels `1,3`, `coinc-window-ps=200`, and `pairing-mode=all_pairs`:

- total coincidences: `646811`
- average rate: about `2.16e5 cps`
- with `time-bin-s=0.01`, `std_counts_over_poisson` was about `1.0007`

This indicates a stable acquisition at the 10 ms timescale.

A folded-time check over candidate total periods from `3 us` to `40 us`, using `20 ns` bins, did not show a strong concentration region or decay envelope. The folded histograms were close to Poisson-limited fluctuations. For the current data, the strong JTI diagonal is therefore not evidence of a microsecond-scale coincidence burst within those candidate periods; it is better interpreted as stable channel-to-channel timing correlation across the acquisition.
