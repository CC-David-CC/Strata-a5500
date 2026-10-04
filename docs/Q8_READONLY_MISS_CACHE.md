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
checks are complete. The 32K performance screen is running; no speedup claim yet.
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
possible interleaving. The 32K throughput runs have now started. The serving
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
