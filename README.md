# Experimental Q8 miss-fetch overlap

This is an experimental fork of **[Niko1221/Strata](https://github.com/Niko1221/Strata)**.
Credit for Strata and its existing kernels belongs to upstream and its contributors.

This branch tests uploading missed Q8 experts while resident experts compute.
Explicit captured CUDA dependencies protect plan readiness, completed fills and
buffer reuse. `STRATA_Q8_MISS_FETCH_OVERLAP=0` keeps the original serial path.
The secondary GPU cache is a separate optional switch.

Target: **RTX PRO 6000 Blackwell Workstation Edition 96GB**, Ryzen 7950X,
128GB RAM; full Unsloth Q8_0, FP16 KV, native 32K and 128K.

**Build and 20 GPU component cases passed; memcheck/initcheck: zero errors.**
**All 33 full-model lifecycle requests passed**, covering plain/MTP serial,
overlap, and overlap plus the secondary cache. Paired tokens, recorded work and
main-model state fingerprints matched, including cancellation/recovery and MTP
checkpoint restoration. The four-mode 32K throughput matrix is running;
no speed gain is claimed for overlap yet.

See **[design, invariants and validation plan](docs/Q8_MISS_FETCH_OVERLAP.md)**.
Main and default behavior are unchanged. This fork preserves the upstream license;
use **[upstream Strata](https://github.com/Niko1221/Strata)** for standard installation.
