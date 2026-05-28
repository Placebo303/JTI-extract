# Coincidence Timeline and Folded-Time Diagnostics

This project includes a standalone diagnostic for checking how coincidence pairs are distributed over acquisition time. It is separate from dense JTI extraction.

## Absolute acquisition-time timeline

Use:

```bash
python scripts/analyze_ttbin_coincidence_timeline.py \
  --input "<data.ttbin>" \
  --channels 2 3 \
  --coinc-window-ps 200 \
  --pairing-mode all_pairs \
  --time-bin-s 0.01 \
  --output-dir results/coincidence_timeline
```

The script pairs channel events, computes each coincidence midpoint,

```text
t_c = (t_a + t_b) / 2
```

and histograms `t_c` across the full acquisition span. The default plot uses coincidence rate in counts per second.

## Outputs

- `coincidence_timeline.csv`: acquisition-time bins with coincidence counts and rate
- `coincidence_timeline.png`: coincidence rate versus acquisition time
- `coincidence_timeline_summary.json`: input parameters, event counts, pair counts, histogram statistics, and Poisson comparison

The summary includes event counts, total coincidences, average rate, histogram statistics, and `std_counts_over_poisson`. Values near 1 indicate Poisson-limited fluctuations at the selected time-bin size.

## Optional diagonal-band filter

The timeline script can optionally keep only pairs that land near the frame-local JTI diagonal:

```bash
python scripts/analyze_ttbin_coincidence_timeline.py \
  --input "<data.ttbin>" \
  --channels 2 3 \
  --coinc-window-ps 200 \
  --pairing-mode all_pairs \
  --time-bin-s 0.01 \
  --jti-binwidth-ps 400 --frame-bins 4500 --diag-halfwidth-bins 1 \
  --output-dir results/coincidence_timeline_diag
```

This filter is optional. By default the script analyzes all coincidence pairs in absolute acquisition time.

## Interpretation

- Stable `std_counts_over_poisson` near 1.0 indicates Poisson-limited fluctuations
- Deviations may indicate drift, burst noise, or rate modulation
- A folded-time check over candidate periods can reveal microsecond-scale structure
