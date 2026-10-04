# Experimental Q8 miss-copy concurrency

This is an experimental fork of **[Niko1221/Strata](https://github.com/Niko1221/Strata)**.
Credit for Strata and its existing kernels belongs to upstream and its contributors.

This branch varies how many GPU thread blocks upload missed experts from RAM.
`STRATA_MISS_FETCH_BLOCKS` defaults to the original 384 blocks. Copied bytes,
expert arithmetic and explicit buffer dependencies stay fixed.

Target: **RTX PRO 6000 Blackwell Workstation Edition 96GB**, Ryzen 7950X,
128GB RAM; full Unsloth Q8_0 with FP16 KV and native context.

**Unverified prototype: no speed gain claimed.** The parent overlap experiment
reduced host wait but increased CPU expert time. This branch tests whether
copy concurrency contributes to that tradeoff. Component and full-model checks
are required before selecting a setting.

See **[evidence, hypothesis, invariants and gates](docs/Q8_MISS_FETCH_GEOMETRY.md)**.
The parent overlap and secondary-cache controls remain independent options.
Main is untouched, and this fork preserves the upstream license. For standard
installation and support, use **[upstream Strata](https://github.com/Niko1221/Strata)**.
