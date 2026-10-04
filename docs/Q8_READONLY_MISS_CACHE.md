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

The independent miss trace, component gates, paired full-model lifecycle checks,
32K repeats and native-128K pairs are complete. The sections below report each
measurement and its output/work qualifications. The small 32K MTP gain repeated;
plain decoding remained essentially tied.

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
require their own allocation and model tests; the projection alone proves no fit
or speed gain. Eight slots were tested at 32K MTP in the follow-up below;
sixteen slots remain untested in full-model inference.

Runtime source `eb22e57` built successfully. Its binary SHA-256 is
`9541ee14db3aee6f28f4427fdb43d9910f4039f780f962d1534099d3dc68144e`.
Seven fixture shape/capacity cases passed full-byte comparisons, graph replay,
eviction/bypass, source immutability, guards, and plans abandoned before or after
fill without publication. Both memcheck and initcheck reported zero errors.
The actual 5,222,400-byte expert case checked 574 accesses (107 hits, 467 fills)
and seven abandoned plans. This is component evidence, not full-model parity.

Evidence: [miss trace replay](benchmarks/q8-miss-reuse-20261004.json),
[component/build results](benchmarks/q8-readonly-components-20261004.json).

## Competing designs

The four-way cache uses the same memory as 192 additional primary expert slots.
The follow-up below measures that alternative alongside the secondary cache.
Changing primary placement can change CPU/GPU arithmetic, so its token/work
comparison is reported separately from the fixed-placement cache test.

Code inspection also found a serial section in the verifier's `post` lambda: resident
expert computation completes before missed-expert staging starts. An independent
experiment can fork after the route/plan is ready, stage misses on another stream
while resident expert kernels run, and join before consuming those misses. Both
plan readiness and completed fills require explicit dependencies. The same join
must protect later staging-buffer reuse and cancellation. The separate
`perf/q8-miss-fetch-overlap` branch implements this design and
has passed component checks. Its full-model tests are separate from this cache
report; concurrent kernels may compete for memory bandwidth and reduce the
apparent opportunity.

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
MTP showed a small initial gain. The follow-up below reports completed
reverse-order MTP/n-gram repeats, an eight-way MTP cache, an equal-VRAM
primary-cache competitor, and paired native-128K measurements.

Evidence: [complete first matrix](benchmarks/q8-readonly-first-32k-20261004.json).

## Completed repeats and native 128K

The follow-up completed 14 arms / 28 requests. Together with the first screen,
this is 44 throughput requests, plus the separate 22-request lifecycle gate.
Every throughput request reached 1,024 output tokens with no decode expert file
reads. All arms used the same component-tested `eb22e57` binary. The baseline
already includes this fork's buffer-ownership rotation and duplex copies; the
cache results measure an additional change, not a stock-upstream comparison.

Actual input was 32,768 or 131,072 tokens; allocation was input plus 8,192. KV is
FP16, RoPE is native, the automatic miss fraction is 0.55, and the CPU pool has
15 workers. A fresh engine per arm ran coding then editing, carrying adaptation
from coding into editing. These are finite paired measurements, not confidence
intervals or a task-quality evaluation.

### 32K reversed-order repeats: output tokens/s

Four-slot arms ran before their cache-off controls, reversing the first screen.

| Mode | Cache off, code / edit | Four slots/layer, code / edit | Change, code / edit |
|---|---:|---:|---:|
| MTP | 129.94 / 112.14 | 132.64 / 113.69 | +2.07% / +1.38% |
| N-gram* | 77.17 / 105.00 | 78.98 / 114.25 | +2.34% / +8.81% |

### Capacity and equal-VRAM competitor

| 32K MTP configuration | Extra VRAM | Coding tok/s | Editing tok/s |
|---|---:|---:|---:|
| Baseline | 0 | 129.94 | 112.14 |
| Four slots/layer | 0.934 GiB | 132.64 | 113.69 |
| Eight slots/layer | 1.868 GiB | 132.80 | 115.63 |
| 192 more primary slots* | 0.934 GiB | 130.19 | 115.04 |

Four and eight secondary slots per layer preserve the 15,472 primary slots and
CPU/GPU assignment. Their MTP output and recorded work matched exactly. Eight
slots were measured once; doubling cache capacity gave little additional coding
benefit. *The larger-primary arm uses 15,664 slots and changes placement: coding
diverged at token 13 and both tasks' work changed. It is a useful competing
configuration, not an exact-work control for the secondary cache.

### Native 128K: output tokens/s

The first pairs at this context ran cache off, then four slots per layer.

| Mode | Cache off, code / edit | Four slots/layer, code / edit | Change, code / edit |
|---|---:|---:|---:|
| Plain | 74.74 / 59.69 | 75.00 / 60.20 | +0.34% / +0.86% |
| MTP | 132.18 / 106.52 | 133.97 / 107.95 | +1.35% / +1.34% |
| N-gram* | 74.37 / 100.80 | 76.18 / 103.05 | +2.44% / +2.23% |
| MTP + n-gram* | 131.68 / 103.49 | 133.49 / 105.51 | +1.37% / +1.96% |

### Prefill-inclusive effective output tokens/s

Output tokens divided by complete request wall time; engine startup is excluded.

32K repeats:

| Mode | Cache off, code / edit | Four slots/layer, code / edit | Change, code / edit |
|---|---:|---:|---:|
| MTP | 64.83 / 60.59 | 65.44 / 61.06 | +0.94% / +0.76% |
| N-gram* | 48.39 / 58.62 | 49.11 / 61.33 | +1.48% / +4.62% |

128K:

| Mode | Cache off, code / edit | Four slots/layer, code / edit | Change, code / edit |
|---|---:|---:|---:|
| Plain | 22.33 / 20.81 | 22.37 / 20.87 | +0.19% / +0.25% |
| MTP | 25.66 / 24.54 | 25.71 / 24.63 | +0.21% / +0.37% |
| N-gram* | 22.29 / 24.29 | 22.48 / 24.40 | +0.83% / +0.47% |
| MTP + n-gram* | 25.62 / 24.39 | 25.71 / 24.49 | +0.35% / +0.43% |

### Token and work qualifications

| Comparison | First different token, code / edit (zero-based) | Recorded work matches, code / edit |
|---|---|---|
| 32,768 MTP | match / match | yes / yes |
| 32,768 N-gram* | 488 / match | no / no |
| 131,072 Plain | match / match | yes / yes |
| 131,072 MTP | match / match | yes / yes |
| 131,072 N-gram* | 452 / match | no / no |
| 131,072 MTP + n-gram* | match / match | yes / no |
| 32K MTP, eight slots | match / match | yes / yes |
| 32K MTP, larger primary | 13 / match | no / no |

*N-gram scheduling is timing-sensitive. Matching editing output with different
draft/work counts remains useful workload evidence, but it does not isolate a
kernel improvement on identical work. Keep those rows separate from plain/MTP
matching-work comparisons. No quality gain follows from these speed results.

### Interpretation and reproduce/disable

The small 32K MTP gain survived the reversed pair. Plain decoding changed by less
than 1% in these pairs. Logical upload savings alone overstate the end-to-end
benefit. Lower CPU-expert times suggest reduced host-memory contention as a
possible contributor; this is an inference, not measured DRAM bandwidth or a
proof of the mechanism. The separate captured-upload experiment tests actual
overlap without replacing this serial-cache configuration.

Starting from the recorded launch arguments, set `STRATA_Q8_MISS_CACHE_WAYS=4`
for the tested cache, or `0` to disable it. Eight slots were tested only in 32K
MTP here. Keep FP16 KV, native context, `--expert-cache 15472`, `--pcie-frac 0.55`,
`STRATA_EXCHANGE_ROTATE=1`, `STRATA_EXCHANGE_DUPLEX=1`,
`STRATA_ADAPT_NOWAIT=0`, `STRATA_ADAPT_WORKER=0` and
`STRATA_Q8_EXPERT_REUSE=0`. The raw evidence includes all launch commands,
source/binary hashes, prompt hashes, tokens, work, readiness memory and timings.
The switch defaults off; main, public services and model files are unchanged.

Evidence: [completed follow-up matrix](benchmarks/q8-readonly-followup-20261004.json),
[pair comparisons](benchmarks/q8-readonly-followup-summary-20261004.json).
