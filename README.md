# Experimental Q8 miss-copy concurrency

This is an experimental fork of **[Niko1221/Strata](https://github.com/Niko1221/Strata)**.
Credit for Strata and its existing kernels belongs to upstream and its contributors.

This branch varies how many GPU thread blocks upload missed experts from RAM.
`STRATA_MISS_FETCH_BLOCKS` defaults to the original 384 blocks. Copied bytes,
expert arithmetic and explicit buffer dependencies stay fixed.

Target: **RTX PRO 6000 Blackwell Workstation Edition 96GB**, Ryzen 7950X,
128GB RAM; full Unsloth Q8_0 with FP16 KV and native context.

**Measured at 32K input + 1,024 output, with MTP:** 32 copy blocks with upload
overlap improved editing generation by **4.26% and 4.31%** in the initial and
reversed-order pairs versus 384 blocks without overlap. Coding improved
**1.47% and 1.78%**. All output tokens, recorded work and logical copy counts
matched. These are two paired observations, without population confidence
intervals. A native **128K** MTP triple also passed with exact tokens/work:
coding **133.72 to 136.52 tok/s (+2.09%)**, editing **107.75 to 112.38 tok/s
(+4.30%)**. All four decoding modes have now completed comparisons at both 32K and
128K input; n-gram qualifications are retained below and in the report.

| Reversed pair | 384 blocks, serial | 32 blocks, overlap |
|---|---:|---:|
| Coding generation | 132.52 tok/s | 134.88 tok/s |
| Editing generation | 113.46 tok/s | 118.34 tok/s |
| Coding effective, including prefill | 65.47 tok/s | 66.04 tok/s |
| Editing effective, including prefill | 61.01 tok/s | 62.45 tok/s |

Other completed **32K input + 1,024 output** pairs:

| Mode | Coding: 384 serial → 32 overlap | Editing: 384 serial → 32 overlap |
|---|---:|---:|
| Plain | 74.21 → 74.66 tok/s | 62.38 → 63.22 tok/s |
| N-gram* | 78.76 → 75.80 tok/s | 107.04 → 118.53 tok/s |
| MTP + n-gram* | 131.85 → 135.90 tok/s | 111.48 → 120.21 tok/s |

Plain tokens and recorded work matched. **\* N-gram comparisons are qualified:**
editing tokens matched, but speculative work changed; coding tokens diverged
with overlap. These are request observations, not isolated same-work kernel
gains or proof of equivalent answer quality. Full differences and effective
throughput are in the report below.

The intervention changes upload concurrency, keeping expert math, FP16 KV,
15,472 primary slots, four secondary slots per layer and the selection policy
fixed. Timing-sensitive n-gram work can change the subsequent adaptive
placement trajectory; those comparisons retain their qualifications.
Complete-byte checks passed at default and 1/32/96/384 blocks; six sanitizer
runs reported zero errors. Both serial and overlap paths remain available.

See **[evidence, hypothesis, invariants and gates](docs/Q8_MISS_FETCH_GEOMETRY.md)**.
The parent overlap and secondary-cache controls remain independent options.
Main is untouched, and this fork preserves the upstream license. For standard
installation and support, use **[upstream Strata](https://github.com/Niko1221/Strata)**.

## Native 128K input + 1,024 output

| Mode, 32 copy blocks with overlap | Coding output tok/s | Editing output tok/s |
|---|---:|---:|
| plain | 75.71 | 61.14 |
| mtp | 136.52 | 112.38 |
| ngram* | 75.18 | 104.63 |
| mtp-ngram* | 135.81 | 113.13 |

Plain and MTP preserve tokens and recorded work. **\* N-gram comparisons
retain timing-dependent work/output differences**; see the report for the
control rates, first differing tokens and prefill-inclusive throughput.
