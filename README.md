# Experimental Q8 read-only GPU miss cache

This is an experimental fork of **[Niko1221/Strata](https://github.com/Niko1221/Strata)**.
Credit for Strata and its existing kernels belongs to upstream and its contributors.

A small secondary GPU cache keeps repeatedly uploaded Q8 experts. Its copies can
be discarded without writebacks, while primary placement and CPU/GPU assignment
stay fixed. Primary-cache evictions still use the existing ownership/duplex path.
The switch defaults off: `STRATA_Q8_MISS_CACHE_WAYS=0`.

Hardware: **RTX PRO 6000 Blackwell Workstation Edition 96GB**, Ryzen 7950X,
128GB RAM. Model: **full Unsloth Qwen3.8-Flash-Next Q8_0**, **FP16 KV**, native
RoPE. These gains are on top of this fork's ownership and duplex-copy changes.

## Measured output tokens/s

32K input + 1,024 output, reversed-order repeat:

| Mode | Cache off, code / edit | Four slots/layer, code / edit | Change, code / edit |
|---|---:|---:|---:|
| MTP | 129.94 / 112.14 | 132.64 / 113.69 | +2.07% / +1.38% |
| N-gram* | 77.17 / 105.00 | 78.98 / 114.25 | +2.34% / +8.81% |

128K input + 1,024 output, first paired measurements:

| Mode | Cache off, code / edit | Four slots/layer, code / edit | Change, code / edit |
|---|---:|---:|---:|
| Plain | 74.74 / 59.69 | 75.00 / 60.20 | +0.34% / +0.86% |
| MTP | 132.18 / 106.52 | 133.97 / 107.95 | +1.35% / +1.34% |
| N-gram* | 74.37 / 100.80 | 76.18 / 103.05 | +2.44% / +2.23% |
| MTP + n-gram* | 131.68 / 103.49 | 133.49 / 105.51 | +1.37% / +1.96% |

Four slots per layer add **0.934 GiB VRAM**. The small 32K MTP gain repeated;
plain decoding was essentially tied. Plain/MTP tokens and work matched exactly.
*N-gram rows have per-case work/output qualifications in the report. These are
paired measurements, not confidence intervals or intelligence scores.

**Checks:** 22 lifecycle requests passed, including cancellation/recovery and
MTP checkpoint restoration. GPU component checks, memcheck and initcheck passed.
All 44 throughput requests completed with zero decode expert file reads.

The **[complete report](docs/Q8_READONLY_MISS_CACHE.md)** includes the first 32K
screen, eight-slot and equal-VRAM primary-cache comparisons, effective throughput,
correctness qualifications, raw results, reproduction and the disable switch.
The measured runtime is `eb22e57`; source and binary hashes are in the evidence.

Main and defaults are unchanged. The separate upload-overlap and CPU-reuse
experiments have their own branches and are not claimed as gains here. This fork
preserves the upstream license. Use **[upstream Strata](https://github.com/Niko1221/Strata)**
for standard installation and support.
