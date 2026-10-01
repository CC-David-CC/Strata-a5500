# Strata-a5500: RX 5500 XT 8 GB support

A minor, experimental fork of **[Strata by Niko1221 and the Strata contributors](https://github.com/Niko1221/Strata)**, focused on the **consumer AMD Radeon RX 5500 XT 8 GB (RDNA1 / gfx1012)**. `a5500` is the test machine's nickname.

The inference engine, expert caching, model-loading tools, and MTP (multi-token prediction) come from upstream Strata. This fork adds RDNA1/HIP compatibility, fixes needed for serving without MTP, and tests for the configuration below. Credit for Strata belongs to its original authors and contributors; the [MIT license and attribution](LICENSE) are retained.

## Tested configuration

- **GPU:** AMD Radeon RX 5500 XT, 8 GB VRAM; one GPU, text only.
- **Host:** Ryzen 5 3600, 56 GB installed DDR4 at 1866 MT/s (about 54.8 GiB usable), NVMe SSD, Ubuntu 24.04.
- **Model:** Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S with Q8 KV cache. Adaptive GPU expert cache, mmap-backed CPU experts, and the n-gram/PLE table on SSD.
- **Request:** 8,192 input tokens, up to 512 output tokens; 9,216-token allocated context, one request at a time.
- **Build:** Strata HIP, based on upstream 0.1.30; HIP 5.7.1 and clang 17. The pinned llama.cpp / ggml dependency is unchanged.

This is the configuration validated by this fork. RX 5500 XT setup currently requires a manual Linux source build.

## Measured request performance

Measured September 30, 2026 on the hardware above. Each result is one observation; coding and writing ended before the 512-token cap.

| Task | MTP | Output tokens | Prefill tok/s | Prefill seconds | Generation tok/s | Total seconds | Effective tok/s |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Counting | Off | 512 | 97.71 | 83.84 | 11.35 | 128.96 | 3.97 |
| Counting | On | 512 | 80.25 | 102.09 | 16.81 | 132.55 | 3.86 |
| Coding | Off | 125 | 100.22 | 81.74 | 10.45 | 93.71 | 1.33 |
| Coding | On | 125 | 82.89 | 98.83 | 15.30 | 107.01 | 1.17 |
| Writing | Off | 232 | 100.10 | 81.84 | 10.17 | 104.64 | 2.22 |
| Writing | On | 232 | 82.47 | 99.33 | 10.91 | 120.60 | 1.92 |

Total seconds includes prefill and generation, excluding model startup. Effective tok/s = output tokens / total seconds. MTP improved generation speed, but the additional prefill time made each of these fresh 8K requests take longer overall.

**Checks:** 16 focused GPU tests and five real-expert parity checks passed; all six requests completed without runtime errors. The writing sample exceeded its requested word limit.

## Build and evidence

- [RX 5500 XT build instructions and what this fork changes](docs/AMD_HIP.md#rdna1-rx-5500-xt-8-gb-gfx1012)
- [RX 5500 XT benchmark report](docs/AMD_HIP_PERFORMANCE.md#rx-5500-xt-8-gb-rdna1) and [raw results](docs/benchmarks/2026-09-30-gfx1012.json)
- [Original Strata project and documentation](https://github.com/Niko1221/Strata)
