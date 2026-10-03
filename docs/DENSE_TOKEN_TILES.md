# Dense token tiles: component results, model validation pending

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

Real model state gates, oracle and all four real generation paths are running.
Actual DRAM measurements remain pending. No new model TPS claim is made here.
See [component observations](benchmarks/q4-dense-token-tiles-components-20261003.json).
