# Experimental concurrent serving: Q4 at 32K

The research integration measured **275.8 combined committed output tokens/s**
on Unsloth **UD-Q4_K_XL**, with **eight concurrent requests**, each reading
**32,768 input tokens** and producing **512 output tokens**. Including prefill,
that is **35.7 effective output tokens/s**, or **114.83 seconds** to finish all
eight requests. Hardware: **RTX PRO 6000 Blackwell Workstation 96 GB**, existing
400 W power limit, Ryzen 9 7950X, 128 GB system RAM. KV: **FP16**.

These are synthetic coding workload measurements, not answer-quality scores or
single-stream speeds. This is a draft integration of upstream contributions and
small scheduler changes. The longer-context study continues separately.

## Credit and review scope

- [Strata](https://github.com/Niko1221/Strata) supplies the engine and batch kernels.
- **rkcth's [PR #846](https://github.com/Niko1221/Strata/pull/846)** supplies
  concurrent MTP, shared immutable draft weights, private slot state, accepted-prefix
  commits and bounded batch-graph caching. Its original authorship is preserved.
- David's [PR #947](https://github.com/Niko1221/Strata/pull/947) fixes fully
  resident batch graphs waiting for CPU doorbells that those graphs do not emit.
- This branch adds opt-in **non-MTP slot rotation**, keeps verifier allocation
  bounded at eight physical rows, reports per-slot proposed/accepted/committed
  work, and supplies NVIDIA measurements.

The draft starts at upstream `6f32ec0`. Review the shared functionality with
#846 and #947; this integration records their dependencies explicitly. Default
batch limits remain eight, and grouped MTP remains opt-in. Slot waves require
one GPU. This focused branch omits the research build's Q8 reader, exchange
adaptation and PDL changes; their historical results are identified below.

## Q4 research result: compare equal request counts

Research engine `cd9fcca`; each request is 32K input + 512 output, eight allocated
slots, 40,960 allocated context cells per slot. All 24,576 target experts occupy
71.73 GiB on the GPU; the approximately 26.8 GiB lookup table is locked in RAM.

| Concurrent requests | MTP decode tok/s | Non-MTP decode tok/s | MTP effective tok/s | Non-MTP effective tok/s |
|---:|---:|---:|---:|---:|
| 2 | 231.9 | 178.6 | 34.8 | 33.4 |
| 4 | 277.8 | 244.5 | 35.8 | 35.3 |
| 8 | 275.8 | 297.7 | 35.7 | 36.1 |

At two requests, MTP improved measured decode throughput **29.9%** and effective
throughput **4.2%**. At eight, the ordinary batch path was faster. These are
single screening observations, not repeated speedup estimates. There is no
claim that this PR adds 275.8 tok/s over upstream.

## Fresh build of this focused branch

Code commit **`4d56320`**, built independently from current upstream plus the
three focused code commits. CUDA build and all **11 frontend tests passed**.
The check completed **64 requests / 32,768 committed output tokens**:

- Q4: 2/4/8 concurrent requests in each policy at actual 32K input + 512 output.
  All **14 cross-policy output-token pairs matched exactly**. Recorded repeated
  requests across concurrency counts also matched.
- IQ3_S: 8/12/16 rotating non-MTP slots at actual 8K input + 512 output;
  every request completed and the overlapping-request token checks matched.

| Concurrent requests | MTP decode tok/s | Non-MTP decode tok/s | MTP effective tok/s | Non-MTP effective tok/s |
|---:|---:|---:|---:|---:|
| 2 | 232.4 | 178.2 | 34.9 | 33.3 |
| 4 | 278.0 | 244.4 | 35.8 | 35.3 |
| 8 | 276.2 | 297.3 | 35.7 | 36.1 |

The fresh Q4 N=2 comparison is **+30.4% decode / +4.7% effective** with MTP.
At N=8, MTP is **276.2 combined decode / 35.7 effective tok/s**; non-MTP is
**297.3 / 36.1**. This reproduces the historical result with the focused code;
PDL and the Q8 adaptation patches are absent. There is one observation per point.
The CPU frontend tests are separate from the GPU model checks above.

[Compact receipt](../bench/results/concurrent-serving-20261005/summary.json) |
[Full receipt and output hashes](https://github.com/CC-David-CC/Strata-a5500/blob/work/concurrency-waves/bench/concurrency-20261005/focused-receipt.json)

![Q4 focused-branch concurrency screen](https://raw.githubusercontent.com/CC-David-CC/Strata-a5500/work/concurrency-waves/bench/concurrency-20261005/q4-focused-32k.png)


## Broader research matrix

Historical integration results, eight concurrent requests, actual 32K input +
512 output per request. Every cell is **combined decode / effective tok/s**.

| Model | Grouped MTP | Non-MTP |
|---|---:|---:|
| Pruned Coder IQ1_M | 228.9 / 50.8 | 246.7 / 51.9 |
| Unsloth UD-IQ1_M | 290.7 / 41.3 | 313.5 / 42.2 |
| GSQ Q2_0 | 301.7 / 52.4 | 326.2 / 53.4 |
| GSQ IQ3_XXS | 291.6 / 49.1 | 313.0 / 49.9 |
| GSQ IQ3_S | 284.2 / 47.9 | 304.6 / 48.8 |
| Unsloth UD-Q4_K_XL | 275.8 / 35.7 | 297.7 / 36.1 |
| Unsloth Q8_0* | 85.7 / 8.5 | 84.6 / 8.5 |

At actual 64K input, non-MTP N=8 measured **299.2 / 26.3** for IQ3_S and
**308.4 / 27.0** for IQ3_XXS. Other 64K and 128K results were not complete at
this snapshot. They are ongoing research, not validation of this extracted branch.

*Q8 uses the broader integration, including the separate Q8 lookup reader from
[PR #865](https://github.com/Niko1221/Strata/pull/865). Exact tokens changed across
concurrency counts, and approximately 1.4-1.5 GiB of process swap was observed.
Reduced-cache Q4 also changed tokens. Their causes remain unclassified; neither
case is correctness-qualified by this table. The grouped decode path does not
advance the solo async-adaptation rounds, so these numbers do not establish an
adaptation or duplex-transfer benefit.

## Slot capacity is not a wider kernel

The physical verifier still has **eight rows**. Grouped MTP uses two per request
(current token plus one proposal), selecting at most four requests per window.
Non-MTP uses one row per request. Larger logical populations rotate groups; each
request has private state but shares model weights.

At 32K and fixed full-resident IQ3_S placement, non-MTP N=8/12/16 measured
304.1/302.8/303.0 combined tok/s. The slowest streams were 38.0/25.2/18.9 tok/s.
The current scheduler's throughput plateau is not a hardware-wide optimum.
Q4 with a reduced 65 GiB expert cache fell to about 233 combined tok/s; fitting
more slots did not improve its aggregate rate in that experiment.

## Reproduction and metric definitions

Build this branch with the normal CUDA build, native experts and architecture
120. Fresh validation uses CUDA 13.2 and an existing ccache. The model packs and
MTP runtime are prepared with Strata's normal tools; no model weights are included.

Use `--batch 8 --max-context 40960 --kv fp16 --spec 8 --mtp-max-t 4`, a 1024-token
prefill chunk, all 24,576 experts in the GPU cache, and RAM PLE. The MTP arm sets
`MULTI_CONCURRENCY=TRUE`; the control unsets it and uses `--mtp-max-t 1`.
`STRATA_BATCH_WAVES=1` permits a larger non-MTP slot allocation. It is unnecessary
for the N=8 throughput result. Ngram drafting is disabled.

For timing, prompt reuse and decode during cohort prefill are disabled. Every
input token is read. Greedy decoding is forced to exactly 512 output tokens by
using an unreachable EOS sentinel; this is a throughput workload, not a normal
chat stopping policy. All requests are admitted together. Combined steady decode
counts only **committed client tokens**, after every stream has emitted 64 tokens
until the first stream finishes. Effective throughput is total output tokens
divided by the full cohort wall time, including every prefill.

The [research archive and runnable harness](https://github.com/CC-David-CC/Strata-a5500/tree/work/concurrency-waves/bench/concurrency-20261005)
contain the broader matrix, source/binary identifiers, output hashes, arguments
and environment controls. The focused receipt in this branch records the fresh
build separately.

## Remaining validation

- Repeated and randomized-order throughput checks; longer-context knee study.
- First-divergence investigation for partially resident Q4/Q8.
- GPU sanitizer, accepted-prefix/rollback and cancellation/replacement checks on
  this exact extracted build. Python frontend tests do not establish GPU state safety.
- Multi-GPU execution is untested; opt-in waves reject it.
- Representative workloads beyond these synthetic coding prompts and fixed output lengths.

Keep this PR a draft until those limits have been reviewed. The scope is experimental
single-GPU concurrent serving; it does not change presets or enable public access.
