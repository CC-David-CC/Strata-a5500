# Experimental Q8 upload compaction

A small experimental fork of **[Niko1221/Strata](https://github.com/Niko1221/Strata)**.
Credit for Strata and its existing kernels belongs to upstream and its contributors.

This branch tests removing wasted GPU loop iterations from the secondary
expert-cache upload kernel. Hits already skip memory reads, but the existing
kernel still visits their weight ranges. An opt-in compact list makes it visit
only actual uploads, including staging bypasses. Copied bytes, cache policy,
expert computation and publication dependencies stay fixed.

Target: **RTX PRO 6000 Blackwell Workstation Edition 96GB**, Ryzen 7950X,
128GB RAM; full Unsloth **Q8_0, FP16 KV**, native context. Enable with
`STRATA_Q8_COMPACT_MISS_FILL=1`; it is off by default.

**No repeated model speedup: keep this option off for the measured configuration.**
The initial 32K MTP coding +1.40% did not repeat: reversing order gave
**-0.17% coding / +0.23% editing**. At native 128K, it gave **-0.37% / -0.03%**.
Tokens, recorded work and copy counts matched exactly in those pairs.

All 24 throughput requests completed: four modes at 32K initially, a reversed
32K MTP pair and a native 128K MTP pair. The report retains the initial n-gram
output/work differences. All 88 byte cases and four sanitizer runs passed;
the corrected fixture failure remains documented. This branch preserves the
experiment and negative result, not a recommended performance setting.

See [invariants and required tests](docs/Q8_COMPACT_MISS_FILLS.md), and the
[inherited copy-grid measurements](docs/Q8_MISS_FETCH_GEOMETRY.md).
Main is untouched and the upstream license is retained. For standard
installation and support, use [upstream Strata](https://github.com/Niko1221/Strata).
