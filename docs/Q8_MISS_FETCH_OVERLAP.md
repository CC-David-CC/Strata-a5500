# Overlap Q8 miss staging with resident experts

Experimental fork of [Niko1221/Strata](https://github.com/Niko1221/Strata).
Target: llm-60, NVIDIA RTX PRO 6000 Blackwell Workstation Edition 96GB,
Ryzen 7950X, 128GB RAM. Full Unsloth Q8_0, FP16 KV, native 32K and 128K.

## Hypothesis and intervention

The verifier currently runs resident expert kernels, then fetches GPU-assigned
misses from mapped RAM into staging, then runs the missed expert kernels. Both
groups' addresses are already known before resident expert computation starts.

`STRATA_Q8_MISS_FETCH_OVERLAP=1` moves the wait for RAM-source readiness and the
miss copy kernels onto a separate nonblocking CUDA stream. A captured event
forks after the plan is ready. Resident expert computation runs on the original
stream, which rejoins the copy branch before running the missed expert kernels.
The switch defaults off. It works independently of the secondary miss cache;
that cache remains controlled by `STRATA_Q8_MISS_CACHE_WAYS`.

Only uniform native Q8_0, whole-model CUDA verification, mapped-RAM copy mode
(`--pcie-mode auto` or `kernel`) and unsplit windows are admitted. HIP and other
model formats are not validated by this experiment. All model weights, primary
placement, expert assignment, reduction order, KV format and sampling stay fixed.

This follows CUDA's documented captured-stream
[fork and join dependencies](https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/cuda-graphs.html).
Using another stream only permits overlap; hardware scheduling and shared
bandwidth determine whether overlap occurs or helps.

## Dependency and lifetime contract

1. Route IDs and the copied CPU/device plan precede the fork.
2. The fetch branch still waits for the existing source-readiness flag. Moving
   this wait cannot authorize reading weights before they are available.
3. Fetch reads pinned RAM and writes staging, secondary-cache slots and `ptr2`.
   These regions are disjoint from resident expert weights, `ptr`, activation
   inputs, resident output rows and resident arithmetic scratch.
4. The original stream waits for complete fills and pointer/tag publication
   before consuming misses. Both expert groups keep their original arithmetic.
5. That join also orders later plan, staging and cache-plan reuse. No double
   buffering or guessed next-layer routes are introduced.
6. Every branch rejoins before capture ends. The verifier's fatal-release path
   polls the added stream too; destruction drains it before freeing the arena.
7. Cancellation, checkpoint restoration and subsequent requests require paired
   main-model state checks. A successful component test alone is insufficient.

## Evidence required

Implementation is prepared; no speed gain is claimed. The extended component
fixture uses the actual staging and cache kernels with the shared fork/join
helpers. It checks complete copied bytes, resident output integrity, zero/full
groups, changing graph inputs, repeated event use, cache eviction/bypass, guards
and immutable RAM sources. Both serial and overlapped paths are tested at the
actual 5,222,400-byte expert size. CUDA memcheck and initcheck precede the engine
build and full-model checks.

After components pass, compare plain and MTP normal requests, cancellation and
recovery; MTP additionally restores parked checkpoints. Then use fresh paired
32K runs in plain, MTP, n-gram and combined modes, with 1,024 output tokens.
Require exact plain/MTP tokens and work. Preserve n-gram work/output differences
without claiming a matching-work gain. Repeat useful gains and extend to native
128K. Compare overlap alone and overlap plus the secondary cache separately.

The hypothesis is falsified if the transfer finishes earlier without improving
request time, if concurrent kernels lose more throughput to resource contention
than they hide, or if any unexplained token/state discrepancy appears. Retain
the serial path and CPU-only miss configuration as independent alternatives.
