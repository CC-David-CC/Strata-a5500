# Q8 CPU / PCIe miss balance

Configuration experiment on llm-60: RTX PRO 6000 Blackwell Workstation Edition
96GB, Ryzen 7950X, 128GB RAM, full Unsloth Q8_0, FP16 KV and native RoPE. Based
on the measured duplex branch and its component-validated Q8 instrumentation.
Main is unchanged. The all-GPU miss test completed and was slower in every mode.

## Evidence motivating the test

With 15,472 expert slots, adaptive ownership rotation, duplex exchanges and
automatic PCIe fraction 0.55, the current 32K MTP control measured:

| Workload | Tokens/window | CPU experts/layer/window | PCIe experts/layer/window | CPU work/window | Total/window |
|---|---:|---:|---:|---:|---:|
| Coding | 3.23 | 0.91 | 0.52 | 6.98 ms | 25.03 ms |
| Editing | 3.91 | 1.74 | 1.29 | 13.89 ms | 34.92 ms |

These are host timing categories, not GPU hardware counters. Source
`b926ad75744f20652e940db9141900bc91f1b48f`, engine SHA-256
`22d90a60f002a38833c44c4834d082a400540c8fb5c84c80997594075a02d2ee`.

`expert_pool_dispatch_multi` computes the PCIe share as
`(nmiss * pcie_num) >> 8` for each layer/window. With a fraction below one,
a single distinct miss therefore goes to the CPU. The observed GPU share
of missed experts is lower than the nominal 0.55, particularly when there
are only one or two misses. Eliminating that CPU work could be more valuable
than the tied result from grouped Q8 weight reuse.

## Intervention

Use the same binary with `--pcie-frac 1 --pcie-mode auto`, leaving Q8 weight
reuse off. Send eligible pinned-RAM misses to the existing GPU staging path,
subject to its existing staging capacity. This is a placement configuration,
not a new kernel. Keep 15,472 resident slots, FP16 KV, model bytes, native
context, ownership rotation, duplex transfers, MTP parameters and stopping
policy fixed.

First screen plain, MTP, n-gram and combined at 32,768 actual input tokens,
40,960 allocation, 1,024 output tokens, coding then editing. Each arm starts a
fresh engine. Compare to the same-binary controls from the preceding matrix.
Record first token divergence, work/acceptance changes, CPU expert counts,
logical PCIe payload, transfer timing, RAM/VRAM and any expert file reads.

Moving expert arithmetic from CPU to GPU can change floating-point rounding.
Do not describe changed token streams or work as an exact-output kernel gain.
If the GPU-only placement helps, bracket the split, repeat promising cases in
reversed order, and test 128K. The all-four-mode scope remains intact.

Falsifier: additional PCIe and GPU computation cost outweighs the removed CPU
work, or correctness/state failures appear. Actual link counters and timelines
will test that explanation; nominal fraction alone is insufficient evidence.

## Model identification

The frozen engine prints a stale hardcoded `Q5_K head` label. Inspection of the
actual input GGUF found `output.weight` in Q8 shard 2: Q8_0, shape
`[2560, 248320]`, 675,430,400 bytes, exactly the uploaded byte count. The loader
uploads the original tensor bytes and records its actual type. This branch
corrects the log/help text for future builds; the queued configuration test
continues using the already validated `b926ad75` binary. No head conversion or
model replacement was performed.

## Completed all-GPU miss screen

Output tokens/s, coding / editing. Same frozen binary and model, 32,768 input
tokens plus 1,024 output tokens; allocation 40,960. Reference controls used the
automatic split; candidate used `--pcie-frac 1`. Fresh engine for each mode,
coding followed by editing. These are first-screen results, not randomized repeats.

| Mode | Automatic split | All eligible misses on GPU | Change, coding / editing |
|---|---:|---:|---:|
| Plain | 73.61 / 61.91 | 60.58 / 45.99 | -17.7% / -25.7% |
| MTP | 129.04 / 111.93 | 98.30 / 78.16 | -23.8% / -30.2% |
| N-gram | 75.03 / 105.17 | 60.81 / 75.32 | -18.9% / -28.4% |
| MTP + n-gram | 130.29 / 111.27 | 98.09 / 74.18 | -24.7% / -33.3% |

Editing output tokens matched in all four modes. Coding first diverged at
tokens 122, 473, 173 and 311 respectively. Work counters differed, so these
are placement comparisons, not exact-work kernel comparisons or quality scores.
All requests completed 1,024 output tokens with zero expert file reads.

In MTP, CPU expert time became approximately zero, but mean host waiting for
GPU progress rose from 12.39 to 26.93 ms/window for coding, and from 14.54 to
43.31 ms/window for editing. Total window time rose from 25.03 to 32.66 ms and
34.92 to 50.01 ms respectively. Host waiting for GPU progress does not mean the
GPU was idle. This result rejects the simple hypothesis that eliminating CPU
expert work would improve this configuration. Separate automatic-split captures recorded DRAM and PCIe traffic; an
all-GPU-miss hardware-counter comparison has not been collected.

The completed all-CPU miss control (`--pcie-frac 0`) is below; the 15,472 resident
GPU experts remain on GPU. It tests the opposite placement extreme.

Raw measurements and comparisons: [q8-pcie-placement-20261004.json](benchmarks/q8-pcie-placement-20261004.json).

## Completed CPU-only miss screen

The resident GPU cache remains enabled. Only missing experts move to the CPU
(`--pcie-frac 0`). Same frozen binary, 32K input plus 1,024 output, coding then
editing. This is one screen against the earlier same-binary controls.

| Mode | Automatic split, coding / editing | CPU-only misses, coding / editing | Change |
|---|---:|---:|---:|
| Plain | 73.61 / 61.91 | 73.91 / 62.67 | +0.4% / +1.2% |
| MTP | 129.04 / 111.93 | 138.05 / 115.99 | +7.0% / +3.6% |
| N-gram | 75.03 / 105.17 | 77.39 / 113.80 | +3.1% / +8.2% |
| MTP + n-gram | 130.29 / 111.27 | 134.12 / 112.22 | +2.9% / +0.9% |

Editing tokens matched in all modes. Coding first differed at tokens 120, 120,
32 and 120 respectively; work counters changed. Effective output throughput
gained 2.8% / 1.9% for MTP and 2.0% / 4.3% for n-gram. These placement changes
are not exact-work kernel gains. The initial measurements motivated the fresh
paired repeats reported below.

MTP coding GPU-reach wait fell from 12.39 to 10.26 ms/window while CPU expert
work rose from 6.98 to 7.75. Editing wait fell from 14.54 to 9.28 while CPU work
rose from 13.89 to 18.12. The CPU remains useful even when more work is assigned
to it; eliminating the missed-expert GPU transfers reduced the measured total
window time. Hardware/timeline profiling is needed to separate the costs.

Reversed-order 32K MTP/n-gram repeats and fresh native-128K pairs in all four
modes are complete below. This configuration is independent of retained copies.

Evidence: [q8-pcie-cpu-only-20261004.json](benchmarks/q8-pcie-cpu-only-20261004.json).

## Fresh paired repeats and native 128K

Completed 12 arms / 24 requests. Same frozen binary, fixed 15,472 GPU slots,
FP16 KV, native RoPE, actual 32,768 or 131,072 input tokens, allocation input
plus 8,192, and 1,024 output tokens. A fresh engine per arm ran coding then
editing, so adaptation from coding carries into editing. At 32K the CPU arm
ran first and the automatic arm second; at 128K the order was automatic then
CPU. These are paired measurements, not confidence intervals or a quality score.

The baseline already includes ownership rotation and duplex copies. These
gains are additional configuration effects measured against that baseline;
do not multiply them by historical gains from unmatched requests.

### 32K reversed repeats: output tokens/s

| Mode | Automatic split, code / edit | CPU-only misses, code / edit | Change, code / edit |
|---|---:|---:|---:|
| MTP | 130.29 / 111.98 | 135.64 / 114.50 | +4.11% / +2.25% |
| N-gram | 74.50 / 100.67 | 75.98 / 110.51 | +1.98% / +9.77% |

### 128K fresh pairs: output tokens/s

| Mode | Automatic split, code / edit | CPU-only misses, code / edit | Change, code / edit |
|---|---:|---:|---:|
| Plain | 74.83 / 59.85 | 74.94 / 60.38 | +0.14% / +0.88% |
| MTP | 131.82 / 106.25 | 137.16 / 110.44 | +4.05% / +3.95% |
| N-gram | 74.41 / 102.50 | 74.75 / 104.34 | +0.47% / +1.80% |
| MTP + n-gram | 131.76 / 102.86 | 134.82 / 110.13 | +2.32% / +7.07% |

### Prefill-inclusive effective output tokens/s

Effective throughput is output tokens divided by complete request wall time.
Engine startup/loading is excluded. This is not total input-plus-output token throughput.

32K:

| Mode | Automatic split, code / edit | CPU-only misses, code / edit | Change, code / edit |
|---|---:|---:|---:|
| MTP | 64.80 / 60.55 | 66.27 / 61.26 | +2.26% / +1.17% |
| N-gram | 47.25 / 57.20 | 47.95 / 60.23 | +1.49% / +5.29% |

128K:

| Mode | Automatic split, code / edit | CPU-only misses, code / edit | Change, code / edit |
|---|---:|---:|---:|
| Plain | 22.35 / 20.82 | 22.36 / 20.92 | +0.04% / +0.48% |
| MTP | 25.66 / 24.53 | 25.82 / 24.79 | +0.64% / +1.06% |
| N-gram | 22.32 / 24.38 | 22.33 / 24.53 | +0.06% / +0.63% |
| MTP + n-gram | 25.64 / 24.36 | 25.74 / 24.75 | +0.38% / +1.59% |

### Output and work qualifications

| Input / mode | First different token, code / edit (zero-based) | Recorded work identical, code / edit |
|---|---|---|
| 32,768 / MTP | 120 / match | no / no |
| 32,768 / N-gram | 32 / match | no / no |
| 131,072 / Plain | 221 / match | no / no |
| 131,072 / MTP | 221 / match | no / no |
| 131,072 / N-gram | 308 / match | no / no |
| 131,072 / MTP + n-gram | 221 / match | no / no |

CPU/GPU placement changes floating-point execution. Matching output does not
make these exact-work kernel comparisons: expert-tier and speculative counters
may differ. N-gram scheduling also varied between repeats. The CPU-only MTP
32K repeat matched the earlier CPU-only run's tokens and recorded work exactly,
but the automatic-versus-CPU comparisons have the differences above. No task
quality evaluation was performed. Every request reached its output budget with
zero decode expert file reads; no OOM or failed request was observed.

### Reproduce the intervention

Starting from the measured Q8 command, use `--pcie-frac 0` for CPU-only misses,
or `--pcie-frac 0.55` for the matched automatic split. The primary GPU cache
remains 15,472 experts. Keep `--pcie-mode auto`, FP16 KV, native context,
`STRATA_EXCHANGE_ROTATE=1`, `STRATA_EXCHANGE_DUPLEX=1`,
`STRATA_ADAPT_NOWAIT=0`, `STRATA_ADAPT_WORKER=0` and
`STRATA_Q8_EXPERT_REUSE=0`. The recorded matrix includes all launch commands,
per-arm options, prompt hashes, token IDs and work counters. This branch does
not change the default miss fraction or configure a public service.

The CPU-only setting is retained as a separate performance configuration.
The next experiment is an independently gated, read-only secondary GPU miss
cache, which aims to retain GPU execution while avoiding repeated uploads.
No speed result for that new cache is claimed here.

Evidence: [completed repeat matrix](benchmarks/q8-pcie-repeat-128k-20261004.json).
