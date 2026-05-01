# Ultra JTI Frame-Length Exploration: Closure Report

> **Project status**: archived.
>
> **Final scientific level**: negative result + reusable diagnostic toolchain.
>
> **Certified result**: transverse timing-correlation width ≈ 200 ps.
>
> **Not certified**: physical along-diagonal temporal duration, local temporal aperture, full Schmidt number, aperture-conditioned Schmidt-like K.

---

## 1. Executive Summary

- **Problem**: Determine whether raw folded-frame JTI intensity can define a physical along-diagonal temporal aperture and support a certified Schmidt number.
- **Approach**: Fixed-lattice G2-like ultra-JTI pipeline with folded-center width, circular min-arc width, local diagonal contrast profile, aperture selection, aperture-local JTI reconstruction, coarse/truncated SVD diagnostics, and surrogate controls.
- **Positive result**: The **transverse timing-correlation width** (across the anti-diagonal direction, i.e., `t_s - t_i`) is stable at approximately **200 ps** at 100 ps binning, consistent across frames from 0.819 µs to 100 µs.
- **Negative result 1**: The `0.774 µs` value from Stage 9 was a frame-containment artifact of the shortest frame (`N=8192`). `diag_center_width95 ≈ 0.94–0.95 × frame_length` across all tested frames, with no plateau.
- **Negative result 2**: Local diagonal contrast, while reduced by time-shift controls, is **completely preserved by phase-shuffle controls** (20× shuffle, zscore=0.00). Therefore the contrast is dominated by frame-phase marginal / occupancy patterns and **cannot be interpreted as a local temporal aperture**.
- **Negative result 3**: Aperture-conditioned Schmidt-like K **grows linearly with coarse_N**, is statistics-limited (283 candidates in the best aperture), and cannot be certified.
- **Why raw folded JTI cannot certify**: The along-diagonal intensity in a folded frame reflects pair-generation time, acquisition stability, frame-phase marginal occupancy, and finite sampling—not pump coherence or effective dimension.
- **Way forward**: Physical methods (JSI/MUB/Franson/delay-line/pump coherence) or a separate methodological study of Schmidt-like estimator validity under sparse/coarse/truncated regimes.

---

## 2. Background and Motivation

The initial question was:

> Given a Type0ppln P_plus JTI dataset (100 ps binning, coincidence window 200 ps), can the along-diagonal bright-ridge width be used to estimate the effective time-bin span that supports a high-dimensional Schmidt-like decomposition?

The initial hypothesis was that increasing the frame length would eventually reveal a containment plateau in the along-diagonal 95% mass width, giving a physical duration estimate. Frame-length values from 0.819 µs (`N=8192`) up to 100 µs (`N=1,000,000`) were tested.

A secondary goal was to use the selected temporal aperture to construct an aperture-local JTI and estimate an aperture-conditioned Schmidt-like K that could approximate the effective mode number.

Neither goal was reached. The results are negative but clarify several important failure modes.

---

## 3. Pipeline Built

The following toolchain was developed and tested:

### Core pipeline (source path: [`src/jti_extract/ultra/`](../src/jti_extract/ultra/))

| Module | Function |
|---|---|
| [`cli_ultra.py`](../src/jti_extract/ultra/cli_ultra.py) | CLI entry point with 33+ parameters; supports TTBIN and pre-loaded array modes |
| [`accumulators.py`](../src/jti_extract/ultra/accumulators.py) | `FixedLatticeAccumulator`: frame lattice, edge guard, diagonal/center/circular-center profiles, min-arc width, flatness diagnostics |
| [`fold_lattice.py`](../src/jti_extract/ultra/fold_lattice.py) | Fixed global frame lattice: `frame_length_ps()`, `phase_in_frame()`, `bin_indices()` |
| [`g2_accumulate.py`](../src/jti_extract/ultra/g2_accumulate.py) | Chunked all-candidates coincidence iterator using fixed physical `coincidence_window_ps` |
| [`contrast_profiles.py`](../src/jti_extract/ultra/contrast_profiles.py) | Per-segment on-diagonal vs sideband contrast profile with `snr_raw` / `snr_valid_bg` fields |
| [`aperture_select.py`](../src/jti_extract/ultra/aperture_select.py) | Run-length + threshold aperture selection; `require_sideband` option |
| [`aperture_jti.py`](../src/jti_extract/ultra/aperture_jti.py) | Aperture-local JTI reconstruction with phase-folded-across-global-frames lattice |
| [`surrogate_controls.py`](../src/jti_extract/ultra/surrogate_controls.py) | Time-shift and phase-shuffle surrogates; `phase_shuffle_multi()` distribution stats |
| [`svd_estimators.py`](../src/jti_extract/ultra/svd_estimators.py) | `svd_coarse_jti()`, `truncated_schmidt_summary()`, `block_bootstrap_coarse_jti()` prototype |
| [`diagnostics_pairing.py`](../src/jti_extract/ultra/diagnostics_pairing.py) | Method comparison: strict/nearest/greedy/folded diagnostics |

### Key design decisions

- **Fixed global frame lattice:** No per-pair origin. All candidates are binned into the same global frame.
- **`g2_all_candidates` as primary:** Strict/nearest/greedy methods are diagnostics only.
- **`--profile-only` mode:** Skips coarse JTI accumulation, SVD, and bootstrap for fast frame-length sweeps.
- **JSON-only fields:** Circular-center diagnostics, flatness metrics, per-method summaries are added to JSON without modifying the CSV schema (`SWEEP_SUMMARY_FIELDS`).
- **Separate contrast output:** Stage 20–22 CSV/JSON outputs are written to independent files (`diag_contrast_profile_*.csv`, `effective_aperture_summary.csv`), not mixed into `ultra_summary.csv`.

The toolchain is reusable but does **not** by itself certify physical apertures or Schmidt numbers.

---

## 4. Positive Results

### Transverse timing-correlation width ≈ 200 ps

Measured consistently across all frame lengths (0.819 µs to 100 µs):

```
diag_profile_mass_width_95_bins = 2
bin_width_ps = 100 ps
→ transverse width ≈ 200 ps
```

- This is the width of the JTI intensity along the **anti-diagonal** direction (`t_s - t_i`), i.e., the timing jitter / coincidence-peak width.
- It is stable and reproducible.
- It is **not** the along-diagonal duration.

### Diagnostic toolchain is functional

All 17+ tests pass. The `--profile-only` mode enables fast N=1,000,000 runs in ~4 seconds. The contrast profile pipeline runs in ~4 seconds for N=1,000,000 (124 MB RSS). The aperture selection and aperture-local JTI modules produce numerically consistent output.

---

## 5. Negative Result 1: `0.774 µs` Was a Frame-Containment Artifact

| Stage | N | frame (µs) | width95 (µs) | width/frame |
|---|---|---|---|---|
| 9 | 8192 | 0.819 | 0.774 | 0.945 |
| 10 | 12288 | 1.229 | 1.16 | 0.944 |
| 10 | 16384 | 1.638 | 1.55 | 0.946 |
| 10 | 24576 | 2.458 | 2.32 | 0.944 |
| 10 | 32768 | 3.277 | 3.09 | 0.943 |

**Conclusion**: `0.774 µs` was the width95 under the shortest frame. The ratio `width95 / frame_length ≈ 0.94–0.95` persists across all tested frames up to 100 µs. The `0.774 µs` value is a frame-containment lower bound, not a physical duration.

This result motivated the shift from "find the containment plateau" to "probe local diagonal contrast".

---

## 6. Negative Result 2: Circular Min-Arc Width Did Not Reveal a Coherence Horizon

| N | frame (µs) | min_arc_width95 (µs) | min_arc/frame |
|---|---|---|---|
| 32768 | 3.28 | 3.09 | 0.942 |
| 100000 | 10.00 | 9.40 | 0.940 |
| 300000 | 30.00 | 28.25 | 0.942 |
| 500000 | 50.00 | 47.04 | 0.941 |
| 1000000 | 100.00 | 94.04 | 0.940 |

The circular min-arc width (shortest circular arc covering 95% mass) also remains at ~94% of frame length, even at 100 µs. This is consistent with a folded center profile whose mass is approximately uniformly distributed across the frame, modulated by a weak peak. The flatness diagnostics (`peak_to_mean=575` at N=1M, not 1) confirm the profile is **not** uniform, but the fraction is dominated by the frame-phase coverage, not a coherence horizon.

**Conclusion**: The `min_arc_width95` does **not** provide a physical frame-length bound. It cannot be interpreted as pump coherence time > 100 µs.

---

## 7. Negative Result 3: Local Contrast Aperture Failed Phase-Shuffle Control

### 7.1 Contrast profile with 100k events (`bg_outer=30`)

- `max_snr = 4.47`, `snr3 = 291/512`, `snr5 = 0/512`
- `sideband_zero = 271/512 (53%)`

The high `sideband_zero` fraction made contrast and SNR unreliable for aperture selection.

### 7.2 Contrast profile with 500k events (`max_events=500k`)

- `n_candidates = 28234`
- `sideband_zero = 16/512 (3%)`
- `snr5_valid_bg = 496/512`
- `max_snr = 8.24`

Increasing statistics resolved the sideband-zero issue. The contrast profile became robust.

### 7.3 Phase-shuffle 20× distribution

| Metric | Value |
|---|---|
| true_max_snr | 8.24 |
| shuffle_max_snr (20×) | **8.24 ± 0.00** (all identical) |
| true_zscore | **0.00** |
| true_percentile | **0.0%** |

This is the **critical negative result**. Twenty independent phase-shuffle runs all produce exactly the same `max_snr = 8.24`. The true signal is indistinguishable from the phase-shuffle distribution (zscore = 0.00).

**Physical meaning of phase-shuffle**: The "phase" here is the **frame phase** (modulo position within each frame), not optical phase. Phase-shuffle preserves the marginal distribution of each channel's frame-phase while destroying the joint correspondence between specific A and B events. If the contrast were due to a local temporal correlation, phase-shuffle would reduce it. It does not.

**Conclusion**: The per-segment contrast is dominated by the **frame-phase marginal / occupancy pattern**, not by a local temporal coincidence correlation that can be certified as an effective temporal aperture.

### 7.4 Time-shift decay

| shift | max_snr | true/surr |
|---|---|---|
| 5 ns | 1.63 | 5.05× |
| 10 ns | 1.44 | 5.71× |
| 30 ns | 1.53 | 5.37× |
| 100 ns | 1.63 | 5.05× |
| 1 µs | 1.75 | 4.72× |
| 10 µs | 1.63 | 5.05× |

Time-shift reduces contrast by ≈5×, but with **no delay dependence**. All shifts from 5 ns to 10 µs produce the same max_snr ≈ 1.5. This confirms that the time-shift breaks the absolute-time coincidence between channels, but the suppression is independent of shift magnitude—consistent with a global marginal effect, not a local timing correlation.

### 7.5 Gate verdict

Per the Stage 26 gate criteria (phase-shuffle zscore ≥ 3): **BLOCKED**. Phase-shuffle zscore = 0.00.

> **The aperture/Schmidt route is permanently blocked under the current contrast metric. Phase-shuffle fully reproduces the contrast, so it cannot be interpreted as a certified local temporal aperture.**

---

## 8. Negative Result 4: Aperture-Conditioned Schmidt-like K Was Not Certified

Even if the gate had passed, the aperture-conditioned K results were not convergent:

| coarse_N | K | nonzero | n_cand |
|---|---|---|---|
| 16 | 15.19 | 16 | 283 |
| 32 | 28.72 | 32 | 283 |
| 64 | 53.07 | 64 | 283 |
| 128 | 85.84 | 108 | 283 |

K grows linearly with coarse_N. Only 283 candidates in the best aperture. Captured Frobenius energy and bootstrap stability were not measured because the aperture gate failed first.

**Conclusion**: Even if the aperture were certified, the K values would remain exploratory diagnostics, not a certified Schmidt number.

---

## 9. Physical Interpretation

The raw JTI intensity has two distinct coordinates:

- **Anti-diagonal** (`t_s - t_i`): Reflects the two-photon timing correlation. The width ≈ 200 ps is stable and trustworthy. This is the transverse timing-correlation peak.
- **Along-diagonal** (`t_s + t_i`, or center coordinate `t_+`): In a folded frame under continuous/pseudo-continuous pumping, this coordinate is dominated by:
  - The pair-generation time distribution
  - Acquisition stability
  - Frame-phase marginal occupancy (how events are distributed across the folded frame)
  - Finite sampling statistics

**Therefore, raw folded JTI along-diagonal intensity is not a standalone estimator of pump coherence time or effective Schmidt number.**

Schmidt number / high-dimensional entanglement certification requires complementary-basis measurements (MUB, Franson, dispersive frequency basis). The JTI alone, especially in a folded frame, does not provide enough information.

---

## 10. Relation to the Literature

Results from "High-dimensional quantum communication with scalable photonic entanglement in time and frequency" (or similar works) should not be misinterpreted as supporting the claim that JTI alone certifies Schmidt number. In that work:

- The JTI frame is defined by `bin_width × number_of_bins`.
- The certified dimension is constrained by **dual-basis measurements** (time and frequency), MUB witnesses, fidelity lower bounds, noise, counts, timing jitter, and dispersion.
- Raw JTI along-diagonal brightness alone does **not** determine the certified Schmidt number.

Our project's negative conclusion is consistent with this: raw folded-frame JTI intensity cannot provide a certified Schmidt number without complementary information.

---

## 11. Final Project Status

```text
Project status: closed / archived.
Final scientific level: negative result + reusable diagnostic toolchain.
Certified result: transverse timing-correlation width ≈ 200 ps.
Not certified:
  - physical along-diagonal temporal duration
  - local temporal aperture (phase-shuffle gate failed)
  - full Schmidt number (K not convergent)
  - aperture-conditioned Schmidt-like K (aperture gate failed)
```

---

## 12. Recommended Future Work

### A. Physical experiment directions

1. **JSI / pump-envelope linewidth**: Direct spectral measurement of the joint spectral intensity or pump coherence.
2. **Dispersive frequency-basis / MUB measurement**: Complementary-basis certification of effective dimension.
3. **Franson visibility vs delay**: Vary the Franson interferometer delay to measure coherence in the energy-time basis.
4. **Pump coherence decay**: Direct pump coherence measurement vs delay.
5. **Delay-line interferometry**: Resolve temporal correlations without frame folding.

### B. Computation / methodology directions

Treat "Schmidt-like approximate K under sparse/coarse/truncated regimes" as a separate methodological study. Key open questions:

- At what `n_candidates_in_aperture` does `K_coarse` plateau for a given coarse_N?
- How does captured Frobenius energy depend on truncated rank and matrix sparsity?
- Is there a correction factor for the bias introduced by coarse binning and finite counting?
- Can bootstrapped K standard deviation be used as a convergence diagnostic?
- Under what conditions does `K_coarse` approximate the physical effective mode number?

These questions should be studied with **synthetic data** (known ground-truth Schmidt rank) before being applied to experimental data.

---

## 13. Archive Checklist

- [x] `0.774 µs` is no longer used as a physical duration.
- [x] `diag_center_width95` is no longer used as a coherence time estimate.
- [x] `local contrast aperture` is no longer used for Schmidt-like analysis.
- [x] `K_coarse` is no longer reported as a certified Schmidt number.
- [x] Transverse `diag_profile_width ≈ 200 ps` is retained as a reliable diagnostic.
- [x] Future work should move to JSI/MUB/Franson-type physical certification or a separate methodological study of Schmidt-like estimator validity under sparse, coarse, and truncated regimes.

---

## Appendix: Files modified during this project

### New source modules (not modifying baseline)

- `src/jti_extract/ultra/contrast_profiles.py`
- `src/jti_extract/ultra/aperture_select.py`
- `src/jti_extract/ultra/aperture_jti.py`
- `src/jti_extract/ultra/surrogate_controls.py`

### Modified source files (minimal patch)

- `src/jti_extract/ultra/cli_ultra.py` — Added optional CLI parameters for contrast profile, aperture selection, phase-shuffle multi, profile-only mode, overwrite guard
- `src/jti_extract/ultra/accumulators.py` — Added circular-center profile, min-arc width, flatness diagnostics (peak_to_mean, CV, entropy)
- `src/jti_extract/ultra/svd_estimators.py` — Added `truncated_schmidt_summary()`, `block_bootstrap_coarse_jti()` prototype

### Test files

- `tests/test_ultra_contrast_profiles.py` (5 tests)
- `tests/test_ultra_aperture_select.py` (5 tests)
- `tests/test_ultra_aperture_jti.py` (3 tests)
- `tests/test_ultra_surrogate_controls.py` (4 tests)

### Documentation files

- `docs/ULTRA_JTI_FRAME_LENGTH_CLOSURE_REPORT.md` (this file)
- `CURRENT_TASK.md` — updated to archive status
- `AGENT_HANDOFF.md` — closure record appended
- `RUN_COMMANDS.md` — archive note added
- `docs/SCHMIDT_ANALYSIS.md` — closure note
- `docs/WORKFLOWS.md` — closure note
- `docs/TROUBLESHOOTING.md` — closure note

### Not modified

- `SWEEP_SUMMARY_FIELDS` in `io_ultra.py` (CSV schema unchanged)
- `g2_accumulate.py` (`all_candidates()` unchanged)
- `src/jti_extract/cli/` (baseline CLI unchanged)
- `src/jti_extract/core/` (baseline algorithms unchanged)
- `scripts/`, `configs/`, `pyproject.toml`
- Raw `.ttbin` data, `results/`, existing `/tmp/ultra_stage*` output directories

---

*Report generated: 2026-05-01. Project archived.*
