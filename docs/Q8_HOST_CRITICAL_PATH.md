# Q8 CPU and PCIe experiments on llm-60

These are research measurements on an experimental branch. Optimization flags
remain off by default; this is not an upstream release.
The frozen controls and every intervention are retained even when throughput is
similar. Equivalent speed can leave a different resource available for the next
experiment.

## Hardware and workload

- RTX PRO 6000 Blackwell **Workstation Edition**, 96 GB; SM 120.
- Ryzen 9 7950X, 128 GB RAM. Four DDR5 DIMMs report 3600 MT/s. PCIe is Gen 4 x16
  under load.
- Full Unsloth Qwen3.8-Flash-Next **Q8_0**, **FP16 KV**, native RoPE.
- 32,768 or 131,072 input tokens; allocation is input plus 8,192 positions.
- 1,024 requested output tokens, coding followed by editing. Each context/mode
  arm starts a fresh engine; expert adaptation carries from coding into editing
  identically within each arm.
- Plain, MTP, n-gram, and MTP plus n-gram are separate measurements.
- 15,472 GPU expert slots (75.25 GiB) and a 44.28 GiB pinned RAM complement are
  fixed across these trials. The lookup table is in system RAM. This is a
  controlled placement comparison, not a search for the largest GPU cache.
- Buffer ownership rotation is enabled. Adaptive completion waits remain enabled.
  Verification capacity is 8; the MTP window limit is 4. Speed projection is off.

The frozen control engine is `1a50d913bf910a1f63fbc1a0788a7083e3ca5f8c`, binary
SHA256 `d14ed6b69a1814ce4b5c08932a47d6921a55fa0aa8dea50427ccf0782d1ad997`.
The worker build is `777ac63e5f76c4f7a1e5c4253025ec5fc37b6a23`; the first duplex
model build is `a259773e8ff868ad142302b64a8173e3ae244098`. A subsequent HIP error-name
mapping change does not enter the CUDA build. HIP execution has not been tested
in this experiment.

## Independent starting points

| Path | Intervention | Invariant |
|---|---|---|
| Original host path | Per-window adaptive thread; sequential eviction then fill | Frozen baseline |
| Persistent worker | Reuse one adaptive thread and CUDA thread context | Same ranking, copies, join and admission waits |
| Duplex exchanges | Start a slot's fill after that slot's eviction; overlap other slots | Every overwrite waits for its own saved-out bytes; ownership waits for every fill |
| CPU pool configuration | Seven workers instead of fifteen | Model, placement, inputs and completion rules unchanged |

The duplex option is `STRATA_EXCHANGE_DUPLEX=1`. It currently applies to serving
with one GPU and a pinned resident complement. Mixed/file-backed swaps and peer
or multi-GPU placements retain the original path. The ordinary CLI path retains
sequential exchanges. The benchmark rejects a requested duplex arm if the log
does not show activation and actual duplex swaps.

Worker reuse is `STRATA_ADAPT_WORKER=1`; `STRATA_ADAPT_WORKER_CPU=N` selects its
CPU affinity. Without that setting it inherits the main thread's affinity.
`STRATA_HOST_TIMING=1` records host phases and bytes. These worker phases overlap
GPU execution; adding every phase duration would double-count elapsed time.

## Isolated copy result

The helper test used actual Q8-sized expert blobs of 5,222,400 bytes, 12
repetitions in alternating A/B and B/A order. Every outgoing word, incoming GPU
word and unchanged input buffer was checked outside the timed interval.

| Experts exchanged | Sequential median | Duplex median | Copy latency reduction |
|---:|---:|---:|---:|
| 1 | 0.3917 ms | 0.3817 ms | 2.54% |
| 4 | 1.4824 ms | 1.0844 ms | 26.85% |
| 16 | 5.8556 ms | 3.8396 ms | 34.43% |
| 96 | 35.0387 ms | 22.2541 ms | 36.49% |

All 96 benchmark samples passed exact copy checks. Compute Sanitizer's smaller
fixture run reported zero memory errors. This is a copy benchmark, **not a model
throughput speedup**. Actual generation savings depend on exchange batch counts
and transfer time left exposed after overlap with computation.

For example, a 2.02 ms saving on 128 exchange batches is about 259 ms. At roughly
3.2-3.9 committed tokens per MTP window, 128 output tokens instead correspond to
about 33-40 windows: 67-80 ms if each such window saves the full 2.02 ms. These
are conditional arithmetic examples, not measured model latency reductions.

## Correctness and interpretation

The new worker build with its optimization disabled passed exact output-token
and work-counter comparisons for plain and MTP at 32K. Worker helper tests passed
ASan/UBSan. GCC ThreadSanitizer initially could not reserve its shadow mapping;
the test passed with ASLR disabled **only for that fixture process**. No system
ASLR setting changed. The full CUDA build completed.

Plain and MTP worker-on cases at 32K and 128K matched tokens and work counters.
Their first throughput differences are below 0.3%, insufficient to establish a
speed benefit from one sample. Retain this path as a base for affinity and
overlap experiments.

N-gram selection uses measured window time. In the first worker comparison,
editing outputs matched but accepted draft counts changed; coding outputs first
diverged at token index 120 (32K) and 606 (128K). These are not matched-work
kernel comparisons. No claim that the divergence is harmless floating-point
noise has been established. Keep first divergence and work counts alongside
throughput; use fixed decision traces if isolating this effect becomes necessary.

Seven-worker 32K plain screening matched tokens and work counts and had similar
speed to fifteen workers. At 128K, plain decoding lost 2.28% for coding and 3.15%
for editing. MTP at both contexts stayed within 0.4% of the fifteen-worker
control. The free CPU cores make a separate adaptive-worker placement experiment
possible. Placement measurements must determine whether this helps.

## Initial full-model duplex results

The initial suite completed on 2026-10-04 at approximately 02:19 UTC. Both
default-off checks passed, then all eight active context/mode trials completed.
Every request generated 1,024 tokens and had zero file-backed expert reads.
The following rates are **decode throughput**, not prefill-inclusive throughput.
The control already has ownership rotation enabled. The only active change in
these candidate arms is duplex exchange; persistent-worker reuse is disabled.

| Input | Mode / task | Control tok/s | Duplex tok/s | Change | Tokens and work match? |
|---:|---|---:|---:|---:|---|
| 32K | Plain / coding | 71.80 | 73.49 | +2.36% | Yes |
| 32K | Plain / editing | 60.51 | 62.06 | +2.57% | Yes |
| 128K | Plain / coding | 72.99 | 74.88 | +2.59% | Yes |
| 128K | Plain / editing | 58.29 | 59.87 | +2.71% | Yes |
| 32K | MTP / coding | 122.20 | 130.18 | +6.53% | Yes |
| 32K | MTP / editing | 105.54 | 112.10 | +6.22% | Yes |
| 128K | MTP / coding | 124.78 | 132.20 | +5.94% | Yes |
| 128K | MTP / editing | 100.12 | 106.52 | +6.39% | Yes |
| 32K | N-gram / coding | 74.62 | 75.15 | +0.71% | No; first token difference at index 268 |
| 32K | N-gram / editing | 103.84 | 104.58 | +0.71% | Tokens match; work differs |
| 128K | N-gram / coding | 73.35 | 75.15 | +2.46% | No; first token difference at index 331 |
| 128K | N-gram / editing | 90.67 | 101.35 | +11.78% | Tokens match; work differs |
| 32K | MTP + n-gram / coding | 121.53 | 128.76 | +5.95% | Yes |
| 32K | MTP + n-gram / editing | 102.97 | 108.70 | +5.57% | Tokens match; work differs |
| 128K | MTP + n-gram / coding | 124.49 | 131.43 | +5.58% | Yes |
| 128K | MTP + n-gram / editing | 99.16 | 103.93 | +4.80% | Tokens match; work differs |

These are the initial pairs; reversed-order results appear below. N-gram work
differences mean those rows do not isolate copy speed. Its output divergences
have not been classified as acceptable numerical error. Matching tokens and
recorded counters is also narrower than proving identical internal states.

For MTP, prefill-inclusive output rates changed as follows:

| Input / task | Control effective tok/s | Duplex effective tok/s |
|---|---:|---:|
| 32K / coding | 62.65 | 64.76 |
| 32K / editing | 58.63 | 60.58 |
| 128K / coding | 25.36 | 25.65 |
| 128K / editing | 24.18 | 24.56 |

The gain is in decoding; the long prompt limits its effect on total request
time. At 32K plain coding, measured join plus admission wait fell from 1.104 to
0.742 ms per output token. At 32K MTP coding, the same-build flag-off check had
1.594 ms of join and 2.147 ms of admission wait per window; duplex had 2.045 ms
of join and 0.072 ms of admission wait. Copy bytes and work were unchanged.
The larger D2H/join time alongside a much smaller admission wait is consistent
with overlapping directions, rather than eliminating the copies.

The earlier [ownership report](Q8_EXCHANGE_ROTATION.md) measured MTP coding
gains of 17.1% and 23.3% in two 64K pairs, and editing gains of 21.2% and 24.0%.
The new duplex gain is measured on top of ownership, but these tests have
different contexts and GPU cache capacity. Do not add the percentages or claim
a combined gain against the original copy baseline without a matched test.
The 17.1% result is the smaller measured 64K coding gain, not a universal floor.

## Where the search goes next

| Path | Evidence now | Next discriminating measurement |
|---|---|---|
| Ownership rotation | Repeated 64K gain, already published | Retain as an established base |
| Duplex PCIe copies | Repeated MTP and plain gains at 32K/128K | Combine with separately tested host configurations |
| Persistent worker | Throughput effectively tied when sharing the main CPU | Move only the worker to another CPU; compare matched work |
| Smaller CPU pool | MTP tied while freeing physical cores; 128K plain regressed | Put the adaptive worker on a freed physical core |
| Combined configuration | Not measured | Combine an independently measured placement winner with duplex |
| Defer ownership metadata publication | Design only | Preserve readable-buffer and completion contracts, then measure exposed waits |
| Admit experts per layer | Design only | Measure copy readiness by layer before replacing the global admission wait |
| Further GPU optimization | CUPTI evidence is available; not this intervention | Re-profile the remaining critical path after host changes |

An estimated 1.3-1.4 ms adaptive-worker start delay in 32K MTP comes from the
recorded phase budget; it is **not** a directly measured dispatch timestamp.
The worker shares the main thread's CPU in these controls. Affinity experiments
are intended to test that explanation, not assume it is correct.

## Reversed-order confirmation

The follow-up suite completed with all token and recorded work comparisons
passing. Every pair below ran duplex **on before off**, with fresh engines,
the same source `a259773e8ff868ad142302b64a8173e3ae244098` and binary SHA256
`6c690e1d71cac554e649c4f196b1b533f8633a4c240d173df0a780280d850223`.
The source's later HIP error-name aliases do not enter this CUDA build.

| Input / mode / task | Duplex off tok/s | Duplex on tok/s | Paired gain |
|---|---:|---:|---:|
| 32K / MTP / coding | 121.77 | 130.51 | +7.18% |
| 32K / MTP / editing | 105.53 | 112.21 | +6.33% |
| 128K / MTP / coding | 124.95 | 131.93 | +5.58% |
| 128K / MTP / editing | 100.30 | 106.12 | +5.80% |
| 32K / plain / coding | 71.71 | 73.80 | +2.91% |
| 32K / plain / editing | 60.52 | 61.99 | +2.44% |
| 128K / plain / coding | 73.13 | 74.88 | +2.39% |
| 128K / plain / editing | 58.28 | 59.62 | +2.30% |

MTP effective output rates, including prefill and request wall time, were
62.56 to 64.80 and 58.63 to 60.63 tok/s for 32K coding/editing; 25.36 to 25.64
and 24.21 to 24.55 for 128K. These smaller gains follow from prefill's share of
the request. Model startup is excluded. All 16 requests reached 1,024 output
tokens and had zero file-backed expert reads. This is two observations per
context/task/arm, not a large-sample confidence interval.

## Worker placement screening

All six arms completed with exact tokens and work at 32K MTP. The adjacent
control used the same CPU pool size and persistent worker pinned to CPU 0.

| Worker placement | Coding tok/s, candidate / control | Editing tok/s, candidate / control |
|---|---:|---:|
| CPU 16, pool 15 | 123.05 / 122.09 (+0.78%) | 106.04 / 105.82 (+0.21%) |
| CPU 24, pool 15 | 122.86 / 122.21 (+0.52%) | 106.06 / 105.89 (+0.16%) |
| CPU 8, pool 7 | 123.25 / 122.75 (+0.41%) | 106.31 / 105.72 (+0.56%) |

CPU 16 is the main core's SMT sibling; CPU 24 is a sibling on another physical
core; CPU 8 is a free physical core with the seven-worker pool. Moving the worker
made launch itself cheaper, but other waits grew. These sub-1% differences do
not establish a large dispatch bottleneck or justify a default affinity change.
The CPU16/pool15 and CPU8/pool7 combinations with duplex are being screened
separately. Neither combination result is part of the gain claims above.

## Repeated work still present

- Ownership rotation eliminated the extra RAM-to-RAM payload copy at commit.
  Eviction and promotion still move the expert bytes across PCIe in opposite
  directions because RAM holds the GPU cache's complement, not every expert.
- In the 32K MTP coding request, adaptation moved 19.71 decimal GB each way;
  editing moved 21.69 GB each way. Duplex changes overlap, not byte counts.
- The residency upload still copies the whole 24,576-entry int32 table after a
  batch, even when few entries changed. Its measured host interval is only
  about 3-6 microseconds per window in these runs.
- Q8 grouped GPU kernels in this host branch still call the row dot once per
  matching token. The earlier `perf/q8-expert-reuse` alternative reuses weight
  fragments, but its old fixed-placement MTP screen gained less than 0.5%.
  Repeated load instructions are not proof of repeated DRAM transactions.
- Duplex still waits for D2H on the adaptive task and H2D at admission. A new,
  separate deferred-publication experiment keeps the per-slot dependencies but
  postpones metadata publication until the final event. It is not included in
  this branch or any reported speedup.

## Evidence and remaining work

Local plans, source/archive hashes, live matrices, tokens, work comparisons and
host timing summaries are under
`.fleet_work/strata/q8-host-critical-20261004/` in the fleet workspace.
Remote runs are under `~/fleet-downloads/rtxpro-q8-host-*` and
`~/fleet-downloads/rtxpro-q8-duplex-*`. `collect.py` refreshes the local evidence;
`analyze.py` derives the comparison table without discarding mismatches.

The initial matrix, worker placement screen and reversed-order plain/MTP suite
are complete. [Exported measurements](benchmarks/q8-host-path-20261004.json)
include source/binary hashes, prompt/token hashes, per-request timings and every
comparison, including mismatches. `tools/summarize_q8_host_evidence.py` generates
that export from the local collector output. N-gram policy comparisons remain
separately qualified. Follow-up combination and deferred-admission experiments
are separate from this published snapshot. Main remains unchanged.
