# Active-width resources in the wider Q4 verifier

Measured on **llm-60, RTX PRO 6000 Blackwell Workstation Edition, 96 GB VRAM,
128 GB installed RAM**, 2026-10-03. The model is full Unsloth
**Qwen3.8-Flash-Next UD-Q4_K_XL**, all routed experts GPU resident, int8 KV.
The tested source is `49b4c76` (capacity 24).

## Change and gates

`STRATA_HC_ACTIVE_T=1` sizes HC shared storage for the active token count and
specializes the staged down kernel through the largest local chunk (nine).
`STRATA_BF16_ACTIVE_T=1` adds accumulator buckets 12, 16 and 18 instead of
reserving 24 slots for every width above eight. Both are opt-in; the default
control remains available. The wider HC specializations receive the required
shared-memory opt-in before launch.

HC plain/staged and BF16 arithmetic comparisons, memcheck and synccheck passed.
The combined variant matched the old wide build's emitted tokens and committed
target state at output caps 23, 24, 25 and 51, using an 8,192-token prompt and
16,384 allocated context. This does not claim state-hash coverage at 64K.

## Known-answer oracle, single observations

Each request below has **65,536 input tokens**, 73,728 allocated context and a
4,096 output budget. The oracle receives the reference answer and its stopping
length; these are verifier diagnostics, not usable generation speeds.

| Variant | T=8 tok/s | T=16 tok/s |
| --- | ---: | ---: |
| Control | 369.42 | 421.23 |
| HC only | 381.17 | 438.60 |
| BF16 only | 369.21 | 422.86 |
| Both | 381.57 | 440.77 |

HC accounts for most of the observed gain. The small BF16-only difference needs
repetition before it can be called a gain.

## Real generation

All four paths were screened on code, prose and editing with 1,024 output
tokens. The verifier allocation/cap was eight and the MTP cap was four. The best
improving workload for each path advanced to an **ABBA** sequence with a 4,096
output budget. Serial did not improve in the screen and was not repeated.

| Path and workload | Control output tok/s | Both output tok/s | Change | Control effective tok/s | Both effective tok/s |
| --- | ---: | ---: | ---: | ---: | ---: |
| MTP, code | 220.86 | 222.90 | +0.92% | 114.57 | 115.04 |
| N-gram, editing | 321.13 | 328.74 | +2.37% | 86.77 | 87.22 |
| MTP + n-gram, editing | 313.96 | 324.15 | +3.25% | 85.88 | 86.63 |

Numbers are the means of two observations per arm. Effective throughput is
output tokens divided by prefill plus decode time. The code requests all
stopped naturally after **2,467 tokens**, and editing after **1,238**; each
matched control/candidate pair had identical output hashes. These are three
selected workloads, not a broad statistical performance claim.

Serial screen results stayed near **104 tok/s**, with differences under 0.2%.
The n-gram result recovers most of the widened build's regression, but does not
beat the earlier approximately **330 tok/s** result in the capacity-8 build.

The separate wide-policy zero-prior defect affects n-gram choices above eight.
These real-request comparisons cap the policy at eight, so that defect was not
exercised here. The oracle does not use the policy to choose its supplied
windows. Wider real n-gram policy results need the separate repair.

[Evidence](benchmarks/q4-active-width-resources-20261003.json) records the source
and executable hashes, request counts, timing components, individual
observations and gate results. Raw files remain under
`llm-60:~/fleet-downloads/rtxpro-q4-wide-active-shapes-20261003/`.
