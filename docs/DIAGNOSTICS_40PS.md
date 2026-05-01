# 40ps Diagnostics

## Singles Timestamp Mod 40ps

Single-channel timestamp residues show whether one hardware channel has a fixed fine-time grid structure independent of pairing.

## Pair dt Mod 40ps

Nearest-pair `dt = t_b - t_a` residues show whether pair selection amplifies or creates a visible 40ps structure.

## Surrogate Shift

Shift surrogate offsets one channel by random large shifts and recomputes pairing statistics. If A40 remains high, the structure likely survives coincidence destruction and may be electronic/TDC related.

## Block Shuffle

Block shuffle preserves local timing blocks but destroys long-range coincidence alignment. A persistent A40 after block shuffle also suggests non-physical pairing-independent residue.

## Time Split

Time split measures A40 amplitude and phase across acquisition segments. Stable phase supports a fixed timing grid; unstable phase weakens that interpretation.

## Folding/JTI Diagonal Metrics

Folding maps paired timestamps into discrete JTI bins with and without strict single-hit filtering. Metrics include main diagonal fraction, diagonal uniformity CV, and FFT components along the diagonal.

## Interpretation

Real coincidence-layer structure should weaken under coincidence-destroying surrogates and may show physical dependence on source/control conditions. TDC/electronics residue often appears in singles or survives surrogate tests with stable phase.
