# Dense token tiles: measured shape tradeoffs

Target: **RTX PRO 6000 Blackwell Workstation Edition, 96 GB**, using the full
Unsloth UD-Q4_K_XL model. This changes the Q8_0 **dense projections inside Q4**;
it is not a benchmark of the full Q8_0 model.

The capacity-24 verifier's paired 96-token Nsight traces showed the dense Q8
projection kernel growing from 72 registers/thread at T=8 to 178 at T=24.
Its summed time grew from 40.99 ms to 62.82 ms while the total kernel count fell.
That suggests a register/occupancy tradeoff worth testing. It does not prove
register pressure is the cause or that DRAM is saturated.

`STRATA_NATIVE_Q8_TOKEN_TILE=2|4|8|12` limits the independent token columns held
by one CTA. Adjacent CTAs compute different token tiles of the same weight row,
so the cache may reuse those weights. The experiment preserves the four-warp
reduction and the per-column accumulation order. It applies only with exact
multi-column mode and `STRATA_NATIVE_Q8_ROWS=1`. Zero is the unchanged default.

This branch inherits the opt-in HC/BF16 active-width changes. Test them
separately; a gain from their combination does not isolate this kernel change.

## Gates and falsification

- `q8_token_tile_bench --selftest`: token widths 1–24, short and odd shapes,
  quant boundaries, scalar format oracle, bitwise comparison and changed-data
  graph replay. Run Compute Sanitizer memcheck too.
- `q8_token_tile_bench --bench`: three actual projection shapes at T=8/16/24,
  rotating at least 512 MiB of weight storage, with reversed variant order.
  CUDA-event times are component measurements, not model throughput.
- Verify committed model state against the untiled control before promotion.
- Measure oracle and real serial/MTP/n-gram/combined paths independently.

More CTAs, duplicate weight reads, integer index arithmetic or L2 pressure may
outweigh reduced registers. No improvement in isolated kernels rejects this
tiling choice; a kernel gain without an end-to-end gain limits its practical
value. Actual DRAM counters are needed before claiming reduced GPU traffic.

## Component results (2026-10-03)

Source `f5f183c` passed the scalar-format/exact comparison fixture, changed-weight
graph replay, Compute Sanitizer memcheck and synccheck on the RTX PRO 6000.
The independent wide-policy CPU regression also passed.

A 12-column tile was the best overall component candidate. Ratios below are
control time / tiled time, averaging the two arm-order medians. Above 1 is
faster. This does not establish an end-to-end improvement.

| Projection (input x output) | T16, tile 12 | T24, tile 12 |
| --- | ---: | ---: |

| 2560 x 10240 | 0.997x | 1.391x |
| 6144 x 2560 | 0.934x | 1.167x |
| 2560 x 248320 | 0.798x | 1.278x |

The same policy improves T24 but can regress T16. This argues for a dispatch
choice based on the active shape if model tests confirm the result. No tiling
occurs when T is at most the selected tile. The first T8 logits control was
faster than subsequent identical-kernel controls (493.68 versus about 735
microseconds); the raw record preserves this timing drift. Do not interpret
that unchanged-kernel difference as an optimization effect.

The model-state and oracle checks are complete below. The broad four-path
comparison and actual DRAM measurements remain in progress.
See [component observations](benchmarks/q4-dense-token-tiles-components-20261003.json).

## Model state and oracle checks

The tiled engine matched the previous target's output tokens and all collected
committed-state fields at output caps 23, 24, 25 and 51, both serial and MTP,
with an 8,192-token prompt and 16,384 allocated context.

The oracle uses known target answers and their stopping length. At 65,536
actual input tokens, 73,728 allocated context and int8 KV, it generated the
same 2,467-token code answer:

| Verification width | Untiled output tok/s | Tile 12 output tok/s |
| --- | ---: | ---: |
| 8 | 369.39 | 369.23 |
| 16 | 420.93 | 404.95 |
| 24 | 402.85 | 431.30 |

These are one observation per cell, not usable generation rates. The T24
improvement supports the component hypothesis; the T16 regression rules out
turning this dispatch on indiscriminately.

## Real n-gram combination screen

The same source (`f5f183c`) includes the finite-cost wide-policy fix and the
independently gated HC/BF16 active-width policies. A randomized editing screen
compared them separately and together, using fresh engines. Here `active`
means both active-width policies; `tiled` means only the 12-column dense tile.
Every response stopped naturally at 1,238 tokens within a 4,096-token budget,
with the frozen reference's exact token hash.

| Variant | Maximum width | Output tok/s |
| --- | ---: | ---: |
| active | 12 | 337.28 |
| control | 12 | 329.18 |
| active | 24 | 319.50 |
| both | 24 | 335.66 |
| control | 24 | 310.55 |
| tiled | 24 | 299.04 |

The oracle gain did not translate directly to real adaptive n-gram decoding:
tiling alone regressed. Its measured timings can change the policy's choice
of future verification widths, so this is an end-to-end result rather than an
isolated fixed-width kernel comparison. The exact output still matched.

Width 12 with active-width policies was selected and repeated A/B/B/A against
width 12 with all three kernel flags off:

| Variant | Mean output tok/s | Mean effective tok/s | Mean wall tok/s |
| --- | ---: | ---: | ---: |
| control | 329.83 | 87.50 | 87.45 |
| active | 337.40 | 87.96 | 87.90 |

This is about 2.3% more decode throughput on the selected editing workload.
Effective throughput includes engine prefill + decode; wall throughput also
includes request protocol overhead. Both exclude engine startup. Two repeats
per arm are a useful confirmation, not a broad confidence interval or a claim
that code/prose improve by the same amount.

The selected configuration is compiled with `STRATA_VERIFY_MAX_T=24`, uses
`STRATA_HC_ACTIVE_T=1`, `STRATA_BF16_ACTIVE_T=1` and
`STRATA_NATIVE_Q8_TOKEN_TILE=0`, and caps n-gram verification at 12. The exact
arguments, environment, request hashes and histograms are retained in the
[structured observations](benchmarks/q4-shape-combinations-20261003.json).
All experts remain resident on the GPU. This is the full Unsloth UD-Q4_K_XL,
not a full Q8-model measurement or a pruned GSQ IQ3 benchmark.

## Broad four-path screen

The Python harness initially rejected widths above eight before loading a
model. Commit `5502c14` fixes that harness bound. The engine stayed at `f5f183c`;
its hash was checked against the previously gated binary.

With runtime verification allocation 16 and MTP cap 4, the repaired 64K-input,
1,024-output screen completed all paths. Values are output tok/s in
**code / prose / editing** order. These are one observation per cell; the
three tasks run sequentially in one fresh engine for each path/variant.

| Path | Control | Tile 12 |
| --- | ---: | ---: |
| serial | 102.53 / 102.50 / 102.79 | 102.51 / 102.46 / 102.76 |
| mtp | 208.60 / 156.52 / 248.37 | 208.24 / 156.77 / 248.59 |
| ngram | 113.69 / 102.28 / 282.01 | 114.09 / 102.53 / 284.11 |
| mtp-ngram | 208.13 / 156.62 / 308.87 | 207.52 / 156.46 / 300.66 |

All matched output hashes passed. No task/path gained the predeclared 1.5%
needed for long repeats. Combined editing regressed by about 2.7%; the other
changes were below 1%. This does not support enabling the tiling policy
broadly. The separate width-24 oracle gain remains a diagnostic observation.

A two-second standalone CUDA probe compile overlapped the serial control's
engine startup, not its requests: compilation ended 2.35 seconds after that
job started, while engine startup alone took 14.57 seconds. Startup is
excluded from these throughput metrics. The scheduling helper was corrected
to reject a parent already stopped by another controller.

Full-model DRAM measurements are still unavailable. User-level NCU lacked
counter permission; the sudo retry exposed a first-graph-upload range issue.
The separate graph-range diagnostic reproduced and isolated that issue. Its
full-model retry hit the original GPU reservation cutoff before validation
completed. Do not compute a new roofline from these runs.

See [four-path observations](benchmarks/q4-tile-four-path-screen-20261003.json).
