# Q8 refills from an existing GPU copy

Experimental work in David's fork of [Niko1221/Strata](https://github.com/Niko1221/Strata).
Target: llm-60, **RTX PRO 6000 Blackwell Workstation Edition 96GB**, 128GB system RAM,
full Unsloth Q8_0, FP16 KV, native RoPE. This is not the upstream default.

## Status

Native build, component/sanitizer checks and all 33 lifecycle requests passed.
The first same-binary 32K MTP pair gained 1.64% coding and 1.50% editing.
All four 32K modes and reversed-order plain/MTP pairs completed. Native 128K was interrupted at the user-requested pause; no 128K result is claimed.
The source starts at cache-budget commit `65a01b4d19de78c4b5d1284f7f7fddef3c50e601`.

## Why try it

The [completed routing census](https://github.com/CC-David-CC/Strata-a5500/tree/diag/q8-cache-routing)
found 4,904 of 7,929 committed MTP primary promotions already in the sixteen-slot-per-layer
secondary GPU cache: 61.85%, or 25.61GB of 41.41GB of refill payload across the two measured
32K-input/1K-output requests. These are opportunities, not an estimated speedup. Delayed
ownership commits can cross request boundaries; the census excludes final pending refills.

## Changes and invariants

- `STRATA_Q8_CACHE_TAG_SNAPSHOT=1` copies 3,072 bytes of tags once per verifier window with
  sixteen slots per layer. It uses the existing end-of-window stream synchronization.
  A completed snapshot is invalidated before the next window can mutate the cache.
- `STRATA_Q8_GPU_REFILL=1` requires that snapshot, duplex transfers, ownership rotation,
  blocking admission, one unsplit GPU stage and the host planner. Remote/peer caches and
  router lookahead are rejected. This first path is restricted to serving.
- Rank, selected swaps, source blob lookups, arithmetic placement and victim preservation
  are unchanged. A cached incoming expert uses D2D instead of H2D; a miss keeps H2D.
- The victim still reaches its RAM exchange buffer before its primary slot is overwritten.
  RAM ownership changes only after the refill completes. The secondary source remains
  immutable until every refill has completed, before the next verifier window starts.
- The secondary cache has no eviction writebacks. This change **does not remove primary
  victim writebacks**. A device pointer from the snapshot does not pin an entry.
- D2D bytes/refill counts are reported separately from H2D bytes. Snapshots have generation
  and byte counters. An exit drain protects source lifetime on failed/partial submission.
- Both flags default to zero. This branch does not combine per-layer admission with GPU
  refills; that combination needs a separate proof of source lifetime.

## Validation and measurements

The queue runs the real-sized 5,222,400-byte expert fixture, Compute Sanitizer memcheck
and initcheck, the original H2D duplex fixture, ownership ASan/UBSan/TSan, and a fresh
ccache-enabled native build. The fixture checks cold/mixed/warm/replaced tags, layers,
bounds, pending observations, close/reopen, both transfer types, unchanged secondary
sources, and every byte of the evicted and incoming experts.

The completed plain/MTP lifecycle requests used control, snapshot-only and refill settings,
including STOP, following requests and MTP checkpoint restoration. Only after those
pass do fresh-engine 32K-input/1K-output coding and editing requests run: plain, MTP,
n-gram and MTP+n-gram. Plain and MTP require exact output and measured work. N-gram
policy can depend on timings; changed outputs/work will be reported explicitly.

Same-binary controls separate tag-copy overhead from D2D benefit. Primary slots 15,472,
secondary slots 16 per layer, PCIe fraction 0.55, copy grid 32 with overlap, full pinned
RAM complement, locked lookup table, native RoPE and FP16 KV stay fixed. Counter
guards require unchanged primary exchanges for matched-work arms and require
`victim D2H bytes = refill H2D bytes + refill D2D bytes`.

No 128K result, repeatability claim or combination gain is implied by this preparation.
The configuration and negative-result reports inherited from the parent branch remain
available under `docs/`; they are not GPU-refill measurements.


## Native correctness gate passed

Source `60e19d404a70edd2e1d6a3c824d0c3ca2096852e`, engine SHA256
`b09d4aaa17f07d8c1c3e5f65dc22ff4cd80ed0a2c23e44a0001f549cb7b4f89a`.
The byte fixture, CUDA memcheck/initcheck, original H2D duplex fixture,
ownership/worker sanitizer checks and fresh native build all passed.

All six lifecycle arms passed: plain/MTP times control, snapshot-only and GPU
refills; 33 requests and 22 exact paired comparisons. Tokens, measured work
and main-model state checks matched, including STOP/following requests and
MTP checkpoint restoration. Full RAM, locked lookup-table and FP16 startup
guards passed; inference expert file reads remained zero.

Counter validation confirms the path actually ran. The refill arm used
8.9877504GB of D2D payload over its three plain lifecycle requests and
8.2618368GB over its eight MTP lifecycle requests. Controls used none. Each
request satisfied `D2H = H2D + D2D`; victim bytes and selected swap counts
matched the corresponding control. Snapshot bytes were exactly 3,072 times
the completed snapshot count. These lifecycle totals are not throughput
results or the previous census workload's payload totals.

[Raw gates, lifecycle comparisons and log hashes/counters](benchmarks/q8-gpu-refill-lifecycle-20261004.json).
No 128K or throughput claim follows from this gate.


## First 32K MTP throughput pair

These are generation rates for 32,768 input + 1,024 output tokens (40,960
allocated), with the fixed setup above. Effective rates include prefill and
generation. Every arm uses the same native binary; no source rebuild separates
the control, tag-snapshot-only and refill settings.

| Setting | Coding output tok/s | Editing output tok/s | Coding effective tok/s | Editing effective tok/s |
|---|---:|---:|---:|---:|
| Control | 138.315 | 124.461 | 66.796 | 64.044 |
| Tag snapshot only | 138.609 | 124.656 | 66.839 | 64.025 |
| GPU refills | 140.584 | 126.322 | 67.360 | 64.521 |

Refills gained **1.64% coding / 1.50% editing** generation throughput and
**0.84% / 0.74%** effective throughput over the same-binary control. The tag-only
arm moved by +0.21% / +0.16%, within the variation of a single pair. All three
arms matched output tokens, measured work, primary swap/victim counts and
secondary-cache counters. These are preliminary observations, not a repeated
performance claim or gains to multiply by another branch's results.

Across these two requests, primary refill H2D payload fell from **41.4084GB
to 15.7978GB**: **25.6106GB (61.85%)** was copied within the GPU instead.
Primary victim D2H stayed at 41.4084GB. This is primary adaptive-refill traffic,
not the total PCIe traffic: verification staging uploads still occur. Fewer
uploads produced a modest timing gain, so upload byte count alone does not
explain the remaining end-to-end bottleneck.

[Raw first-pair records and byte checks](benchmarks/q8-gpu-refill-first-mtp-20261004.json).
The complete four-mode matrix and completed reversed-order 32K pairs are below. The 128K follow-up is paused.


## Complete first 32K matrix

All 20 throughput requests completed; each generated 1,024 tokens from 32,768 input.
Same fixed setup and binary as above. Each row compares its own same-binary control.

| Mode / task | Control output tok/s | GPU refills tok/s | Gain | Control effective tok/s | GPU refills effective tok/s | Qualification |
|---|---:|---:|---:|---:|---:|---|
| plain / coding | 76.215 | 76.781 | +0.74% | 48.033 | 48.151 | Exact tokens and measured work |
| plain / editing | 65.851 | 66.185 | +0.51% | 44.007 | 44.145 | Exact tokens and measured work |
| mtp / coding | 138.315 | 140.584 | +1.64% | 66.796 | 67.360 | Exact tokens and measured work |
| mtp / editing | 124.461 | 126.322 | +1.50% | 64.044 | 64.521 | Exact tokens and measured work |
| ngram / coding | 80.883 | 79.308 | -1.95% | 49.907 | 49.259 | First token difference 288, changed work |
| ngram / editing | 121.568 | 121.467 | -0.08% | 63.369 | 63.363 | Matching tokens, changed work |
| mtp-ngram / coding | 137.853 | 139.669 | +1.32% | 66.786 | 67.110 | Exact tokens and measured work |
| mtp-ngram / editing | 121.963 | 123.800 | +1.51% | 63.330 | 63.812 | Exact tokens and measured work |

Plain, MTP and combined also matched primary swap/victim counts and secondary
cache counters. N-gram alone regressed 1.95% coding and was essentially flat
(-0.08%) editing, with changed speculative work. Keep its earlier configuration
as an alternative; this is not a universal default. Reversed-order 32K plain/MTP
pairs completed on the same binary. The 128K follow-up was interrupted at the user-requested pause, before a candidate result.
No scheduling/refill combination has been tested.

[Complete 32K records](benchmarks/q8-gpu-refill-complete-32k-20261004.json).


## Reversed-order 32K plain and MTP pairs

Candidate ran first, followed by a fresh control from the same binary. Each
request used 32,768 input + 1,024 output, 40,960 allocation and the unchanged
fixed configuration above. The table uses the fresh control in this repeat.

| Mode / task | Control output tok/s | GPU refills tok/s | Gain | Control effective tok/s | GPU refills effective tok/s | Qualification |
|---|---:|---:|---:|---:|---:|---|
| plain / coding | 76.322 | 76.826 | +0.66% | 48.066 | 48.319 | Exact tokens and measured work |
| plain / editing | 65.816 | 66.340 | +0.80% | 43.979 | 44.217 | Exact tokens and measured work |
| mtp / coding | 138.738 | 140.690 | +1.41% | 66.943 | 67.391 | Exact tokens and measured work |
| mtp / editing | 124.556 | 126.273 | +1.38% | 64.067 | 64.530 | Exact tokens and measured work |

Every pair matched output tokens, measured work, primary victim/swap counts
and secondary-cache counters. MTP's refill-upload reduction remained 61.85%;
primary writebacks were unchanged. Two run orders do not establish a confidence
interval. These small gains should remain qualified to the tested workloads.

[Raw observations and independent counter checks](benchmarks/q8-gpu-refill-reverse-32k-20261004.json).
