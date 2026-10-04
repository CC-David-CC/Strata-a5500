# Frozen Q8 configurations and results - 2026-10-04

Experimental fork of [Niko1221/Strata](https://github.com/Niko1221/Strata), by David.
Upstream credit and the original license are retained. Main is unchanged.

## Freeze decision

Optimization is **paused at the user's request**. All three remaining optimizer
units were stopped; no automatic experiment queue is running. Branches, source,
binaries, completed records and incomplete attempts are preserved.

- **LAN default:** per-layer admission, MTP on, n-gram off, Q8_0 with FP16 KV.
  This is the strongest scheduling candidate with exact matched-work results,
  repeated 32K MTP gains, native 128K results and a 33-request lifecycle gate.
- **Bandwidth alternative:** GPU refills, sixteen secondary slots per layer.
  MTP primary adaptive-refill RAM uploads fell **61.85%**, from **41.4084 GB
  to 15.7978 GB**, across the two measured 32K requests. **25.6106 GB** moved
  inside the GPU instead. The saving repeated; small TPS gains do not invalidate
  this resource benefit. Primary victim writebacks stayed at 41.4084 GB.
  This is logical primary-refill payload, **not total PCIe traffic, GPU DRAM
  traffic, measured energy, or a claim that bandwidth was the only bottleneck**.
- **N-gram alternatives:** retain the larger-secondary-cache parent and the
  per-layer configurations separately. Timing-dependent speculation changed
  work and sometimes output. An editing output match does not prove all-prompt
  equivalence. No universal winner is claimed.
- **Larger primary cache:** 16,560 slots reached 145.68 / 127.46 coding/editing
  tok/s at 32K, but changed arithmetic placement/work, and coding diverged at
  token 120. Single pair, less headroom, no 128K coverage: preserved as an
  alternative rather than selected for the endpoint.
- **Combined layer admission + GPU refills:** source prepared, model/build
  tests not started. **Cached-CPU rerouting:** components/build passed, actual
  model/numerical tests not started. Both are paused, not passed or failed.

## Measurement definitions

Hardware: **llm-60, RTX PRO 6000 Blackwell Workstation Edition 96 GB**, Ryzen
7950X, 128 GB installed RAM (DDR5 at 3600 MT/s), PCIe 4 x16. Full Unsloth
Qwen3.8-Flash-Next Q8_0; FP16 KV and native RoPE throughout the current matrix.
Text only. 32K means 32,768 input; 128K means 131,072 input. Each current
throughput request generated **1,024 tokens**. Allocations were 40,960 and
139,264 positions. No 1M claim is carried into the native-context endpoint.

Output tok/s is generation throughput. Effective tok/s is generated tokens
divided by prefill plus generation time; startup is excluded. Arms start a
fresh engine; coding then editing share adaptation within that arm. These
numbers are not an HTTP load test or a service SLA. The full HTTP checks are
reported separately in the deployment validation artifact.

Both repeated run orders passed at 32K for the selected MTP scheduling path
and for plain/MTP GPU refills. There is no confidence interval. Native 128K
layer results are first pairs; the 33-request STOP/checkpoint lifecycle suite
was at 32K. GPU-refill 128K was interrupted before a candidate result.

## Selected scheduling configuration: every mode and context

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 32768-plain-admission-layer | 32,768 | 1,024 | Plain | coding | 77.52 | 48.54 | 4157.16 | 7.88 | 21.09 | Exact output and recorded work versus paired control |
| 32768-plain-admission-layer | 32,768 | 1,024 | Plain | editing | 65.54 | 43.85 | 4243.08 | 7.72 | 23.35 | Exact output and recorded work versus paired control |
| 32768-mtp-admission-layer | 32,768 | 1,024 | MTP | coding | 144.56 | 68.27 | 4141.77 | 7.91 | 15.00 | Exact output and recorded work versus paired control |
| 32768-mtp-admission-layer | 32,768 | 1,024 | MTP | editing | 124.43 | 64.02 | 4221.48 | 7.76 | 15.99 | Exact output and recorded work versus paired control |
| 32768-ngram-admission-layer | 32,768 | 1,024 | Plain+ngram | coding | 78.87 | 49.06 | 4156.21 | 7.88 | 20.87 | * First output difference at token 120; work may differ |
| 32768-ngram-admission-layer | 32,768 | 1,024 | Plain+ngram | editing | 108.65 | 59.72 | 4245.27 | 7.72 | 17.14 | * Matching output; speculative work differs |
| 32768-mtp-ngram-admission-layer | 32,768 | 1,024 | MTP+ngram | coding | 143.82 | 68.17 | 4149.16 | 7.90 | 15.02 | * First output difference at token 311; work may differ |
| 32768-mtp-ngram-admission-layer | 32,768 | 1,024 | MTP+ngram | editing | 122.80 | 63.56 | 4218.98 | 7.77 | 16.11 | * Matching output; speculative work differs |
| 131072-plain-admission-layer | 131,072 | 1,024 | Plain | coding | 78.21 | 22.66 | 4085.12 | 32.09 | 45.18 | Exact output and recorded work versus paired control |
| 131072-plain-admission-layer | 131,072 | 1,024 | Plain | editing | 63.46 | 21.25 | 4091.51 | 32.04 | 48.17 | Exact output and recorded work versus paired control |
| 131072-mtp-admission-layer | 131,072 | 1,024 | MTP | coding | 145.06 | 26.10 | 4076.09 | 32.16 | 39.22 | Exact output and recorded work versus paired control |
| 131072-mtp-admission-layer | 131,072 | 1,024 | MTP | editing | 118.45 | 25.14 | 4086.50 | 32.07 | 40.72 | Exact output and recorded work versus paired control |
| 131072-ngram-admission-layer | 131,072 | 1,024 | Plain+ngram | coding | 78.20 | 22.66 | 4084.95 | 32.09 | 45.18 | * First output difference at token 221; work may differ |
| 131072-ngram-admission-layer | 131,072 | 1,024 | Plain+ngram | editing | 113.53 | 24.94 | 4092.82 | 32.02 | 41.04 | * Matching output; speculative work differs |
| 131072-mtp-ngram-admission-layer | 131,072 | 1,024 | MTP+ngram | coding | 144.30 | 26.08 | 4077.31 | 32.15 | 39.24 | Exact output and recorded work versus paired control |
| 131072-mtp-ngram-admission-layer | 131,072 | 1,024 | MTP+ngram | editing | 118.61 | 25.16 | 4090.39 | 32.04 | 40.68 | * Matching output; speculative work differs |

Plain/MTP match exact output, recorded work, primary transfer payload and
secondary counters against their own control. See the
[per-layer report](Q8_LAYER_ADMISSION.md) for controls, gains and repeat rates.
The serving default uses MTP without n-gram. Rows with `*` retain the actual
observations and are not described as identical-work gains.

## Bandwidth-saving alternative: complete 32K matrix

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 32768-mtp-gpu-refill | 32,768 | 1,024 | MTP | coding | 140.58 | 67.36 | 4140.82 | 7.91 | 15.20 | Exact output and recorded work versus paired control |
| 32768-mtp-gpu-refill | 32,768 | 1,024 | MTP | editing | 126.32 | 64.52 | 4222.35 | 7.76 | 15.87 | Exact output and recorded work versus paired control |
| 32768-plain-gpu-refill | 32,768 | 1,024 | Plain | coding | 76.78 | 48.15 | 4134.45 | 7.93 | 21.26 | Exact output and recorded work versus paired control |
| 32768-plain-gpu-refill | 32,768 | 1,024 | Plain | editing | 66.19 | 44.15 | 4244.39 | 7.72 | 23.19 | Exact output and recorded work versus paired control |
| 32768-ngram-gpu-refill | 32,768 | 1,024 | Plain+ngram | coding | 79.31 | 49.26 | 4162.60 | 7.87 | 20.78 | * First output difference at token 288; work may differ |
| 32768-ngram-gpu-refill | 32,768 | 1,024 | Plain+ngram | editing | 121.47 | 63.36 | 4241.37 | 7.73 | 16.16 | * Matching output; speculative work differs |
| 32768-mtp-ngram-gpu-refill | 32,768 | 1,024 | MTP+ngram | coding | 139.67 | 67.11 | 4136.07 | 7.92 | 15.25 | Exact output and recorded work versus paired control |
| 32768-mtp-ngram-gpu-refill | 32,768 | 1,024 | MTP+ngram | editing | 123.80 | 63.81 | 4216.70 | 7.77 | 16.04 | Exact output and recorded work versus paired control |

The [GPU-refill report](Q8_GPU_REFILLS.md) includes controls and reversed-order
plain/MTP pairs. Repeated MTP gains were +1.41% coding / +1.38% editing, with
exact output/work and unchanged primary victim counts. The byte saving is a
separate success metric. Combining it with per-layer scheduling is untested.

## Alternative cache allocations and n-gram path

| Configuration | Input | Output | Mode | Task | Output tok/s | Effective tok/s | Prefill tok/s | Prefill s | Prefill + decode s | Qualification |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 32768-mtp-primary15472-ways16 | 32,768 | 1,024 | MTP | coding | 137.51 | 66.55 | 4129.08 | 7.94 | 15.38 | Exact output and recorded work versus paired control |
| 32768-mtp-primary15472-ways16 | 32,768 | 1,024 | MTP | editing | 123.36 | 63.75 | 4224.69 | 7.76 | 16.06 | Exact output and recorded work versus paired control |
| 32768-plain-primary15472-ways16 | 32,768 | 1,024 | Plain | coding | 75.50 | 47.75 | 4158.06 | 7.88 | 21.44 | Exact output and recorded work versus paired control |
| 32768-plain-primary15472-ways16 | 32,768 | 1,024 | Plain | editing | 64.71 | 43.48 | 4244.12 | 7.72 | 23.54 | Exact output and recorded work versus paired control |
| 131072-mtp-primary15472-ways16 | 131,072 | 1,024 | MTP | coding | 138.43 | 25.89 | 4078.18 | 32.14 | 39.54 | Exact output and recorded work versus paired control |
| 131072-mtp-primary15472-ways16 | 131,072 | 1,024 | MTP | editing | 116.35 | 25.03 | 4085.26 | 32.08 | 40.89 | Exact output and recorded work versus paired control |
| 131072-plain-primary15472-ways16 | 131,072 | 1,024 | Plain | coding | 76.19 | 22.49 | 4085.68 | 32.08 | 45.52 | Exact output and recorded work versus paired control |
| 131072-plain-primary15472-ways16 | 131,072 | 1,024 | Plain | editing | 62.26 | 21.11 | 4089.58 | 32.05 | 48.50 | Exact output and recorded work versus paired control |
| 131072-ngram-primary15472-ways16 | 131,072 | 1,024 | Plain+ngram | coding | 76.07 | 22.47 | 4083.32 | 32.10 | 45.56 | Exact output and recorded work versus paired control |
| 131072-ngram-primary15472-ways16 | 131,072 | 1,024 | Plain+ngram | editing | 111.15 | 24.86 | 4101.27 | 31.96 | 41.17 | * Matching output; speculative work differs |
| 131072-mtp-ngram-primary15472-ways16 | 131,072 | 1,024 | MTP+ngram | coding | 137.74 | 25.86 | 4077.56 | 32.14 | 39.58 | Exact output and recorded work versus paired control |
| 131072-mtp-ngram-primary15472-ways16 | 131,072 | 1,024 | MTP+ngram | editing | 117.81 | 25.10 | 4085.87 | 32.08 | 40.77 | * Matching output; speculative work differs |
| 32768-mtp-primary16560-ways4 | 32,768 | 1,024 | MTP | coding | 145.68 | 72.39 | 4607.81 | 7.11 | 14.14 | * First output difference at token 120; work may differ |
| 32768-mtp-primary16560-ways4 | 32,768 | 1,024 | MTP | editing | 127.46 | 68.24 | 4703.86 | 6.97 | 15.00 | * Matching output; speculative work differs |

Cache capacity changes are configurations; moving more primary experts onto
the GPU changes arithmetic placement. Percentages from separate branches
must not be added or multiplied. Keep each recorded setup with its own control.

## What remains preserved but paused

| Path | Evidence at freeze | Disposition |
|---|---|---|
| Buffer ownership rotation | Repeated 64K FP16 MTP gains about 17-24%; separate 1M YaRN plain result 41.45 to 44.85 tok/s | Included in later paths; keep original 64K/1M reports |
| Duplex transfers | Repeated plain gains 2.3-2.9%, MTP 5.6-7.2%; exact tokens/work | Included in selected configuration |
| Secondary read-only cache, overlap, copy-grid tuning | Passed components/lifecycle and matched-work model comparisons | Included in selected configuration; settings frozen |
| Sixteen secondary entries per layer | Repeated 32K plain/MTP gain; 128K all modes measured | Separate capacity and bandwidth alternative |
| Per-layer admission | Repeated 32K MTP; all 128K modes complete | Selected endpoint engine |
| GPU refills | Actual 61.85% primary refill-upload saving, exact plain/MTP, repeated small speed gains | Freeze as a resource-saving alternative |
| Whole-batch deferred publication | Approximately flat, below per-layer result | Preserve comparator |
| Persistent worker / CPU affinity / smaller CPU pool | No material repeatable gain in tested cases | Preserve; not selected |
| CPU Q8 weight reuse / compact miss fills | Small or negative gains; compact improvement did not survive follow-up | Preserve negative results |
| Retained FIFO RAM copies | About 0.47% writeback saving, slower | Preserve negative result |
| Seeded 8 GiB RAM copies | About 11.3% fewer writeback bytes, flat/slower | Preserve resource saving separately from speed |
| Send all missed experts to GPU | 17-33% slower in tested cases | Preserve negative result |
| Cached-CPU rerouting | Component/build checks passed; model tests never started | Paused, unvalidated for serving |
| Layer admission plus GPU refills | Source prepared; no build/model test result | Paused, no combined gain claim |
| Q4 optimization | Previously published; parked before this Q8 freeze | Not a Q8 result; no new tests |

Earlier Q8 numbers with INT8 KV and different placement (for example 47.45 /
29.90 plain and 78.07 / 42.96 MTP coding/editing at 64K) are historical context,
not a controlled comparison to this FP16 32K/128K matrix.

## Reproducibility and complete records

- [All completed current hillclimb observations](Q8_FROZEN_ALL_MEASUREMENTS.md):
  every retained completed record, including controls, repeats, regressions
  and explicitly labeled diagnostics. No row is manufactured for unfinished work.
- [Machine-readable measurements](benchmarks/q8-frozen-20261004/complete-measurements.json).
- [Frozen branch inventory](benchmarks/q8-frozen-20261004/branch-inventory.json).
- [Exact measured profile index](benchmarks/q8-frozen-20261004/profile-index.json).
- [LAN deployment and rollback](../deploy/q8-lan-20261004/README.md).

The endpoint uses source `ac398f5eb349eca70a6fd61eea63e824f843c868`, binary SHA256
`95290a8a30c5d8d8984b02b5b7fc3128c8d2745f139891e5bdb9a5a9b5e6a7b9`.
The bandwidth alternative uses source `60e19d404a70edd2e1d6a3c824d0c3ca2096852e`,
binary SHA256 `b09d4aaa17f07d8c1c3e5f65dc22ff4cd80ed0a2c23e44a0001f549cb7b4f89a`.
Profiles refer to the existing immutable exports on llm-60; they do not silently
rebuild a different engine. Credentials are outside the repository.
