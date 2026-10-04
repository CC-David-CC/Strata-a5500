# Q8 miss-copy concurrency experiment

Experimental fork of [Niko1221/Strata](https://github.com/Niko1221/Strata).
Target: llm-60, RTX PRO 6000 Blackwell Workstation Edition 96GB, Ryzen 7950X,
128GB RAM; full Unsloth Q8_0, FP16 KV, native 32K and 128K.

## Observation motivating the change

The first 32K MTP pair with four secondary-cache slots per layer used runtime
`bcacb884`. Upload overlap changed editing from 113.67 to 115.29 output tokens/s,
with identical output and recorded work. Mean host wait for GPU progress fell
14.59 to 12.85 ms/window, while CPU expert time rose 13.45 to 14.46 ms/window.
Full-window time fell 34.38 to 33.90 ms. Coding was essentially tied.

Evidence: [parent MTP request records and paired analysis](benchmarks/q8-miss-fetch-geometry-parent-20261004.json).

These are first paired observations from the parent overlap branch. The host
wait interval is not GPU idle time. Memory contention is a hypothesis; these
logs do not measure host DRAM traffic or prove the mechanism. Stage profiling
and a hardware-counter capability probe are separate jobs.

## Intervention and invariants

Both the ordinary miss copy and the secondary-cache fill launch 384 blocks of
256 threads. `STRATA_MISS_FETCH_BLOCKS` sets the block count from 1 through 4096
at graph capture; absence preserves 384. The same setting controls both copies.

Only launch concurrency changes. The grid-stride loops retain the full copy
extent, 16-byte accesses, source/destination addresses and complete-fill/tag
publication dependencies. Primary placement, CPU/GPU assignment, expert math,
token policy and FP16 KV remain fixed. Captured overlap and the secondary cache
keep independent switches. No DMA or driver-callback path is added.

Lower concurrency could reduce contention with CPU expert reads or resident
GPU kernels. It could also lengthen uploads enough to lose overall. Copy time
alone cannot choose the winner; measure matching-work request time and the CPU,
resident-kernel and exposed fetch/join intervals together.

## Validation and selection

Implementation prepared; no build, parity or speed result yet. Component gates
run the original 384-block default and explicit 1/32/96/384 configurations with
the actual 5,222,400-byte expert, small/tail shapes, captured serial/overlap paths,
cache eviction/bypass, complete-byte output, source immutability and guards.
Memcheck/initcheck run at 32/96/384, and invalid values must be rejected.

After these gates and the parent stage profile, select a small full-model
comparison. Keep serial and overlap, cache off/on and all decoding modes as
separate paths. Require exact plain/MTP tokens and recorded work; qualify n-gram
work changes. Repeat useful gains, then extend them to native 128K. No result
from the parent branch establishes a gain for this block-count change.
