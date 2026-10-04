# Experimental Q8 read-only GPU miss cache

This is an experimental fork of **[Niko1221/Strata](https://github.com/Niko1221/Strata)**.
Credit for Strata and its existing kernels belongs to upstream and its contributors.

This branch adds a small secondary GPU cache for repeatedly uploaded Q8 experts.
It preserves primary expert placement and the CPU/GPU split. Its immutable copies
can be discarded without writebacks; primary-cache evictions still use the existing
ownership/duplex path. The switch defaults off: `STRATA_Q8_MISS_CACHE_WAYS=0`.

Target: **RTX PRO 6000 Blackwell Workstation Edition 96GB**, Ryzen 7950X, 128GB RAM;
full Unsloth Q8_0, FP16 KV, native 32K and 128K.

## What is verified so far

- A matched-output/work 32K MTP trace projected **8.04% fewer miss-upload bytes**
  with four slots per layer (0.934 GiB), or **14.15%** with eight (1.868 GiB).
- GPU component checks passed complete byte comparisons, changing graph inputs,
  eviction/bypass, abandoned fills, source immutability and allocation guards.
- CUDA memcheck and initcheck each reported **zero errors**. The engine built.

**Paired plain/MTP lifecycle checks passed all 22 requests:** normal generation,
MTP checkpoint restoration, cancellation and recovery matched output tokens,
recorded work and main-model state fingerprints with the cache off/on.

## First paired 32K measurements

32K input + 1,024 output, same binary, 0.934 GiB extra cache. Output tokens/s:

| Mode | Cache off, code / edit | Cache on, code / edit | Change, code / edit |
|---|---:|---:|---:|
| Plain | 73.70 / 61.87 | 73.53 / 62.32 | -0.24% / +0.74% |
| MTP | 130.01 / 111.92 | 132.69 / 113.79 | +2.06% / +1.67% |
| N-gram* | 74.96 / 100.18 | 74.53 / 106.31 | -0.57% / +6.12% |
| MTP + n-gram* | 129.78 / 108.84 | 131.18 / 112.49 | +1.08% / +3.36% |

Plain/MTP tokens and work matched. *N-gram and combined comparisons have the
per-case qualifications in the report. This is one pair per mode; reverse-order
repeats, capacity/equal-VRAM comparisons and native-128K tests are queued. The
initial MTP gain is small and has not yet been established by repeated runs.

See **[implementation, conditions, evidence and remaining gates](docs/Q8_READONLY_MISS_CACHE.md)**.
This branch retains the upstream license. For standard installation and support,
use **[upstream Strata](https://github.com/Niko1221/Strata)**.
