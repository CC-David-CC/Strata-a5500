# Read-only Q8 miss cache experiment

Target: llm-60, RTX PRO 6000 Blackwell Workstation Edition 96GB, Ryzen 7950X,
128GB RAM. Full Unsloth Q8_0, FP16 KV, native 32K and 128K. Main is unchanged.

This branch adds an opt-in secondary GPU cache for the missed experts that the
existing CPU/GPU split already sends to the GPU. It preserves the primary
adaptive cache and the grouped expert arithmetic. A hit avoids another upload;
discarding a copy performs no writeback. The authoritative expert remains in
the primary GPU/RAM/file hierarchy. This differs from retaining promoted
experts in RAM, whose tested unseeded FIFO policy saved too few writebacks.

`STRATA_Q8_MISS_CACHE_WAYS=0` is the default. Values 1 through 16 allocate that
many slots per layer. Four ways across 48 layers cost 1,002,700,800 bytes
(0.934 GiB), plus small metadata and the original staging area. The experiment
requires uniform Q8_0, whole-model CUDA verification, `--pcie-mode auto` or
`kernel`, and no `--spec-split`. It has not been validated on HIP or other GPUs.

## Copy and lifetime contract

1. The GPU reserves every existing hit before selecting victims. A miss cannot
   overwrite a later member of the same group. Excess misses use staging.
2. A replacement slot becomes invalid before its bytes are overwritten.
3. A parallel copy kernel fills missing weights. A separate publication kernel
   runs after the entire copy kernel; only then does the new expert tag become
   valid. The host never treats an enqueued copy as a completed cache fill.
4. Copies, publication, expert consumers and later eviction use the same stream.
   This initial implementation adds no cross-stream lifetime dependency.
5. Cache tags describe immutable weights, not KV or recurrent state. Accepted
   or rejected drafts may warm the cache, but cannot publish a partial fill.
   The existing fatal verifier-release path continues refusing later windows.
6. No CPU/GPU assignment, expert ordering, grouped launch geometry, model bytes,
   sampling policy or primary expert residency changes.

The component fixture exercises complete byte comparisons at the actual
5,222,400-byte expert size, small boundary sizes, changing groups through captured
graphs, hits with null RAM pointers, eviction, bypass, per-slot guards, immutable
RAM sources, and plans abandoned before fill/publication. It does not by itself
prove full-model cancellation or speculative-state correctness.

## Evidence gates

The independent miss trace, component gates and paired full-model lifecycle
checks are complete. The first 32K performance screen is complete below; repeated gains are not yet established.
It compares default-off and four slots per layer using the same binary, with exact
token/work checks for plain and MTP and first-divergence/work reporting for n-gram
and combined. Repeat gains and test both native contexts before publishing a
speed claim.

Per-request logs report cumulative completed groups, hits, uploads, bypasses
and logical bytes saved/uploaded. Difference adjacent reports for a request.
These are payload counts, not PCIe hardware counters. Cache hit rate alone does
not prove a throughput gain; extra launches and memory traffic can outweigh it.

`test_q8_readonly_lifecycle.py` prepares paired plain/MTP gates against the
component-tested binary: a normal 32K request, STOP after 16 delivered tokens,
then another request. MTP additionally tests A/B/A conversation and checkpoint
restoration; this engine rejects conversation caching with MTP off. It requires
matching main-model state fingerprints and tokens on the normal/checkpoint
requests. If asynchronous STOP performs different work between arms, the
post-cancel state comparison is reported as unequal-work, not claimed exact.
The revised harness passed all four arms (22 requests total). Cache on/off had
identical output tokens, recorded work and all recorded main-model state
fingerprints, including both cancellation and recovery comparisons. MTP also
passed the checkpoint restores. This validates the recorded cases, not every
possible interleaving. The first 32K throughput screen is complete below. The serving
path remains private.

Evidence: [full lifecycle results](benchmarks/q8-readonly-lifecycle-20261004.json).

The first lifecycle attempt stopped before readiness because its plain-mode
control requested a nonzero conversation-cache budget, an unsupported engine
configuration. The revised harness uses zero for plain mode. Its logs are kept;
this was a harness configuration failure before any candidate inference.

## Completed trace and component evidence

The diagnostic MTP trace used 32,768 input tokens and 1,024 output tokens each
for coding then editing. All output tokens and recorded work matched the frozen
control. Its 13,727 nonempty groups accounted for exactly the engine's logical
miss-upload payload. The following are trace replay projections, not TPS:

| Policy | Extra VRAM | Avoided miss-upload bytes |
|---|---:|---:|
| Global LRU, 192 slots | 0.934 GiB | 7.77% |
| Per-layer LRU, 4 slots/layer | 0.934 GiB | 8.04% |
| Per-layer LRU, 8 slots/layer | 1.868 GiB | 14.15% |
| Per-layer LRU, 16 slots/layer | 3.735 GiB | 25.74% |

The native-128K MTP control had 5,128 MiB free at readiness. Four slots per layer
leave useful headroom without changing the 15,472 primary slots. Larger caches
still need actual allocation and model tests; the projection alone proves no fit
or speed gain.

Runtime source `eb22e57` built successfully. Its binary SHA-256 is
`9541ee14db3aee6f28f4427fdb43d9910f4039f780f962d1534099d3dc68144e`.
Seven fixture shape/capacity cases passed full-byte comparisons, graph replay,
eviction/bypass, source immutability, guards, and plans abandoned before or after
fill without publication. Both memcheck and initcheck reported zero errors.
The actual 5,222,400-byte expert case checked 574 accesses (107 hits, 467 fills)
and seven abandoned plans. This is component evidence, not full-model parity.

Evidence: [miss trace replay](benchmarks/q8-miss-reuse-20261004.json),
[component/build results](benchmarks/q8-readonly-components-20261004.json).

## Next comparisons

The four-way cache uses the same memory as 192 additional primary expert slots.
Compare that alternative before attributing a win to the secondary organization.
Changing primary placement can change CPU/GPU arithmetic, so its token/work
comparison is reported separately from the fixed-placement cache test.

Code inspection also found a serial section in the verifier's `post` lambda: resident
expert computation completes before missed-expert staging starts. An independent
experiment can fork after the route/plan is ready, stage misses on another stream
while resident expert kernels run, and join before consuming those misses. Both
plan readiness and completed fills require explicit dependencies. The same join
must protect later staging-buffer reuse and cancellation. This overlap has not
yet been implemented or measured; concurrent kernels may compete for memory
bandwidth and reduce the apparent opportunity.

## First completed 32K performance screen

All eight arms / 16 requests completed. Full Unsloth Q8_0, FP16 KV, native
32,768 input tokens, 40,960 allocation, 1,024 output tokens, 15,472 primary expert
slots, automatic miss fraction 0.55. A fresh engine per arm ran coding then
editing. Within each mode the cache-off arm ran first, then four ways per layer
(0.934 GiB extra VRAM). Both used component-tested runtime `eb22e57` and the same
binary. These are first paired measurements, not confidence intervals.

### Output tokens/s

| Mode | Cache off, code / edit | Cache on, code / edit | Change, code / edit |
|---|---:|---:|---:|
| Plain | 73.70 / 61.87 | 73.53 / 62.32 | -0.24% / +0.74% |
| MTP | 130.01 / 111.92 | 132.69 / 113.79 | +2.06% / +1.67% |
| N-gram* | 74.96 / 100.18 | 74.53 / 106.31 | -0.57% / +6.12% |
| MTP + n-gram* | 129.78 / 108.84 | 131.18 / 112.49 | +1.08% / +3.36% |

### Prefill-inclusive effective output tokens/s

Output count divided by complete request wall time, excluding model startup.

| Mode | Cache off, code / edit | Cache on, code / edit | Change, code / edit |
|---|---:|---:|---:|
| Plain | 47.04 / 42.19 | 46.95 / 42.39 | -0.20% / +0.49% |
| MTP | 64.87 / 60.55 | 65.08 / 61.09 | +0.33% / +0.89% |
| N-gram* | 47.43 / 57.00 | 47.35 / 59.05 | -0.18% / +3.60% |
| MTP + n-gram* | 64.74 / 59.65 | 65.10 / 60.75 | +0.55% / +1.85% |

### Output/work and upload accounting

| Mode | First different token, code / edit (zero-based) | Work matches, code / edit | Avoided upload payload |
|---|---|---|---:|
| Plain | match / match | yes / yes | 8.49% |
| MTP | match / match | yes / yes | 8.04% |
| N-gram* | 173 / match | no / no | 8.31% |
| MTP + n-gram* | match / match | yes / no | 7.81% |

Plain and MTP matched every output token and all recorded work. MTP + n-gram
coding also matched. *N-gram coding diverged at token 173, while editing matched
tokens but had different draft/work counts. Combined editing matched tokens
with different work. These timing-sensitive rows do not isolate a kernel gain
on identical work. No quality improvement is inferred from speed.

The MTP run consumed 1,945 secondary-cache hits out of 24,188 miss groups,
avoiding exactly 10,157,568,000 upload bytes. Those counts match the independent
trace prediction. Upload savings are logical expert payload, not hardware PCIe
counters, and do not include primary-cache eviction traffic. The inherited
`logical_pcie_weight_bytes` diagnostic describes demand before secondary-cache
savings; use the new cache counters to account for uploaded payload.

No decode expert file reads or OOMs occurred. Plain speed is essentially tied;
MTP has a small initial gain that needs repetition. Reverse-order MTP/n-gram
repeats, an eight-way MTP cache, an equal-VRAM primary-cache competitor, and
paired native-128K measurements are queued before a broader performance claim.

Evidence: [complete first matrix](benchmarks/q8-readonly-first-32k-20261004.json).
