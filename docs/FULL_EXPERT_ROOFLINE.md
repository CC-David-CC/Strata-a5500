# Full-expert Q4/Q8 investigation

This is experimental work in David's Strata fork, branch `perf/full-expert-q4-q8`.
It builds on [Niko1221/Strata](https://github.com/Niko1221/Strata), release v0.1.34
(`1678de3`), and the fork's `contrib/non-mtp-serving` branch (`12fa219`). Commit
`2be5cf1` adds an experimental mapped Q8_0 PLE reader. Q8 now completes the first
8K tests with MTP on and off. This does not establish a kernel speedup or robust
long-context Q8 support. The shared serving dependency is intentional: it lets
the same client test MTP on and off.

Start in Strata because it already runs the full Unsloth Q4 model, provides MTP,
and has expert placement and timing machinery. Keep llama.cpp as the independent
same-GGUF reference and the working Q8 baseline. A separate engine, vLLM port, or
SGLang port is not needed to test the first hypotheses. Reconsider only if measured
architectural constraints prevent a required optimization.

## Evidence already collected

Unmodified v0.1.34 on llm-60, RTX PRO 6000 Blackwell Workstation Edition 96 GB,
64 GB system RAM; UD-Q4_K_XL; int8 KV; 16,384 allocated context; fresh 8,192-token
prompts; MTP window 4, threshold 0.5; prompt reuse disabled:

| Task | Output tokens | Output tok/s | Prefill seconds | Request seconds | Effective output tok/s |
| --- | ---: | ---: | ---: | ---: | ---: |
| Counting | 2,048 | 249.65 | 2.095 | 10.307 | 198.70 |
| Coding | 2,048 | 212.14 | 1.826 | 11.484 | 178.33 |
| Prose | 1,504 | 157.98 | 1.809 | 11.332 | 132.72 |

One run per task. Counting and coding hit the limit; the coding module is
incomplete. Prose stopped naturally. These are speed and smoke tests, not quality
scores. Effective rate counts output tokens over prefill plus generation and
request overhead; startup is excluded. OS page cache was not flushed.

All four Q4 shard hashes passed. All 24,576 routed experts fit on the GPU;
generation had 100% expert-cache hits, zero CPU expert computations, and no expert
reads from RAM/disk. Prefill temporarily borrowed 1,298 cache slots and refilled
them from the files, so the no-disk statement applies only to generation.
Peak sampled GPU use was 81,013 MiB, with about 16 GiB spare. The temporary engine
stopped after testing. Local full evidence is in
`.fleet_work/strata/q4-strata-0134-llm60/` in the enclosing fleet workspace.

Previous llama.cpp evidence, different workloads and builds:

- Q4, F16 KV, 16K input + 4K output: 96.82 output tok/s, 67.14 effective, 61.010 s.
- Q8, F16 KV, 8K + 2K: 38.95 output tok/s, 25.53 effective, 80.233 s. Thirty-two
  layers' experts were resident on GPU; sixteen used RAM backing plus a GPU cache
  of 64 experts per offloaded weight tensor. Cache misses were copied to the GPU.
- Those are historical comparisons, not a controlled measurement of MTP speedup.

### Matched 8K measurements on the experimental branch

Fresh 8,192-token prompts, 16,384 allocated context, int8 KV, up to 2,048 output
tokens, prefill chunk fixed at 8,192. Both modes use the same prompt hashes;
MTP uses window 4, minimum draft probability 0.5. Each arm ran once in off/on
order. Long prompts contain repetitive synthetic filler; these prefill rates
are not representative of an arbitrary 8K document. Full results and hashes are
summarized in [the evidence JSON](benchmarks/full-expert-q4-q8-initial.json).

| Quant / task | MTP off output tok/s | MTP on output tok/s | Off effective tok/s | On effective tok/s |
| --- | ---: | ---: | ---: | ---: |
| Q4 / counting | 104.69 | 259.67 | 94.31 | 203.64 |
| Q4 / coding | 104.66 | 220.33 | 95.73 | 183.43 |
| Q4 / prose | 104.35 | 163.81 | 92.80 | 136.66 |
| Q8 / counting | 66.18 | 121.83 | 55.27 | 80.85 |
| Q8 / coding | 61.97 | 87.53 | 50.70 | 63.33 |
| Q8 / prose | 52.25 | 51.87 | 42.34 | 42.85 |

Counting and coding reached 2,048 tokens. Q4 prose produced 1,504 in either mode;
Q8 prose stopped naturally at 1,542 off / 1,498 on. The prose rates therefore do
not establish a matched-output MTP improvement. All temporary engines exited.

The Q4 buffer intervention kept the prefill chunk at 8,192 and used
`--no-prefill-borrow`. Across the six off/on cases, output token IDs were unchanged,
prefill time fell 28-32%, and decode rates barely changed. MTP coding effective
throughput improved from 183.43 to 192.32 tok/s (4.8%). This is a configuration
result from one fixed-order pair, requiring repeated A/B/B/A trials before a
robust speed claim. No new GPU kernel optimization has been measured yet.

Q8 validation: 1,029 synthetic row probes and 1,059 real-model row probes decoded
bit-for-bit identically to ggml; malformed-file checks and the existing direct
reader self-test passed. Full-model IQ4/Q5/FP8 regression on the changed engine
remains outstanding. Q8 direct PLE I/O is deliberately rejected pending tests.

Q8 fit: the GPU held 18,144 experts without MTP / 17,958 with it. The remaining
31.28 / 32.19 GiB fitted in pinned system RAM. Decode expert-file counters were
zero; borrowed prefill slots still required file refills. Only 256 / 240 MiB VRAM
remained after load, so the next context test must reserve more headroom first.
The n-gram table is mapped separately and can still fault from storage.

## What the roofline means

Use bytes per **emitted** token, not file size, active parameter count alone, or
tokens examined by the verifier. For each step record time as well as bytes.

NVIDIA specifies [1,792 GB/s VRAM bandwidth](https://www.nvidia.com/en-us/products/workstations/professional-desktop-gpus/rtx-pro-6000/).
The observed host-to-device probe on llm-60 was 28.9 GB/s. Neither number promises
application throughput. GB below is decimal; GiB is binary.

### No MTP: ideal weight reads

`weight bytes/token = dense weights + expert weights * 10/512 + one embedding row`

| Model representation | Dense/read-every-step GB | Selected experts GB | Total GB/token | Weight-only reference tok/s |
| --- | ---: | ---: | ---: | ---: |
| Original Q4 GGUF | 4.8302 | 1.5043 | 6.3344 | 282.9 |
| Strata Q4 compatibility pack | 5.2806 | 1.5043 | 6.7848 | 264.1 |
| Original Q8 GGUF | 4.7926 | 2.5068 | 7.2994 | 245.5 |
| Strata Q8 compatibility pack | 5.2806 | 2.5068 | 7.7873 | 230.1 |

The input embedding is one row, not a full vocabulary scan. The output head is a
full scan. PLE reads selected rows, not the whole n-gram table. Strata's existing
small-projection BF16 conversions add a net 450,396,160 bytes to Q4's estimate
and 487,936,000 bytes to Q8's estimate.
Conversion error is already part of this compatibility baseline and must stay
documented. Routed expert bytes are unchanged.

These references omit KV/recurrent-state traffic, activations, dequantization,
imperfect coalescing, synchronization, and host/disk latency. They are not a full
hardware roofline. Q8's all-GPU number is hypothetical: its non-PLE payload is
124.6 GiB, too large for this card.

### MTP: change the traffic denominator

Let `T` be verified candidate positions, `A` emitted tokens per window, `U_l` the
number of distinct experts used in layer `l`, and `e_l` bytes per expert there.

`bytes/window = dense bytes + sum(U_l * e_l) + KV/state/activation traffic`

`time/window >= max(GPU time, PCIe time, NVMe time, dependency latency) + serial draft time`

`output tok/s = A / time/window`

The max expression assumes ideal overlap; a fully serialized schedule adds the
times. Dependencies can put the real schedule between those cases. MTP can exceed
the *single-token* reference by reusing weights. It cannot exceed a correct
roofline recalculated for its actual traffic and computation.

For illustration, dense weights read once/window, no reuse between routed experts
of successive candidates, peak bandwidth, and observed MTP window statistics give:

| Task | Verified/window | Emitted/window | Ideal weight reference | With observed draft time added | Measured |
| --- | ---: | ---: | ---: | ---: | ---: |
| Counting | 3.99 | 3.98 | 632 tok/s | 523 tok/s | 250 tok/s |
| Coding | 3.63 | 3.16 | 527 tok/s | 437 tok/s | 212 tok/s |
| Prose | 3.01 | 2.20 | 402 tok/s | 334 tok/s | 158 tok/s |

These are models, not promised speeds or measured GPU utilization. Actual DRAM
transactions and expert unions have not yet been profiled. Reuse can reduce
traffic further; KV, extra reads, quantization instructions and synchronization
increase time. This model suggests headroom but does not establish a 2x speedup.

The observed verifier took 12.79–14.60 ms/window; drafting took 1.11–1.31 ms.
Investigate verifier memory traffic, quantized matrix kernels, and launch/wait
structure before changing Q4's expert cache: that cache already hits 100%.

### Context sensitivity and current estimates

These are **partial bandwidth references**, not measured performance, a forecast,
or a complete hardware roofline. Use one request on llm-60, int8 KV, peak 1,792
GB/s VRAM bandwidth, measured 28.9 GB/s PCIe, and RAM for all expert misses.
The context columns mean populated history, not unused allocated capacity.

The source's sparse attention selects at most 2,051 cells. Across its 12 QSA
layers, ideal int8 KV reads cost 12,672 bytes per selected cell, and pooled FP32
indexer keys add 1,536 bytes per history token. The calculator includes these
reads per verified position. Recurrent-state traffic, extra activation reads,
dequantization, random PLE faults and synchronization are still omitted.

| Model and execution assumption | 8K history tok/s | 16K history tok/s | 64K history tok/s |
| --- | ---: | ---: | ---: |
| Q4, no MTP, all experts GPU | 263 | 262 | 259 |
| Q4, code-like MTP, no expert reuse between candidates | 432 | 431 | 422 |
| Q8, no MTP, 96.5% GPU expert-byte hit rate | 134-226 | 134-226 | 133-224 |
| Q8, code-like MTP, same hit rate, no expert reuse | 155-256 | 155-256 | 154-256 |
| Q8, code-like MTP, same hit rate, 25 unique experts/layer/window | 210-362 | 210-362 | 208-362 |

Q4 MTP assumes the observed release coding window: 3.63 verified, 3.16 emitted,
1.24 ms serial drafting. Q8 uses its observed coding window: 3.75 verified, 3.34
emitted, 1.65 ms drafting. Q8 ranges span serialized versus perfectly overlapped
GPU and PCIe work; real performance can be below both references. The last row
assumes routing reuse, which has not yet been measured. Dense weights are read
once per window in this idealized model. Cold experts are transferred to GPU;
the current engine also computes some on CPU, which needs a separate CPU term.

The 96.5% Q8 byte hit rate is a sensitivity assumption near the measured off-mode
expert counts, not a measured transfer-byte hit rate. In particular, the log's
97-99% cache statistic excludes PCIe experts from its denominator and cannot be
substituted directly. At only 90% byte hits, the 8K no-MTP reference drops to
76-115 tok/s. Cache identity and transfer bytes matter much more here than the
small ideal attention-read increase from 8K to 64K.

Keep acceptance and cache hit rate fixed when interpreting these context columns.
Real longer requests may change both; their larger allocation can displace hot
experts. These Q4/Q8 branch runs have only tested 8K input so far. The older
llama.cpp long-context results are not validation of this branch.

## Q8: separate the two disk paths

### Expert cache misses

For `B` GB of experts missing from VRAM per output token:

- If RAM holds them: host-to-GPU floor is `B / 28.9` seconds.
- If they must come from an NVMe: add `B / S_nvme` without overlap, or use the
  larger of the two times with ideal pipelining. Include read amplification.
- This is transfer-only. GPU verification, dequantization, and latency still cost time.

Assume **5 GB/s effective NVMe reads**, an illustrative input, not a measurement:

| Miss bytes/output token | RAM-to-GPU only | NVMe + PCIe, serialized | NVMe + PCIe, perfect overlap |
| --- | ---: | ---: | ---: |
| 0.10 GB | 289 tok/s | 42.6 tok/s | 50 tok/s |
| 0.25 GB | 115.6 tok/s | 17.1 tok/s | 20 tok/s |
| 0.50 GB | 57.8 tok/s | 8.5 tok/s | 10 tok/s |
| 1.00 GB | 28.9 tok/s | 4.3 tok/s | 5 tok/s |

With MTP replace `B` by unique miss bytes/window divided by emitted tokens/window.
For example, 0.5 GB fetched once for three emitted tokens gives transfer-only
ceilings of 173.4 tok/s from RAM, or 25.6–30 tok/s from this assumed NVMe.
Fetching 0.5 GB separately for each candidate removes that benefit.

The preferred llm-60 layout is GPU hot/resident experts, the remaining experts in
RAM, and PLE mapped from NVMe. Q8 need not read expert weights from disk each
token if the GPU cache complement fits RAM. The measured 8K configuration used
31.28 GiB without MTP / 32.19 GiB with MTP for the complement; larger reserves,
buffers and context allocations can increase that requirement.

### The PLE/n-gram table

Q8's PLE table is 54,400,261,120 bytes = 50.664 GiB. A token selects 16 rows of
160 values; Q8_0 uses five 34-byte blocks per row. That is **2,720 logical bytes**
per token. Sixteen unrelated cold 4 KiB page reads cost about 64–68 KiB including
occasional row crossings. This is an IOPS/latency and cache-locality problem, not
a 50.7 GiB transfer per token. CPU-dequantized F32 rows are only 10,240 bytes/token
for the GPU link (F16 would be 5,120); record the actual path used.

At an *assumed* 100 microseconds per synchronous page fault, 16 serial faults cost
about 1.6 ms/token before compute. Batched prefetch or row caching can hide some of
that latency. Sequential SSD GB/s alone cannot predict it. Measure cold and warm
row accesses, queue depth, pages/read and requested versus actual bytes.

## State variables and invariants

| Category | State to record or control |
| --- | --- |
| Model | Shard/pack hashes, tensor type/shape/stride, compatibility conversions, all 512 experts/layer |
| Request | Frozen token IDs, context position, KV and recurrent state, PLE token history/EOS, HC state, RNG/sampling, output/EOS limits |
| MTP | Draft history and rollback, verified and accepted positions, rejection reason, expert union per window |
| Placement | Exact expert identities in GPU/RAM/NVMe, LRU/hotness, pinned bytes, in-flight transfers, completion events |
| Execution | Context allocation, buffers, batch/tile sizes, stream dependencies, thread/NUMA placement |
| Machine | GPU clocks/power/temperature, other processes, free RAM, OS page cache, PCIe link, storage bandwidth/latency |

Invariants:

1. Retain all experts and the model's top-k routing. Prefetch may predict reads;
   computation must use the actual routed experts. No pruning or skipped experts.
2. Keep original quantized expert and lookup bytes. Any repacking or conversion
   has a manifest and its own correctness comparison. Never silently change quant.
3. Preserve committed KV, recurrent and PLE state across rejected drafts,
   cancellation, EOS and cache eviction. A cache changes placement, not semantics.
4. Keep prompts, output limits, KV format and MTP policy fixed within each A/B arm.
   A different acceptance threshold is a separate quality-sensitive experiment.
5. Compare logits/state and greedy output against the unchanged same-quant engine.
   Floating-point reordering needs an explicit error envelope; bit identity is the
   default gate for changes that only move data. Existing MTP on/off differences
   are not evidence that a new optimization is harmless.
6. Preserve other workloads. Use an idle window, private processes, and terminate
   only our process group when another GPU job appears. Never flush global caches.

## Causal experiments

| Explanation | Intervention with other controls fixed | Evidence supporting it | What would falsify it |
| --- | --- | --- | --- |
| Expert I/O limits Q8 | Same replay, vary GPU cache budget; RAM-resident vs task-local cold expert reads | Time follows unique missed bytes / measured tier bandwidth | Bytes decrease but critical-path time does not |
| PLE fault latency limits decode | Same rows: warm cache vs isolated cold mapping; synchronous vs batched prefetch | Fewer serial faults reduce measured stalls | PLE waits are tiny or hiding them does not change unprofiled time |
| Q4 prefill refills unnecessary borrowed slots | Fixed 8K chunk, borrowed vs separately reserved buffers | Refill bytes disappear and prefill improves, experts still all fit | Refill disappears but prefill does not improve, or extra buffers evict experts |
| Verifier is bandwidth limited | Profile DRAM bytes and time by kernel; tile candidates together to reuse reads | DRAM traffic per emitted token falls with time | Bandwidth is low and math/dequant/occupancy dominates |
| Launch/synchronization dominates | Replay fixed work with fused operations/device scheduling | Fewer launches/waits lower time without changing bytes or logits | GPU kernel time already accounts for nearly all the critical path |
| MTP amortizes offload | Same teacher-forced route trace, T=1/2/4; deduplicate expert reads by window | Transfer bytes/emitted token fall with measured acceptance | Expert unions grow linearly, acceptance is low, or draft/verification waste exceeds savings |
| Kernel change really speeds generation | Paired A/B/B/A unprofiled trials, fixed outputs and warmup | Median and effective TPS improve beyond variation | Gain disappears outside profiler, depends on shorter output, or changes quality/state |

The single-token and MTP baselines are both required. A speedup from changing the
workload, quantization, prompt cache, output length, or stop policy does not count
as a kernel improvement.

## Representation that handles the awkward cases

Use immutable **tensor slices**: `(shard, offset, byte_length, dtype, shape,
strides, layer, expert, role)`. Do not assume all three expert projections occupy
one shard or have equal quantization. Q4 already splits layer 11 across shards.

Separate a slice's identity from a **residency record**: location, ready event,
version/generation, and outstanding readers. Eviction waits for readers; DMA
completion makes data ready. Represent an MTP window as a sparse map from a
distinct expert to its token/routing-weight uses. Fetch once, reuse, then scatter
results back in original token order. This makes duplicate routes and differing
expert sizes explicit instead of special cases in a launch loop.

For PLE, use a format descriptor with block elements, block bytes, row elements,
row bytes and decoder. Q8 has 170-byte rows, larger than upstream's 160-byte
maximum. This branch raises scratch capacity, selects the existing Q8 decoder,
checks offsets and file bounds, and validates unchanged rows against ggml.
Mapped Q8 works in the first smoke tests; direct-reader support remains gated.

## Ordered implementation and acceptance gates

1. **Baseline:** build the branch; Q4 MTP off/on at 8K, 2K output; collect identical
   frozen prompts and actual output lengths. First controlled intervention is
   `--no-prefill-borrow` with the chunk explicitly held at 8,192 (auto otherwise
   changes it to 2,048 and would confound the experiment).
2. **Q8 compatibility:** add a typed Q8_0 PLE reader with unchanged rows. Test
   signed values, scales, first/last row, block/page boundaries, malformed/truncated
   files and reopen. Compare rows against ggml and preserve IQ4/Q5/FP8 behavior.
   Start mapped mode; direct I/O only after its variable-row contract is verified.
   Validate the other Q8 tensors and pack conversions before declaring full support.
3. **Q8 fit:** bounded GPU cache + RAM complement + NVMe PLE. Record actual cache
   identities, resident/pinned RAM and headroom, including MTP and prompt buffers.
   Smoke-test with and without MTP, then run the same 8K workloads as Q4.
4. **Profile:** short Nsight Systems/Compute samples plus unprofiled companions.
   Record DRAM/L2 bytes, occupancy, integer/dequant instruction pressure, kernel
   duration, CPU/GPU gaps, H2D bytes/time, expert hit/union counts and PLE I/O.
5. **One optimization at a time:** window-aware Q4/Q8 tile reuse and grouped expert
   work; asynchronous double-buffered cold-expert fetch; PLE row prefetch/cache;
   fuse/device-schedule only demonstrated gaps. Consider existing K-quant MMQ
   prefill option as its own build arm; do not attribute prefill gains to decode.
6. **Coverage:** 8K+2K, 16K+4K, 64K+4K; code/prose plus counting as a favorable MTP
   control. At least three paired repeats after warmup for a claimed improvement.
   Include MTP off/on, fresh prompts, EOS/cancellation/rejection correctness and
   a long-context memory gate. Profiled wall time is never the speed headline.
7. **Publication:** separate compatibility, measurement, and performance commits;
   include failure/negative results, commands, revisions, hardware, prompts and raw
   evidence. Keep the branch experimental until correctness and repeated speed
   gains pass. Choose a small upstreamable change from the evidence; do not submit
   an unvalidated bundle as production support.

## What computation can explore

`tools/full_expert_roofline.py` varies bandwidth, cache miss rate, RAM coverage,
expert reuse and accepted tokens. It gives serial versus perfectly overlapped
reference times, not predicted performance. Use measured route traces next to
simulate LRU/LFU/profile-guided byte budgets, estimate unique expert unions and
derive Pareto frontiers for VRAM versus transfer bytes. Replay the same traces to
compare scheduling choices without confounding them with different generated text.

Parameter sweeps should search a constrained budget: cache bytes + dense + KV +
draft + workspace + reserve <= available VRAM, and resident complement + process
buffers + OS reserve <= available RAM. Fitting is necessary, not sufficient.
Reject a configuration that swaps, breaks correctness, or improves decode while
making total completion time worse for the intended workload.

Initial research targets, not results: Q4 at 300+ code tok/s would be a useful step
from 212; 400+ needs evidence of substantially better verification. For Q8, target
the measured hybrid bound rather than the infeasible all-GPU reference (246 tok/s
for original GGUF weights; 230 tok/s after the compatibility pack conversions).
MTP can help both, but cache locality, expert reuse, acceptance and draft cost must
demonstrate why the gain exists.
