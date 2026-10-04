# Experimental Q8 CPU / PCIe miss balance

This is an experimental fork of **[Niko1221/Strata](https://github.com/Niko1221/Strata)**.
Credit for the engine and its existing kernels belongs to upstream and its
contributors. This branch measures an existing placement setting on top of
the fork's buffer-ownership and duplex-copy optimizations; it is not an upstream release.

Hardware: **NVIDIA RTX PRO 6000 Blackwell Workstation Edition 96GB**, Ryzen 7950X,
128GB RAM. Model: **full Unsloth Qwen3.8-Flash-Next Q8_0**, **FP16 KV**, native
RoPE. All rows generated 1,024 output tokens. The 75.25 GiB primary GPU expert
cache stays active; "CPU-only" applies only to misses (`--pcie-frac 0`).

## Fresh paired measurements

32K input, output tokens/s:

| Mode | Automatic split, code / edit | CPU-only misses, code / edit | Change, code / edit |
|---|---:|---:|---:|
| MTP | 130.29 / 111.98 | 135.64 / 114.50 | +4.11% / +2.25% |
| N-gram | 74.50 / 100.67 | 75.98 / 110.51 | +1.98% / +9.77% |

128K input, output tokens/s:

| Mode | Automatic split, code / edit | CPU-only misses, code / edit | Change, code / edit |
|---|---:|---:|---:|
| Plain | 74.83 / 59.85 | 74.94 / 60.38 | +0.14% / +0.88% |
| MTP | 131.82 / 106.25 | 137.16 / 110.44 | +4.05% / +3.95% |
| N-gram | 74.41 / 102.50 | 74.75 / 104.34 | +0.47% / +1.80% |
| MTP + n-gram | 131.76 / 102.86 | 134.82 / 110.13 | +2.32% / +7.07% |

**Qualification:** changing placement changes numerical execution. Coding token
streams and work counts differed; see the per-case comparison. N-gram work also
varied with timing. These are configuration measurements, not exact-output
kernel gains or intelligence scores. Prefill-inclusive gains are smaller.

The initial four-mode 32K screen, all-GPU miss regressions, effective throughput,
correctness details and reproduction settings are in the
**[complete report](docs/Q8_PCIE_MISS_BALANCE.md)**. All requests completed with
zero decode expert file reads. Defaults and `main` are unchanged.

The measured engine is `b926ad75744f20652e940db9141900bc91f1b48f`; documentation
and the corrected head-format log label were added afterwards. A new read-only
GPU miss-cache experiment is separate and has no validated performance result yet.

This branch preserves the upstream license. For normal installation and supported
configurations, use **[upstream Strata](https://github.com/Niko1221/Strata)**.
