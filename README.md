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

**These are byte savings and component checks, not a model speedup.** Full-model
normal-request, checkpoint and cancellation gates are running before throughput
comparisons. The initial harness attempt requested unsupported conversation caching
with MTP off; its replacement respects the engine's existing restriction.

See **[implementation, conditions, evidence and remaining gates](docs/Q8_READONLY_MISS_CACHE.md)**.
This branch retains the upstream license. For standard installation and support,
use **[upstream Strata](https://github.com/Niko1221/Strata)**.
