# Draft-independent IQ dispatch: current-main refresh

Native source tested: `d4cc56ca071b584d4cc32c96e4a745bf15db12a4`, merged with
upstream `61b3fb5dd3f1e8ec09cf7e4e05208bc6d3c46406`. CPU dispatch uses a
one-token minimum for supported IQ kernels and the same rule for IQ4_NL down
rows. This removes the CPU arithmetic switch caused by expert-group occupancy.
`STRATA_IQ_MT_MIN=2` remains a deliberate compatibility/performance comparison;
it restores rounding changes between solo and grouped rows.

## Direct CPU checks and backend builds

Fresh CUDA sm61 and HIP gfx1012 builds passed CPU dispatch bit-parity tests;
forced AVX2/ggml controls passed on the P4 host. The explicit legacy threshold
failed its negative control as expected. HIP and CUDA synthetic native GPU
format checks passed for six IQ gate/up formats paired with IQ4_NL down. SYCL
build and its CPU dispatch/default and legacy-negative controls passed; no SYCL
GPU numerical test is claimed. Synthetic GPU checks use numerical tolerances,
not an end-to-end speculative-output identity guarantee.

## Current model gates: distinguish the fix from remaining failures

The current-main P4 confidence-floor gate failed two prose requests at token 123.
With this fix, that 12-request floor-0/floor-0.95 comparison passed. However, the
separate 14-request comparison that includes no-draft and single-token reference
arms still failed in the mixed CPU/GPU configuration at token 30. Full native
output records, hashes and gate results are retained; this is not reported as an
all-model parity pass.

The same mixed-placement discrepancy reproduced on RTX PRO 6000 Blackwell with
645 cached experts, at token 30 (floor 0) or 62 (floor 0.95). Disabling one-token
self-commit, head mixing, or grouped GR/KV updates did not resolve it. With the
same input/cases and **zero GPU experts**, CPU-only checks passed; the automatic
all-GPU expert-cache code-prompt control also passed. Broader CPU-only controls
passed 18 requests across three prompts on main, this fix and the legacy setting.
Those legacy model probes happen not to flip output IDs; they do not override
the failing direct raw-row negative control.

This isolates the observed problem to the mixed placement in these probes,
without proving its exact cause. CPU and GPU arithmetic need not be identical;
this change does not promise full drafting/pipeline parity. The broader pipeline
gate continues to fail with the same token differences before and after this
CPU fix, and suffix-on-pipeline coverage remains zero. Those are separately
visible findings, not tests silently removed to obtain a passing report.

## Current CPU cost

Ryzen 5 7600X3D, AVX-512, one thread pinned to CPU 2, synthetic 128 MiB expert
weights, widths 1/2/4, three within-process samples and three separate processes
per setting. Default/legacy order alternates. Entries below are the median of
three reported engine-dispatch medians, gate/up plus down, milliseconds per
expert at width 1; positive change means **slower**. Full logs preserve every
method, width, minimum and median. These are CPU expert microbenchmarks, not
whole-model decode speed or model quality measurements.

| Format pair | Default ms | Legacy ms | Time change |
|---|---:|---:|---:|
| iq2_s/iq4_nl | 0.257 | 0.259 | -0.77% |
| iq2_xs/iq4_nl | 0.376 | 0.223 | +68.61% |
| iq2_xxs/iq4_nl | 0.280 | 0.238 | +17.65% |
| iq3_s/iq4_nl | 0.373 | 0.339 | +10.03% |
| iq3_xxs/iq4_nl | 0.334 | 0.295 | +13.22% |
| iq4_xs/iq4_nl | 0.171 | 0.171 | +0.00% |

This numerical-consistency choice can have a substantial single-token cost,
especially IQ2_XS on this CPU. Older measured costs remain separately dated;
this report is not a claim that the new default is faster. Reproduction:

```sh
cmake --build build --target iq_avx2_parity
build/iq_avx2_parity
STRATA_IQ_MT_MIN=2 build/iq_avx2_parity  # expected negative-control exit 1
build/iq_avx2_parity --bench --dispatch --cpu 2 --mb 128 --reps 3 --nt 1,2,4 \
  --pairs iq2_xxs/iq4_nl,iq2_xs/iq4_nl,iq2_s/iq4_nl,iq3_xxs/iq4_nl,iq3_s/iq4_nl,iq4_xs/iq4_nl
```

SYCL CPU measurements used the native SYCL-build parity executable and oneAPI
2026.1 environment. No production server settings were changed. Unattended
microbenchmark campaign time was 33.903s; setup/engineering time is excluded.
