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
intervals; native 128K and other decoding modes are still being tested.

| Reversed pair | 384 blocks, serial | 32 blocks, overlap |
|---|---:|---:|
| Coding generation | 132.52 tok/s | 134.88 tok/s |
| Editing generation | 113.46 tok/s | 118.34 tok/s |
| Coding effective, including prefill | 65.47 tok/s | 66.04 tok/s |
| Editing effective, including prefill | 61.01 tok/s | 62.45 tok/s |

The intervention changes upload concurrency, keeping expert placement, math,
FP16 KV, 15,472 primary slots and four secondary slots per layer fixed.
Complete-byte checks passed at default and 1/32/96/384 blocks; six sanitizer
runs reported zero errors. Both serial and overlap paths remain available.

See **[evidence, hypothesis, invariants and gates](docs/Q8_MISS_FETCH_GEOMETRY.md)**.
The parent overlap and secondary-cache controls remain independent options.
Main is untouched, and this fork preserves the upstream license. For standard
installation and support, use **[upstream Strata](https://github.com/Niko1221/Strata)**.
